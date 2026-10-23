"""Lifecycle management for one Haywire node instance: creation, hot reload,
serialization and cleanup.
"""

import copy
import time
import threading
import logging
from contextlib import contextmanager
from collections.abc import Mapping
from typing import List, Optional, Any, Dict, Iterator, TYPE_CHECKING
from dataclasses import dataclass, field

from ..graph.types import ChangeReason
from .layout import PATCH, STAGE, LayoutChannel, position_of
from haywire.core.node.node_warning import NodeWarning
from ..errors import HaywireException
from ..registry.lifecycle_event import LifeCycleEvent
from ..validation.interface import IStructuralValidator

if TYPE_CHECKING:
    from ..graph.base import BaseGraph
    from ..execution.execution_context import ExecutionContext
    from . import BaseNode

logger = logging.getLogger(__name__)

#: The props fields besides the patch position that a rebuild carries over: the node's
#: arrangement (stacking order, place on stage). Sizes reset. See ADR 0053.
_CARRIED_ARRANGEMENT = ("z", "on_stage", "stage_x", "stage_y", "stage_z")


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
    ):
        """Initialize a new NodeWrapper."""
        self.registry_key = registry_key
        """The registry key of the node class, fixed for the wrapper's lifetime."""
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

        # Reference to structural validator from graph
        self._structural_validator: "IStructuralValidator" = self._graph._structural

        self._alternate_registry_keys: List[str] = []
        """Alternate registry keys for this node if the specific version is not available"""

        self._is_dirty_structural: bool = False

        self._pending_position: tuple[float, float] | None = None
        """Where the node goes once it has an instance; held only while ``_node_instance`` is
        ``None``, because props are the position's only home. See ADR 0053."""

        self._rebuild_data: Optional[Dict[str, Any]] = None
        """Node data the next requested rebuild restores exactly; see ``BaseGraph.request_node_rebuild``."""

        self._stand_in_data: Optional[Dict[str, Any]] = None
        """The node data a stand-in keeps for the node it replaces: saved back as is, and
        rebuilt from once the node's class works. See ADR 0058."""

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

    def set_rebuild_data(self, node_data: Optional[Dict[str, Any]]) -> None:
        """Hold *node_data* for the next requested rebuild; ``None`` rebuilds through ``init()``."""
        with self._lock:
            self._rebuild_data = node_data

    def take_rebuild_data(self) -> Optional[Dict[str, Any]]:
        """Return the data held for the next requested rebuild, and clear it."""
        with self._lock:
            data, self._rebuild_data = self._rebuild_data, None
            return data

    @property
    def is_stand_in(self) -> bool:
        """True while an error node stands in for this wrapper's node.

        That is the case when the node's class is unknown or its constructor
        raised. The stand-in shows the error, keeps the node's place and
        connections, and saves the node's original data back. See ADR 0058.
        """
        instance = self._node_instance
        if instance is None:
            return False
        identity = type(instance).class_identity
        return bool(getattr(identity, "_is_error", False)) and identity.registry_key != self.registry_key

    def _stand_in_save_data(self, include_data: bool = True) -> Dict[str, Any]:
        """The kept node data with the props the user can change on the stand-in's card;
        without ``include_data``, the ports' values are left out as ``Port.to_dict`` does."""
        assert self._stand_in_data is not None and self._node_instance is not None
        data = copy.deepcopy(self._stand_in_data)
        live = self._node_instance._to_dict()
        data["props"] = live["props"]
        data.setdefault("settings", {})["props"] = live["settings"]["props"]
        if not include_data:
            for port in data.get("ports", {}).values():
                port.pop("field_data", None)
        return data

    @property
    def is_cleaned_up(self) -> bool:
        """True once ``cleanup()`` has released the node instance."""
        return self._cleaned_up

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

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Hold this node's lock, with the graph's validation lock taken first.

        A validation batch holds the graph's lock while it builds and
        housekeeps nodes, and node code run under this lock can mark the graph
        dirty; taking the two in this order on every thread keeps them from
        deadlocking. Without a graph only the node's lock is taken.
        """
        graph = self._graph
        if graph is None:
            with self._lock:
                yield
            return
        with graph._validation.lock, self._lock:
            yield

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

    def build(self, node_info: Optional[Dict[str, Any]] = None):
        """Build the node: instantiate, initialize, validate structurally, then test it.

        Clears any recorded errors and advisory warnings first, and subscribes to
        the redraw-triggering props afterwards. Failures are recorded on
        ``state`` rather than raised.

        Args:
            node_info: Serialized node data to restore from. ``None`` builds a fresh
                node through its ``init()``; a stand-in instead rebuilds from the data
                it keeps, with its current props (see ``is_stand_in``).
        """
        with self._locked():
            logger.debug(f"Start node building: {self._node_id} ... ")

            self._state._clear_errors()
            # Advisory warnings come from the saved file; a rebuild re-derives the
            # node from current code, so none of them apply to the result.
            self._state.clear_warnings()

            if not node_info and self.is_stand_in and self._stand_in_data is not None:
                node_info = self._stand_in_save_data()

            if (
                self._instantiate(node_info)
                and self._initialize(node_info)
                and self._structural_validation()
                and self._test()
            ):
                logger.debug(f"Node building succeeded: {self._node_id}")
            else:
                logger.debug(".. building failed with errors.")

            self._subscribe_props_redraw()
            self._subscribe_stage_membership()

    def _instantiate(self, node_info: Optional[Dict[str, Any]] = None) -> bool:
        """Create the node instance, cleaning up any existing one first; the node keeps its arrangement.

        A rebuild carries over the patch position, the stacking order and the place on
        stage; everything else resets.

        When the class's constructor raises, the failure lands in ``state.error_instantiate``
        and an error node stands in, keeping the node's data (see ``is_stand_in``).

        Returns ``False`` only when no instance could be made, not even the stand-in;
        the position then waits for the next build.
        """
        if self._node_cls is None:
            return False
        node_cls = self._node_cls  # narrowed for the rest of the method
        carried_position = None
        carried_arrangement: Dict[str, Any] = {}
        # The node's data as it stands, kept by a stand-in if the class below fails to build.
        original = node_info or None
        if original is None and self._node_instance is not None:
            if self.is_stand_in:
                original = self._stand_in_data
            else:
                try:
                    original = self._node_instance._to_dict()
                except Exception:
                    # Only a stand-in would need it; the rebuild goes ahead without it.
                    logger.warning(f"Node {self._node_id}: no data kept for a stand-in", exc_info=True)
        try:
            if self._node_instance:
                # A rebuild keeps the node where it is; everything else resets.
                props = self._node_instance.props
                carried_position = props.get_position()
                carried_arrangement = {name: getattr(props, name) for name in _CARRIED_ARRANGEMENT}
                # TODO: Create Garbage Collection for old instance
                self._node_instance._cleanup()
                self._node_instance = None
            elif self._pending_position is not None:
                carried_position = self._pending_position
            self._node_instance = node_cls(self._node_id, self)
            if carried_position is not None:
                self._node_instance.props.set_position(carried_position)
            for name, value in carried_arrangement.items():
                setattr(self._node_instance.props, name, value)
            self._pending_position = None
            self._state.is_instantiated = True
            self._state.error_instantiate = None
            self._stand_in_data = copy.deepcopy(original) if self.is_stand_in else None

            return True

        except Exception as e:
            if carried_position is None and node_info:
                carried_position = position_of({"node_data": node_info})
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
            return self._stand_in(original, carried_position)

        return False

    def _stand_in(self, original: Optional[Dict[str, Any]], position: tuple[float, float] | None) -> bool:
        """Put the error node in place of a node whose class failed to construct.

        Returns whether it stood in; when the error node cannot be built either, the
        wrapper holds no instance and ``position`` waits for the next build.
        """
        try:
            error_cls = self._node_factory.get_error_node(self.registry_key)
            self._node_instance = error_cls(self._node_id, self)
        except Exception as e:
            self._node_instance = None
            self._pending_position = position
            HaywireException.from_exception(
                exception=e, operation="Instantiate Node", message="The error node could not stand in"
            ).log(logger)
            return False
        if position is not None:
            self._node_instance.props.set_position(position)
        self._pending_position = None
        self._stand_in_data = copy.deepcopy(original)
        return True

    def _initialize(self, node_info: Optional[Dict[str, Any]] = None) -> bool:
        """Bring the node to its initial state — from *node_info* if given, else
        through its ``init()`` — and run ``post_init()`` last.

        Returns whether it succeeded; a failure lands in ``state.error_initialize``.
        """
        assert self._node_instance is not None, "must be set by _instantiate"
        assert self._node_cls is not None, "must be set by _import_node_cls"
        node_instance = self._node_instance
        node_cls = self._node_cls
        if not node_info and self.is_stand_in:
            # A rebuild without data that failed to construct: the stand-in takes the old node's data.
            node_info = self._stand_in_data
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
        with self._locked():
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

            # A node whose definition lives outside its class absorbs the reload
            # itself, keeping values and label the generic rebuild would discard.
            if self._node_instance is not None:
                try:
                    if self._node_instance.on_class_reloaded(lc_event):
                        return
                except Exception as e:
                    HaywireException.from_exception(
                        exception=e,
                        operation="Node Class Reloaded",
                        message=(
                            f"Node '{self.registry_key}' failed to absorb its class reload; "
                            f"rebuilding it instead."
                        ),
                    ).enrich(
                        node_id=self._node_id,
                        graph_id=self._graph.graph_id,
                        registry_key=self.registry_key,
                    ).log(logger)

            # Tell graph about need for hot reload (will trigger rebuild via validation)
            if self._graph:
                self._graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_HOT_RELOADED)

    def cleanup(self) -> None:
        """Release the node instance and the factory subscription.

        Callers must not touch the wrapper's fields afterwards. Calling it a
        second time does nothing.
        """
        with self._locked():
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

    def move(self, new_x: float, new_y: float, channel: LayoutChannel = PATCH):
        """Move the node to ``(new_x, new_y)`` in canvas coordinates, in ``channel``."""
        if self._node_instance:
            self._node_instance.props.set_position((new_x, new_y), channel)
        elif channel is PATCH:
            self._pending_position = (new_x, new_y)

    def set_props(self, values: Mapping[str, Any]) -> None:
        """Set ``NodeProperties`` fields from ``{name: value}``, e.g. a new node's stage placement.

        A stand-in takes them like any node and saves them. A wrapper holding no instance
        at all keeps only the patch position (``posX``/``posY``), for the next build.
        """
        if self._node_instance is not None:
            for name, value in values.items():
                setattr(self._node_instance.props, name, value)
        elif "posX" in values or "posY" in values:
            self.move(float(values.get("posX", 0.0)), float(values.get("posY", 0.0)))

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
        with self._locked():
            # Notify graph of redraw request
            if self._graph and not self._is_dirty_structural and self.state.is_registered:
                # Set before the call: an inline scheduler validates inside it and clears the flag.
                self._is_dirty_structural = True
                try:
                    self._graph._validation.mark_node_dirty(
                        self._node_id, ChangeReason.NODE_VALIDATION_REQUESTED
                    )
                except BaseException:
                    self._is_dirty_structural = False
                    raise

    def mark_value_edited(self) -> None:
        """Mark that a user edited a value this node saves, so the graph becomes unsaved.

        Call it after a user's write to a port value or a setting. The node
        reports ``ChangeReason.NODE_VALUE_CHANGED`` and the graph
        ``ChangeReason.GRAPH_CONTENT_CHANGED``: nothing rebuilds, redraws or
        reassembles. The graph mark keeps the save when a redraw reason already
        held the node's slot (a label edit). It does nothing until the node is
        registered with the graph.
        """
        # No node lock: it guards no node state here, and held while waiting for
        # the graph's validation lock it would invert the lock order.
        graph = self._graph
        if graph and self.state.is_registered:
            graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_VALUE_CHANGED)
            graph._validation.mark_graph_dirty(ChangeReason.GRAPH_CONTENT_CHANGED)

    def redraw(self) -> None:
        """Request a redraw of the node in the UI."""
        # No node lock: held while waiting for the graph's validation lock, it deadlocks a batch.
        graph = self._graph
        if graph:
            graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_REDRAW_REQUESTED)

    def mark_layout_changed(self) -> None:
        """Mark the node's persisted arrangement dirty — its card rebuilds and the graph saves.

        Distinct from ``redraw()``, whose ``NODE_REDRAW_REQUESTED`` is
        visual-only and tells the app layer not to mark the file unsaved.
        """
        graph = self._graph
        if graph:
            graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_LAYOUT_CHANGED)

    def _subscribe_props_redraw(self) -> None:
        """Watch the instance's appearance-affecting props and redraw on change."""
        if self._node_instance is None:
            return

        for field_name in type(self._node_instance.props).REDRAW_FIELDS:
            self._node_instance.props._subscribe_field(field_name, self._on_props_redraw_change)

    def _on_props_redraw_change(self, _value: Any, _old: Any) -> None:
        """Cell-event adapter to request a debounced redraw."""
        self.redraw()

    def _subscribe_stage_membership(self) -> None:
        """Watch the instance's ``on_stage`` prop and report ``NODE_STAGE_CHANGED`` on change."""
        if self._node_instance is None:
            return

        self._node_instance.props._subscribe_field("on_stage", self._on_stage_membership_change)

    def _on_stage_membership_change(self, _value: Any, _old: Any) -> None:
        """Re-measure the stage canvas and mark the node dirty as ``NODE_STAGE_CHANGED``."""
        # No node lock: held while waiting for the graph's validation lock, it deadlocks a batch.
        graph = self._graph
        if graph is None or not self.state.is_registered:
            return
        graph._check_canvas_size(STAGE)
        graph._validation.mark_node_dirty(self._node_id, ChangeReason.NODE_STAGE_CHANGED)

    def request_graph_reassembly(self) -> None:
        """Ask the graph to regenerate the flow structure, rebuilding and redrawing nothing.

        Call it when a setting inside the node changed something the flow
        assembler reads. When the node's inlets or outlets changed instead, call
        ``mark_as_structuraly_dirty()``.
        """
        graph = self._graph
        if graph:
            graph._validation.mark_graph_dirty(ChangeReason.GRAPH_REQUIRE_REASSEMBLY)

    def _housekeeping(self) -> None:
        """Rebuild the node's port pipelines if it is structurally dirty.

        Called by graph validation or after deserialization, never from inside a
        node.
        """
        with self._locked():
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
        with self._locked():
            if self._node_instance:
                self._node_instance.on_saved()

            result: dict[str, Any] = {
                "node_id": self._node_id,
                "registry_key": self.registry_key,
            }

            if self.is_stand_in:
                # A stand-in saves the node it replaces, not itself; with no data there is nothing to save.
                if self._stand_in_data is not None:
                    result["node_data"] = self._stand_in_save_data(include_data=include_data)
            elif self._node_instance:
                result["node_data"] = self._node_instance._to_dict(include_data=include_data)

            return result

    def __repr__(self) -> str:
        return (
            f"NodeWrapper(id={self._node_id}, "
            f"registry_key={self.registry_key}, valid={self._state.is_valid()})"
        )
