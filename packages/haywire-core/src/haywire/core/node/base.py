from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional
from dataclasses import asdict
from abc import abstractmethod

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.node.properties import NodeProperties  # re-exported for type hints
from ..execution.execution_context import ExecutionContext
from .data import NodeData
from haywire.core.settings import Settings

if TYPE_CHECKING:
    from haywire.core.node import NodeWrapper

logger = logging.getLogger(__name__)


class BaseNode(NodeData):
    """
    Base class for all Haywire nodes.

    Combines NodeData (port management) with node lifecycle and execution.
    Subclasses must implement the worker() method for execution logic.

    The API for reading and writing port values inside worker():
    - value(id) - Get unwrapped value
    - out(id, value) - Set unwrapped value
    - No manual wrapping/unwrapping needed!

    Important: Nodes in modules that start with dev_*.py or end with *_dev.py are not
    automatically registered in the node registry. On a File change though they will
    be loaded and are available.
    This is useful for nodes under development that should not yet be part of the library.
    """

    if TYPE_CHECKING:
        # mypy view: instances expose `props` as a NodeProperties instance.
        # Without this hint mypy would see only the inner class (below) and
        # report attribute access as `field[T]` descriptors instead of T.
        props: NodeProperties
    else:

        class props(NodeProperties):
            """Per-instance observable props (muted, collapsed, skin, position, …).

            Inner-class form is the schema declaration discovered by the @node
            decorator's _wire_settings_schemas. At construction time NodeData.__init__
            replaces this on the instance with a NodeProperties instance.
            """

    def __init__(self, node_id: str, wrapper: "NodeWrapper"):
        """
        Initialize node.

        Args:
            node_id: Unique identifier for this node instance
            wrapper: NodeWrapper managing this node
        """
        super().__init__(node_id, wrapper)

    @abstractmethod
    def init(self):
        """
        Override this method in subclasses to
        Initialize Node to its default setup

        This method needs to be overwritten by every node and is
        called when the node is created or rebuilt. It should be only used to
        add ports and set default values.

        Only do operations in here that can also be deserialized from file. For
        any additional setup that cannot be done through deserialization,
        use the post_init() method.
        """
        pass

    def post_init(self) -> None:
        """
        Override this method in subclasses to implement custom
        setup logic right after initialization.

        It should be used to perform any additional setup that cannot be done
        through deserialization, such as instantiating classes.

        Do not use it for performative operations or as a preparation for the
        worker execution - the on_startup() method should be used for that purpose.

        This method is called right after
            - init() or
            - loading from file (_initialize_from_dict()).

        """
        pass

    def on_testrun(self) -> tuple[bool, str | None]:
        """
        Run node test. This test is executed when the node is added
        to the graph and can be used to verify that the node is set up
        correctly.

        Override this method in subclasses to implement node-specific tests.

        Returns:
            True if all tests pass, False otherwise
            Optional string with failure reason if tests fail
        """
        return True, None

    def on_validate(self, context: ExecutionContext) -> None:
        """
        Override this method in subclasses to implement custom input validation.
        Handle validation of inputs before execution.

        This method is called right before the worker is executed and
        can be used to validate input values: to check for valid ranges, types,
        or other constraints on input data.

        TODO: what shall we do on validation failure? Raise exception?
        """
        pass

    def on_startup(self, context: ExecutionContext) -> None:
        """
        Perform any startup logic when the node is executing for the first time.
        It is called once before the first execution of the worker.

        Override this method in subclasses to implement custom startup logic.
        """
        pass

    def on_frame_start(self, context: ExecutionContext) -> None:
        """
        Perform any logic needed at the start of each frame.

        This method is called at the beginning of each frame before
        any nodes are executed. It can be used to reset state or
        prepare for the frame's execution.

        Override this method in subclasses to implement custom frame-start logic.
        """
        pass

    def _execute(self, context: "ExecutionContext") -> Optional[str]:
        """
        Execute the worker with optimized value extraction.

        This is the single entry point

        Args:
            context: Execution context

        Returns:
            Outlet ID to follow, or None
        """
        # Data nodes skip execution entirely if nothing changed
        if self.behavior.is_data_node:
            if not self._has_dirty_ports:
                return None

        # Resolve dirty data for ALL node types (lazy pulls + deferred on_change)
        while self._has_dirty_ports:
            _port_id, port = self._has_dirty_ports.popitem()
            port.resolve_dirty_data()

        self.on_validate(context)

        if self._executor is None:
            self._executor = self._analyze_worker_signature()

        result = self._executor(context)

        parsed = self._parse_worker_result(result)

        return parsed

    @abstractmethod
    def worker(self, context: ExecutionContext, *args, **kwargs) -> str | None:
        """
        The main execution logic of the node.

        Override this method in subclasses to implement node behavior.

        Worker signature design:
        - Parameter names must match inlet port IDs
        - Parameters are automatically extracted and passed as unwrapped values
        - Use type hints to document expected types
        - Use default values for optional ports (if port doesn't exist, default used)
        - Required parameters (no default) must have matching ports or ValueError raised

        Args:
            context: Execution context (always first parameter)
            *args: Named parameters matching inlet port IDs (auto-extracted)
            **kwargs: Named parameters matching inlet port IDs (auto-extracted)

        Returns:
            - None  # for data flow nodes
            - 'next'  # for control flow nodes

        Examples:
            Simple node with required inputs:

            .. code-block:: python

                def worker(self, context: ExecutionContext, value: float, multiplier: float):
                    self.out('result', value * multiplier)

            Node with optional inputs (default if port missing):

            .. code-block:: python

                def worker(self, context: ExecutionContext, value: float, offset: float = 0.0):
                    self.out('result', value + offset)

            Control flow node:

            .. code-block:: python

                def worker(self, context: ExecutionContext, condition: bool):
                    return 'true_branch' if condition else 'false_branch'

            Multi-output with control flow:

            .. code-block:: python

                def worker(self, context: ExecutionContext, x: float, y: float):
                    self.out('sum', x + y)
                    self.out('product', x * y)
                    self.out('difference', x - y)
                    return 'next'
        """
        pass

    def on_frame_end(self, context: ExecutionContext) -> None:
        """
        Perform any logic needed at the end of each frame.

        This method is called at the end of each frame after
        all nodes have been executed. It can be used to finalize
        state or perform cleanup for the frame.

        Override this method in subclasses to implement custom frame-end logic.
        """
        pass

    def on_shutdown(self, context: ExecutionContext) -> None:
        """
        Perform any shutdown logic when the graph stops executing.

        Override this method in subclasses to implement custom shutdown logic.
        """
        pass

    def on_saved(self) -> None:
        """
        Handle any logic needed when the graph is saved.

        This method is called whenever the graph is saved to disk.
        It can be used to perform any necessary cleanup or state updates
        before serialization.

        Override this method in subclasses to implement custom save handling.
        """
        pass

    def on_teardown(self) -> None:
        """
        Clean up resources when node is destroyed.

        Override this method in subclasses to implement custom cleanup logic.
        This is called when the node is removed from the graph and should
        release any resources held by the node.
        """
        pass

    def _cleanup(self) -> None:
        """Clean up resources when node is destroyed."""
        # A subclass on_teardown() must never block the rest of cleanup or a
        # subsequent re-instantiation. This matters most when a prior init()
        # failed (e.g. a missing type after a deserialized graph references a
        # since-removed type key): post_init() never ran, so teardown may hit
        # unset attributes. Isolate it so the store/settings cleanup below still
        # runs and the node can be re-instantiated.
        try:
            self.on_teardown()
        except Exception as e:
            error = HaywireException.from_exception(
                exception=e,
                operation="on_teardown()",
                message=f"on_teardown() raised for node '{self.class_identity.registry_key}'",
                registry_key=self.class_identity.registry_key,
            ).enrich(
                node_id=self.node_id,
                module_name=self.class_library.module_name,
                class_name=self.class_identity.class_name,
                library_identity=self.class_library,
            )
            error.log(logger)
        self._store.clear()
        # Clean up settings bags (release global namespace subscriptions)
        for bag_name in type(self)._settings_bags:
            bag = getattr(self, bag_name, None)
            if isinstance(bag, Settings):
                bag.cleanup()

    # =========================================================================
    # SERIALIZATION (updated)
    # =========================================================================

    def _to_dict(self, include_data: bool = True) -> dict:
        """
        Serialize node to dictionary.
        This also includes identity and library info.

        Args:
            include_data: If True, includes field values

        Returns:
            Dict representation of the node
        """
        return {
            "node_id": self.node_id,
            "ports": self._serialize_ports(include_data=include_data),
            "settings": {name: getattr(self, name).to_dict() for name in type(self)._settings_bags},
            "props": self.props.to_dict(),
            "store": self._store.to_dict(),
            "identity": asdict(self.identity),
            "library": asdict(self.library),
        }

    def _initialize_from_dict(self, data: dict) -> None:
        """
        Load node state from dictionary.

        Restores all node state from the serialized format produced by
        to_dict(), including dataclass fields and ports. The node instance
        must already be created with the correct class type.

        This is typically called by NodeWrapper or Graph after creating
        the node instance via NodeFactory.

        Strategy:
        - Only restores fields that exist in the dataclass definition
        - Silently ignores unknown fields (forward compatibility)
        - Missing fields keep their default values (backward compatibility)

        Note on extensibility:
        - Don't add dynamic attributes to dataclass instances - use custom dict

        Args:
            data: Serialized node data (from to_dict())

        Raises:
            ValueError: If data is invalid or ports fail to deserialize

        Example:
            # Create and load node
            node_cls, error = node_factory.get_node(registry_key)
            node = node_cls(node_id, wrapper)
            node.initialize_from_dict(saved_data)

            # User-defined data in metadata.custom IS preserved:
            node.metadata.custom['my_plugin'] = {'version': '1.0', 'data': [...]}
            # After save/load cycle, this data will be fully restored!
        """
        # Restore settings bags FIRST: regenerate_promoted_ports() below recreates
        # each promoted port and binds its cell by reference, so the cell must
        # already hold its loaded value before the port subscribes to it (an
        # outlet's on_changed → propagate must not fire mid-load through a
        # half-built graph). Settings restore mutates each cell in place (and
        # restores each bag's _promoted_keys), so regenerating a port afterwards
        # sees the restored value with no load-time propagation.
        from haywire.core.settings.settings import PromotedFormatError

        for bag_name, bag_data in data.get("settings", {}).items():
            bag = getattr(self, bag_name, None)
            if not isinstance(bag, Settings):
                continue
            try:
                bag.from_dict(bag_data)
            except PromotedFormatError:
                # Reset-and-continue: the bag stays at descriptor
                # defaults (nothing restored), the node loads and stays fully
                # functional, and the user is told via a WARNING that renders on
                # the node card. They lose this node's individually-saved
                # settings.
                logger.warning(
                    "Node %r bag %r: incompatible settings format; reset to defaults.",
                    self.node_id,
                    bag_name,
                )
                self.wrapper.state.error_custom = HaywireException.create(
                    f"Settings for '{bag_name}' were saved in an old format and have "
                    f"been reset to defaults. Re-save the graph to update it.",
                    severity=ErrorSeverity.WARNING,
                )

        # Deserialize the NON-promoted ports (promoted ports are not in the
        # ports block). Then regenerate promoted ports from
        # the already-restored settings bags. This runs before edges wire
        # (two-phase graph load), so a regenerated promoted inlet exists before
        # any edge resolves against it.
        if "ports" in data:
            self._deserialize_ports(data["ports"])

        self._regenerate_promoted_ports()

        # Restore reactive props
        if "props" in data:
            self.props.from_dict(data["props"])

        if "store" in data:
            self._store.from_dict(data["store"])
