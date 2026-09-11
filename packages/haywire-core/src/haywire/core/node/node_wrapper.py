"""Lifecycle management for one Haywire node instance: creation, hot reload,
serialization and cleanup.
"""

import time
import threading
import logging
from typing import List, Optional, Tuple, Any, Dict, TYPE_CHECKING
from dataclasses import dataclass, field

from ..graph.types import ChangeReason
from haywire.core.node.node_warning import NodeWarning
from ..errors import HaywireException
from ..registry.lifecycle_event import LifeCycleEvent
from ..validation.interface import IStructuralValidator

if TYPE_CHECKING:
    from ..graph.base import BaseGraph
    from ..execution.execution_context import ExecutionContext
    from . import BaseNode

logger = logging.getLogger(__name__)


@dataclass
class NodeWrapperState:
    """Lifecycle state of wrapper and its node instance"""

    is_registered: bool = False
    """The node has been registered with the graph"""
    is_imported: bool = False
    """The node class has been imported"""
    is_instantiated: bool = False
    """The node instance has been created"""
    is_initialized: bool = False
    """The node is initialized"""
    is_structural: bool = False
    """The node has passed structural validation"""
    has_test_passed: bool = False
    """The node has been successfully tested"""
    is_executing: bool = False
    error_import: Optional[HaywireException] = None
    """node import error"""
    error_instantiate: Optional[HaywireException] = None
    """node instantiate error"""
    error_initialize: Optional[HaywireException] = None
    """node initialize error"""
    error_structural: Optional[HaywireException] = None
    """node structural validation error"""
    error_custom: Optional[HaywireException] = None
    """node custom error """
    error_test: Optional[HaywireException] = None
    """node test error"""
    error_runtime: Optional[HaywireException] = None
    """node runtime error (startup, execution, shutdown)"""
    test_execution_time_ns: float = 0.0
    """Duration of the last on_testrun() call, in microseconds despite the name"""
    warnings: list[NodeWarning] = field(default_factory=list)
    """Advisory, non-fatal notices such as compatibility warnings. They do not
    affect is_valid()."""

    def is_valid(self) -> bool:
        """True once every stage has passed: registered, imported, instantiated,
        initialized, structurally valid and tested."""
        return (
            self.is_registered
            and self.is_imported
            and self.is_instantiated
            and self.is_initialized
            and self.is_structural
            and self.has_test_passed
        )

    def get_errors(self) -> list[HaywireException] | None:
        """Every error recorded on this node, or ``None`` if there are none. Carrying
        an error does not necessarily make the node invalid."""
        error: list[HaywireException] = []
        if self.error_import:
            error.append(self.error_import)
        if self.error_instantiate:
            error.append(self.error_instantiate)
        if self.error_initialize:
            error.append(self.error_initialize)
        if self.error_structural:
            error.append(self.error_structural)
        if self.error_test:
            error.append(self.error_test)
        if self.error_custom:
            error.append(self.error_custom)
        if self.error_runtime:
            error.append(self.error_runtime)

        return error if error else None

    def _clear_errors(self) -> None:
        """Clear all error states"""
        # self.error_import = None -> we dont clear import errors here,
        # this error can only be cleared on hot reload
        self.error_instantiate = None
        self.error_initialize = None
        self.error_structural = None
        self.error_test = None
        self.error_custom = None
        self.error_runtime = None

    def add_warning(self, warning: NodeWarning) -> None:
        """Append an advisory warning."""
        self.warnings.append(warning)

    def has_warning(self) -> bool:
        """True if any advisory warning is present."""
        return bool(self.warnings)

    def clear_warnings(self) -> None:
        """Drop all advisory warnings (e.g. before a re-check)."""
        self.warnings.clear()


class NodeWrapper:
    """Manages the complete lifecycle of one node instance.

    Instantiates, initializes, structurally validates and tests the node; reacts
    to the node class being reloaded, added or removed; serializes the node with
    the graph; and releases it on cleanup.
    """

    def __init__(
        self,
        registry_key: str,
        node_id: str,
        graph: "BaseGraph",
        position: Tuple[float, float] = (3750, 3750),
    ):
        """Initialize a new NodeWrapper.

        Args:
            position: Initial (x, y) canvas position of the node.
        """
        self.registry_key = registry_key
        """The registry key of the node class. Only _rebuild() may change it."""
        self._node_id = node_id
        """The node instance's ID, fixed for the wrapper's lifetime."""
        self._graph = graph
        """Parent graph instance"""

        from haywire.core.di.context import get_node_factory

        self._node_factory = get_node_factory()

        self._node_factory.add_event_subscriber(self.registry_key, self._on_node_lifecycle_event)

        # Thread safety
        self._lock = threading.RLock()

        # Cleanup flag — signals that cleanup() has run and callers must not
        # access the wrapper's fields. Mirrors Settings._cleaned_up.
        self._cleaned_up: bool = False

        # Lifecycle state
        self._state: NodeWrapperState = NodeWrapperState()

        self._node_cls: type["BaseNode"] | None = None
        self._node_instance: Optional["BaseNode"] = None

        # Store initial position for later initialization
        self._initial_position = position

        # Reference to structural validator from graph
        self._structural_validator: "IStructuralValidator" = self._graph._structural

        self._alternate_registry_keys: List[str] = []
        """Alternate registry keys for this node if the specific version is not available"""

        self._is_dirty_structural: bool = False

        self._import_node_cls()

    @property
    def node(self) -> "BaseNode":
        """The current node instance.

        Raises:
            RuntimeError: If the node has not been built yet, or has been cleaned up.
        """
        with self._lock:
            if self._node_instance is None:
                raise RuntimeError(
                    f"NodeWrapper '{self.registry_key}' has no node instance "
                    f"(not built or already cleaned up)."
                )
            return self._node_instance

    def is_valid(self) -> bool:
        """True when the node has passed every lifecycle stage. See ``NodeWrapperState.is_valid``."""
        return self._state.is_valid()

    @property
    def state(self) -> NodeWrapperState:
        """Get the wrapper's lifecycle state.

        Raises:
            RuntimeError: If the wrapper has been cleaned up.
        """
        if self._state is None:
            raise RuntimeError(f"NodeWrapper '{self.registry_key}' state has been cleaned up.")
        return self._state

    @property
    def node_id(self) -> str:
        """Get the node id"""
        return self._node_id

    @property
    def graph(self) -> "BaseGraph":
        """The parent graph this wrapper belongs to."""
        return self._graph

    def set_as_registered(self, is_registered: bool) -> None:
        """Record whether the node is registered with the graph."""
        with self._lock:
            self._state.is_registered = is_registered

    # =========================================================================
    # House Keeping & Validation
    # =========================================================================

    def _import_node_cls(self):
        """Resolve the node class for ``registry_key``, recording any import error
        and, when it fails, the alternate registry keys to offer instead."""
        self._node_cls, self._state.error_import = self._node_factory.get_node(self.registry_key)
        if self._state.error_import:
            self._state.is_imported = False
            self._state.error_import.enrich(
                node_id=self._node_id,
                graph_id=self._graph.graph_id,
            ).log(logger)
            self._alternate_registry_keys = self._node_factory.get_alternate_node_registry_keys(
                self.registry_key
            )
        else:
            self._state.is_imported = True

    def _rebuild(self, registry_key: str) -> None:
        """Rebuild the node under a new registry key, carrying its serialized state over."""
        with self._lock:
            self.registry_key = registry_key
            self._import_node_cls()
            node_info = self._node_instance._to_dict() if self._node_instance is not None else None
            self.build(node_info)
            # Tell graph about need for hot reload
            if self._graph:
                self._graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_HOT_RELOADED)

    def build(self, node_info: Optional[Dict[str, Any]] = None):
        """Build the node: instantiate, initialize, validate structurally, then test it.

        Clears any recorded errors and advisory warnings first, and subscribes to
        the redraw-triggering props afterwards. Failures are recorded on
        ``state`` rather than raised.

        Args:
            node_info: Serialized node data to restore from; ``None`` builds a
                fresh node through its ``init()``.
        """
        with self._lock:
            logger.debug(f"Start node building: {self._node_id} ... ")

            self._state._clear_errors()
            # Advisory warnings come from the saved file; a rebuild re-derives the
            # node from current code, so none of them apply to the result.
            self._state.clear_warnings()

            if (
                self._instantiate()
                and self._initialize(node_info)
                and self._structural_validation()
                and self._test()
            ):
                logger.debug(f"Node building succeeded: {self._node_id}")
            else:
                logger.debug(".. building failed with errors.")

            self._subscribe_props_redraw()

    def _instantiate(self) -> bool:
        """Create the node instance, cleaning up any existing one first.

        Returns whether it succeeded; a failure lands in ``state.error_instantiate``.
        """
        if self._node_cls is None:
            return False
        node_cls = self._node_cls  # narrowed for the rest of the method
        try:
            if self._node_instance:
                # TODO: Create Garbage Collection for old instance
                self._node_instance._cleanup()
                self._node_instance = None
            self._node_instance = node_cls(self._node_id, self)
            self._node_instance.props.set_position(self._initial_position)
            self._state.is_instantiated = True
            self._state.error_instantiate = None

            return True

        except Exception as e:
            self._state.error_instantiate = HaywireException.from_exception(
                exception=e,
                operation="Instantiate Node",
                message=f"Failed to instantiate node '{self.registry_key}'",
            ).enrich(
                module_name=node_cls.__module__,
                registry_key=self.registry_key,
                class_name=node_cls.__name__,
                library_identity=node_cls.class_library,
                node_id=self._node_id,
                graph_id=self._graph.graph_id,
            )
            self._state.error_instantiate.log(logger)
            self._state.is_instantiated = False

        return False

    def _initialize(self, node_info: Optional[Dict[str, Any]] = None) -> bool:
        """Bring the node to its initial state — from *node_info* if given, else
        through its ``init()`` — and run ``post_init()`` last.

        Returns whether it succeeded; a failure lands in ``state.error_initialize``.
        """
        assert self._node_instance is not None, "must be set by _instantiate"
        assert self._node_cls is not None, "must be set by _import_node_cls"
        node_instance = self._node_instance
        node_cls = self._node_cls
        try:
            if node_info:
                # _initialize_from_dict regenerates promoted ports itself, from
                # the restored _promoted_keys.
                node_instance._initialize_from_dict(node_info)
            else:
                node_instance.init()
                # Fresh drop: realise the setting(promote_default=...) seeds the bags
                # recorded at construction, through the same call the load path makes,
                # so promoted ports land after the author-declared ports either way.
                node_instance._regenerate_promoted_ports()
            node_instance.post_init()
            self._state.is_initialized = True
            self._state.error_initialize = None
            return True
        except Exception as e:
            self._state.error_initialize = HaywireException.from_exception(
                exception=e,
                operation="Initialize Node",
                message=f"Failed to initialize node '{self.registry_key}'",
            ).enrich(
                node_id=self._node_id,
                graph_id=self._graph.graph_id,
                registry_key=self.registry_key,
                module_name=node_cls.__module__,
                library_identity=node_cls.class_library,
            )
            self._state.error_initialize.log(logger)
            self._state.is_initialized = False

        return False

    def _structural_validation(self) -> bool:
        """Check the node against the graph's structural validator — event-node
        constraints, control-flow topology, and the like.

        Returns whether it passed; a failure lands in ``state.error_structural``.
        """
        assert self._node_cls is not None, "must be set by _import_node_cls"
        node_cls = self._node_cls
        try:
            (is_valid, error_message, suggestions) = self._structural_validator.validate_node(self)

            self._state.is_structural = is_valid

            if not is_valid and error_message:
                self._state.error_structural = HaywireException.create(message=error_message).enrich(
                    node_id=self._node_id,
                    graph_id=self._graph.graph_id,
                    registry_key=self.registry_key,
                    module_name=node_cls.__module__,
                    library_identity=node_cls.class_library,
                    operation="Structural Validation",
                    category="Structural Validation Error",
                    suggestions=suggestions,
                )
                self._state.error_structural.log(logger)
            else:
                self._state.error_structural = None

            return is_valid

        except Exception as e:
            self._state.error_structural = HaywireException.from_exception(
                exception=e, message=f"Structural validation failed: {e}"
            ).enrich(
                node_id=self._node_id,
                graph_id=self._graph.graph_id,
                registry_key=self.registry_key,
                module_name=node_cls.__module__,
                library_identity=node_cls.class_library,
                operation="Structural Validation",
                category="Structural Validation Error",
                suggestions=[
                    "Check node type and event node constraints",
                    "Verify control flow requirements if applicable",
                ],
            )
            self._state.error_structural.log(logger)
            self._state.is_structural = False
            return False

    def _test(self) -> bool:
        """Run the node's ``on_testrun()``, recording its verdict and duration.

        Returns whether the test passed; a failure lands in ``state.error_test``.
        """

        try:
            if self._node_instance:
                start_time = time.perf_counter()
                success, error = self._node_instance.on_testrun()

                execution_time = (time.perf_counter() - start_time) * 1000000.0
                self._state.test_execution_time_ns = execution_time

                self._state.has_test_passed = success
                if not success and error:
                    self._state.error_test = HaywireException.create(
                        message=f"Node test execution failed: {error}"
                    ).enrich(
                        module_name=self._node_cls.__module__,
                        registry_key=self.registry_key,
                        node_id=self._node_id,
                        graph_id=self._graph.graph_id,
                        operation="Node Test Execution",
                        category="Node Execution Error",
                        suggestions=[
                            "Check the test() method implementation",
                            "Ensure all required ports exist",
                        ],
                    )
                else:
                    self._state.error_test = None

                return success

        except Exception as e:
            self._state.error_test = HaywireException.from_exception(
                exception=e, message=f"Node test execution failed: {e}"
            ).enrich(
                operation="Node Test Execution",
                category="Node Execution Error",
                node_id=self._node_id,
                graph_id=self._graph.graph_id,
            )
            self._state.error_test.log(logger)
            self._state.has_test_passed = False

        return False

    def _on_node_lifecycle_event(self, lc_event: LifeCycleEvent) -> None:
        """React to the node class being reloaded, added or removed.

        A removal or error event records an import error; a successful reload
        adopts the new class. Either way the node is marked dirty, so the graph
        rebuilds or reports it.
        """
        with self._lock:
            logger.info(
                f"NodeWrapper {self._node_id}: Detected life cycle event - {lc_event.event_type.value}"
            )

            if lc_event.is_warning_event():
                if lc_event.is_removal():
                    # The registry does not flag a removal as an error, but the node
                    # is unusable without its class, so record one here.
                    self._state.error_import = HaywireException(
                        operation="Node Removed",
                        message=(
                            f"Node '{self.registry_key}' has been removed "
                            f"from the registry and can no longer be used."
                        ),
                    ).enrich(
                        node_id=self._node_id,
                        graph_id=self._graph.graph_id,
                        registry_key=self.registry_key,
                        module_name=lc_event.module_name,
                        library_identity=lc_event.library_identity,
                        suggestions=[
                            "Re-add the node class to the registry",
                        ],
                    )
                else:
                    self._state.error_import = lc_event.error

                if self._state.error_import:
                    self._state.error_import.log(logger)

                # Tell graph about error
                if self._graph:
                    self._graph._validation.mark_node_dirty(
                        self._node_id, ChangeReason.NODE_HOT_RELOAD_ERROR
                    )
                return  # abort further processing

            # Successful reload - update class reference
            self._node_cls = lc_event.affected_class
            self._state.error_import = None
            self._state.is_imported = True

            # Tell graph about need for hot reload (will trigger rebuild via validation)
            if self._graph:
                self._graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_HOT_RELOADED)

    def cleanup(self) -> None:
        """Release the node instance and the factory subscription.

        Callers must not touch the wrapper's fields afterwards. Calling it a
        second time does nothing.
        """
        with self._lock:
            if self._cleaned_up:
                return
            # Remove event subscription
            self._node_factory.remove_event_subscriber(self.registry_key, self._on_node_lifecycle_event)

            self._node_cls = None
            if self._node_instance:
                self._node_instance._cleanup()
                self._node_instance = None
            self._cleaned_up = True

    # =========================================================================
    # RUNTIME OPERATIONS
    # =========================================================================

    def move(self, new_x: float, new_y: float):
        """Move the node, and record the position a later rebuild restores it to."""
        self._initial_position = (new_x, new_y)
        if self._node_instance:
            self._node_instance.props.set_position(self._initial_position)

    def _add_runtime_error(self, error: HaywireException) -> None:
        """Record a runtime error, replacing any error already held.

        Only the first error after a clear triggers a redraw, so a node failing
        every loop iteration cannot flood the UI.
        """
        if self._state.error_runtime is None:
            self._state.error_runtime = error
            self.redraw()
        else:
            self._state.error_runtime = error

    def clear_runtime_errors(self) -> None:
        """Clear all runtime errors and trigger redraw if any existed"""
        if self._state.error_runtime is not None:
            self._state.error_runtime = None
            self.redraw()

    # =========================================================================
    # Wrapper Runtime Hooks
    # =========================================================================

    def on_startup(self, exec_ctx: "ExecutionContext") -> None:
        """Wrapper-level startup hook, run as the flow starts."""

    def on_shutdown(self, exec_ctx: "ExecutionContext") -> None:
        """Wrapper-level shutdown hook, run once the last node in the flow has executed."""
        ...

    # =========================================================================
    # Node Change Notifications
    # =========================================================================

    def mark_as_structuraly_dirty(self) -> None:
        """Mark the node as needing structural re-validation.

        Call it whenever the node changes its inlets or outlets. It does nothing
        until the node is registered with the graph.
        """
        with self._lock:
            # Notify graph of redraw request
            if self._graph and not self._is_dirty_structural and self.state.is_registered:
                self._graph._validation.mark_node_dirty(
                    self._node_id, ChangeReason.NODE_VALIDATION_REQUESTED
                )
                self._is_dirty_structural = True

    def redraw(self) -> None:
        """Request a redraw of the node in the UI."""
        with self._lock:
            # Notify graph of redraw request
            if self._graph:
                self._graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_REDRAW_REQUESTED)

    def _subscribe_props_redraw(self) -> None:
        """Watch the instance's appearance-affecting props and redraw on change."""
        if self._node_instance is None:
            return

        for field_name in type(self._node_instance.props).REDRAW_FIELDS:
            self._node_instance.props._subscribe_field(field_name, self._on_props_redraw_change)

    def _on_props_redraw_change(self, _value: Any, _old: Any) -> None:
        """Cell-event adapter to request a debounced redraw."""
        self.redraw()

    def request_graph_reassembly(self) -> None:
        """Ask the graph to regenerate the flow structure, rebuilding and redrawing nothing.

        Call it when a setting inside the node changed something the flow
        assembler reads. When the node's inlets or outlets changed instead, call
        ``mark_as_structuraly_dirty()``.
        """
        with self._lock:
            # Notify graph of reassembly request
            if self._graph:
                self._graph._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY)

    def _housekeeping(self) -> None:
        """Rebuild the node's port pipelines if it is structurally dirty.

        Called by graph validation or after deserialization, never from inside a
        node.
        """
        with self._lock:
            if self._node_instance:
                if self._is_dirty_structural:
                    self._node_instance._housekeeping()
                    self._is_dirty_structural = False

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def serialize(self, include_data: bool = True) -> Dict[str, Any]:
        """Return the wrapper and node state for a graph save, calling the node's
        ``on_saved()`` first.

        Args:
            include_data: When True, port field values are included.
        """
        with self._lock:
            if self._node_instance:
                self._node_instance.on_saved()

            result: dict[str, Any] = {
                "node_id": self._node_id,
                "registry_key": self.registry_key,
                "position": list(self._initial_position),
            }

            if self._node_instance:
                result["node_data"] = self._node_instance._to_dict(include_data=include_data)

            return result

    def __repr__(self) -> str:
        return (
            f"NodeWrapper(id={self._node_id}, "
            f"registry_key={self.registry_key}, valid={self._state.is_valid()})"
        )
