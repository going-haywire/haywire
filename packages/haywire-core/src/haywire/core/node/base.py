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
    """Base class for all Haywire nodes: ports, lifecycle and execution.

    Declare ports in `init()` and do the work in `worker()`. Inside `worker()`,
    read a port with `value(id)` and write one with `out(id, value)`; both take
    and return plain values, with no wrapping of your own.

    A node in a module named `dev_*.py` or `*_dev.py` is not registered in the
    node registry automatically, but is still loaded and usable after a file
    change — useful while a node is under development.
    """

    if TYPE_CHECKING:
        # mypy view: instances expose `props` as a NodeProperties instance; without
        # this hint mypy sees only the inner class and types access as `field[T]`.
        props: NodeProperties
    else:

        class props(NodeProperties):
            """Per-instance observable props (collapsed, locked, skin, position, …).

            Replaced on each instance by a ``NodeProperties`` instance at
            construction, so ``self.props`` is never this class.
            """

    def __init__(self, node_id: str, wrapper: "NodeWrapper"):
        """Initialize the node."""
        super().__init__(node_id, wrapper)

    @property
    def display_label(self) -> str:
        """The name this node goes by — its own label, else its class's."""
        return self.props.label.strip() or self.identity.label

    @abstractmethod
    def init(self):
        """Bring the node to its default setup: add ports and set default values.

        Called when the node is created or rebuilt. Restrict it to work that
        loading a saved graph can reproduce; anything else belongs in
        ``post_init()``.
        """
        pass

    def post_init(self) -> None:
        """Complete the setup that loading a saved graph cannot reproduce, such as
        instantiating helper objects.

        Called right after ``init()``, or right after the node is loaded from
        file. Work that prepares a worker run belongs in ``on_startup()``.
        """
        pass

    def on_testrun(self) -> tuple[bool, str | None]:
        """Verify that the node is set up correctly. Run when the node is added to the graph.

        Returns:
            ``(True, None)`` when the node passes, otherwise ``(False, reason)``
            with a message shown on the node card.
        """
        return True, None

    def on_validate(self, context: ExecutionContext) -> None:
        """Validate inlet values — ranges, types, or any other constraint.

        Called right before each worker execution.

        TODO: what shall we do on validation failure? Raise exception?
        """
        pass

    def on_startup(self, context: ExecutionContext) -> None:
        """Prepare the node for execution. Called once, before its first worker run."""
        pass

    def on_frame_start(self, context: ExecutionContext) -> None:
        """Run at the start of each frame, before any node in it executes."""
        pass

    def _execute(self, context: "ExecutionContext") -> Optional[str]:
        """Run the worker and return the outlet ID to follow, or ``None``.

        Resolves every dirty port and calls ``on_validate()`` first. A data node
        with no dirty port returns ``None`` without running its worker.
        """
        if self.behavior.is_data_node:
            if not self._has_dirty_ports:
                return None

        # Every node type resolves dirty data here: lazy pulls and deferred on_change.
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
        """The node's execution logic. Every concrete node overrides it.

        Each parameter after ``context`` is named for an inlet port, and that
        port's unwrapped value is passed in. A parameter with a default is
        optional: the default applies when no port of that name exists. A
        required parameter with no matching port raises ``ValueError`` when the
        signature is analyzed.

        Args:
            context: Execution context; always the first parameter.
            *args: Values of the inlet ports named in the signature.
            **kwargs: Values of the inlet ports named in the signature.

        Returns:
            ``None`` for a data-flow node, or the ID of the outlet to follow
            for a control-flow node.

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
        """Run at the end of each frame, after every node in it has executed."""
        pass

    def on_shutdown(self, context: ExecutionContext) -> None:
        """Run when the graph stops executing."""
        pass

    def on_saved(self) -> None:
        """Run whenever the graph is saved to disk, before the node is serialized."""
        pass

    def on_teardown(self) -> None:
        """Release any resources this node holds. Called when it is removed from the graph."""
        pass

    def _cleanup(self) -> None:
        """Clean up resources when node is destroyed."""
        # Isolated so a raising on_teardown() cannot block the store/settings
        # cleanup below, or the node could not be re-instantiated. After a failed
        # init() post_init() never ran, so teardown may hit unset attributes.
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
                bag._cleanup()

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def _to_dict(self, include_data: bool = True) -> dict:
        """Serialize the node, including its identity and library info.

        Args:
            include_data: When True, port field values are included.
        """
        return {
            "node_id": self.node_id,
            "ports": self._serialize_ports(include_data=include_data),
            "settings": {name: getattr(self, name)._to_dict() for name in type(self)._settings_bags},
            "props": self.props._to_dict(),
            "store": self._store.to_dict(),
            "identity": asdict(self.identity),
            "library": asdict(self.library),
        }

    def _initialize_from_dict(self, data: dict) -> None:
        """Restore the node's settings, ports, props and store from a ``_to_dict()`` dict.

        The instance must already exist, built from the matching class. Unknown
        keys are ignored and absent ones keep their defaults. A settings bag
        saved in an incompatible format is reset to its declared defaults and a
        warning is attached to the wrapper state instead of raising, so the node
        still loads (see ADR 0019).

        Args:
            data: Serialized node data.

        Raises:
            ValueError: If a serialized port names a type the registry cannot
                resolve.

        Example::

            node_cls, error = node_factory.get_node(registry_key)
            node = node_cls(node_id, wrapper)
            node._initialize_from_dict(saved_data)
        """
        # Settings first: _regenerate_promoted_ports() below binds each promoted
        # port to its bag cell by reference, so the cell must already hold the
        # loaded value — otherwise an outlet's on_changed → propagate fires
        # mid-load through a half-built graph.
        from haywire.core.settings.settings import PromotedFormatError

        for bag_name, bag_data in data.get("settings", {}).items():
            bag = getattr(self, bag_name, None)
            if not isinstance(bag, Settings):
                continue
            try:
                bag._from_dict(bag_data)
            except PromotedFormatError:
                # Reset-and-continue: the bag stays at descriptor defaults and the
                # node loads fully functional; the user loses this node's saved
                # settings and is told by the warning below.
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

        # Promoted ports are absent from the "ports" block; they are regenerated
        # from the restored bags below. Both run before edges wire (two-phase
        # graph load), so a promoted inlet exists before any edge resolves to it.
        if "ports" in data:
            self._deserialize_ports(data["ports"])

        self._regenerate_promoted_ports()

        if "props" in data:
            self.props._from_dict(data["props"])

        if "store" in data:
            self._store.from_dict(data["store"])
