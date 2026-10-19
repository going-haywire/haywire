"""
DataPort Class - Unified port for inlets and outlets.

This module provides the DataPort class that integrates with the DataField hierarchy.
Direction is determined by the is_inlet field (True for inlet, False for outlet).
"""

from __future__ import annotations
import logging
import threading
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Callable, Dict, Optional, TYPE_CHECKING

from haywire.core.types.enums import PortOrigin, PortType, ShowWidgetStrategy, StoreStrategy
from haywire.core.edge.edge_wrapper import EdgeWrapper
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.types.identity import DataTypeIdentity
from haywire.core.types.interface import IType
from haywire.core.types.wire import WILDCARD, WireRole, WireType, wire_type_of
from haywire.core.types.utils import serialize_element_type

# Import the new DataField classes
from haywire.core.types.fields import DataField
from haywire.core.types.link_set import LinkSet
from haywire.core.types.pipe import Pipe, Pipes

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.types.registry import TypeRegistry
    from haywire.core.node import NodeData


def _same_value(a: Any, b: Any) -> bool:
    """True if *a* and *b* are one object or compare equal; a failing or ambiguous comparison is False."""
    if a is b:
        return True
    try:
        return bool(a == b)
    except Exception:
        return False


logger = logging.getLogger(__name__)

# ids of the immediate inlets whose on_change is running on this thread; see DataPort._fire_immediate.
_immediate_fires = threading.local()


def _firing_inlets() -> set[int]:
    """Return the ``id()`` of every immediate inlet whose ``on_change`` is running on this thread."""
    firing = getattr(_immediate_fires, "inlets", None)
    if firing is None:
        firing = _immediate_fires.inlets = set()
    return firing


@dataclass
class DataPort(DataTypeIdentity):
    """
    Unified port for both inlets and outlets; direction is set by ``port_type``.
    """

    # Port identifier within node (different from registry_id!)
    id: str = ""

    port_type: PortType = PortType.UNDEFINED

    # Runtime data field (created by type in __post_init__)
    _data: DataField = field(init=False, repr=False, metadata={"serialize": False})
    """DataField instance storing port data (set in __post_init__)"""

    _is_inlet: bool = field(init=False, repr=False, metadata={"serialize": False})
    """Cached ``port_type == INLET``; lets the set_value hot path branch on an
    attribute read instead of an ``is_inlet()`` method call. Re-type a port
    through ``adopt_port_type()``, the one path that refreshes this."""

    _is_immediate: bool = field(init=False, repr=False, metadata={"serialize": False})
    """Cached: the wire type's role is ``IMMEDIATE``, so the set_value hot path branches on an
    attribute read. Refreshed by ``_derive_wire()``."""

    # Type tracking
    type_cls: type[IType] | None = field(default=None, metadata={"serialize": False})
    """The type class (FLOAT, ArrayType, etc.)"""

    wire_type: type[WireType] | None = field(
        default=None, init=False, repr=False, compare=False, metadata={"serialize": False}
    )
    """The wire type this port's values travel on, derived from ``type_cls``. ``None`` for
    a config port, a fold, a bare ``ADD`` slot and a type that declares none. Read-only:
    set by ``_derive_wire``."""

    # Edge state: one set per end of an edge
    incoming: LinkSet = field(init=False, repr=False, compare=False, metadata={"serialize": False})
    """The edges ending at this port. Filled for an inlet or a swinglet."""

    outgoing: LinkSet = field(init=False, repr=False, compare=False, metadata={"serialize": False})
    """The edges leaving this port. Filled for an outlet or a swinglet."""

    # Outlet-specific
    _pipes: Optional[Pipes] = field(default=None, repr=False, metadata={"serialize": False})

    single_link: bool = False
    """Narrow this port to one link where its link ceiling allows many; see ``takes_many_links``.

    Read when an edge links, so setting it removes no edge the port already holds: the next link
    leaves only itself linked.
    """

    # Inlet-specific
    use_mode: str = "optional"

    # Internal: Store default override for field creation
    default: Optional[Dict[str, Any]] = field(default=None, repr=False)

    def __hash__(self) -> int:
        """Hash by port id so DataPort can be used in sets."""
        return hash(self.id)

    def is_config(self) -> bool:
        """True for a config port, False for anything else."""
        return self.port_type == PortType.CONFIG

    def is_outlet(self) -> bool:
        """True if this port can be an edge's outlet end: an outlet or a swinglet."""
        return self.port_type in (PortType.OUTLET, PortType.SWINGLET)

    def is_inlet(self) -> bool:
        """True if this port can be an edge's inlet end: an inlet or a swinglet."""
        return self.port_type in (PortType.INLET, PortType.SWINGLET)

    def is_swinglet(self) -> bool:
        """True for a swinglet, which may be either end of an edge."""
        return self.port_type == PortType.SWINGLET

    def adopt_port_type(self, port_type: PortType) -> None:
        """Set this port's direction, refreshing the caches derived from it.

        The only supported re-typing: a fold takes the direction of the ports
        it holds once its block closes (``NodeData.fold``). Assigning
        ``port_type`` directly instead leaves ``_is_inlet`` stale, and
        ``set_value`` reads that cache rather than ``is_inlet()``.
        """
        self.port_type = port_type
        self._is_inlet = port_type in (PortType.INLET, PortType.SWINGLET)

    @property
    def promoted(self) -> bool:
        """True for a port promoted from a setting (``origin is PROMOTED``).

        Decides value ownership, not just provenance: a promoted port borrows
        the setting's cell, so it does not serialize its own value and its
        widget is bound through the descriptor.
        """
        return self.origin is PortOrigin.PROMOTED

    @promoted.setter
    def promoted(self, value: bool) -> None:
        self.origin = PortOrigin.PROMOTED if value else PortOrigin.DECLARED

    def is_user_removable(self) -> bool:
        """Whether the user may delete this port from the pin context menu.

        True for a port the user brought into being — promoted from a setting,
        or resolved from an ``ADD`` pin — and False for one the node's
        author declared.
        """
        return self.origin is not PortOrigin.DECLARED

    # ========================================================================
    # HIERARCHY & ORGANIZATION
    # ========================================================================

    parent_fold: Optional[str] = None
    """ID of parent group port, None if top-level"""

    order: int = 0
    """Display order within parent"""

    is_fold: bool = False
    """True if this port is a fold container.

    A fold takes the ``port_type`` of the children it holds, so that it renders
    in their lane. It draws no pin of its own — see ``has_pin()``.
    """

    needs_loopback: bool = False
    """Set to True if the control flow from this outlet needs to loop back to the node"""

    origin: PortOrigin = PortOrigin.DECLARED
    """Where this port came from, and so whether the user may remove it."""

    is_linked_lazy: bool = False
    """Lock every linked edge to lazy propagation; see ``EdgeWrapper.locked_propagation``."""

    _is_dirty_structural: bool = False
    """Internal flag to track if port link has structurally changed"""

    _is_set_by_node: bool = field(default=False, metadata={"serialize": False})
    """Internal flag to indicate if the value was set via the node"""

    _pending_lazy_pipes: set = field(default_factory=set, metadata={"serialize": False})
    """Tracks Pipe objects needing lazy resolution at execution time."""

    # ========================================================================
    # CALLBACKS
    # ========================================================================

    on_change: Optional[str] = None
    """Callback identifier to invoke when port value changes (e.g., 'reconfigure_ports')"""

    on_connect: Optional[str] = None
    """Callback identifier to invoke when connection is made"""

    on_disconnect: Optional[str] = None
    """Callback identifier to invoke when connection is broken"""

    widget: dict[str, Any] | None = field(default=None, repr=False, metadata={"serialize": False})
    """transient input only field. do not use other then in port creation"""

    widget_key: str | None = field(default=None)
    """Resolved widget key (set from widget["key"] in __post_init__)"""

    widget_config: dict[str, Any] = field(default_factory=dict)
    """Widget configuration dict (merged from widget["config"] in __post_init__)"""

    show_widget: ShowWidgetStrategy = ShowWidgetStrategy.NOT_LINKED
    """When the inline widget is rendered relative to link state. Per-direction
    defaults (inlet NOT_LINKED, outlet NEVER, config ALWAYS) are injected by
    as_inlet/as_outlet/as_config; override per-port via kwargs."""

    operable: bool = True
    """Whether operating this port's widget on a node card may change its value.
    ``False`` makes every write to it need level mode ``edit``."""

    # Runtime reference (not serialized)
    _wrapper: Optional["NodeWrapper"] = field(default=None, repr=False, metadata={"serialize": False})

    _node: Optional["NodeData"] = field(default=None, repr=False, metadata={"serialize": False})
    """Reference to parent node (for callbacks)"""

    def __post_init__(self):
        """
        Create data field via type.
        """
        # Skip parent's post_init for runtime ports

        if self.widget:
            if not isinstance(self.widget, dict):
                raise ValueError(
                    f"Attribute 'widget' is of type: {type(self.widget).__name__}, "
                    f"but must be a dict with 'key' and optional 'config' fields. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )
            # Parse new widget dict format: {'key': '...', 'config': {...}}
            if "key" not in self.widget:
                raise ValueError(
                    "Attribute 'widget' is a dict and must contain the 'key' field. "
                    "Use WidgetClass.config(**kwargs) to generate correct format."
                )

            # Extract widget key and merge config into widget_config dict
            widget_key = self.widget["key"]
            widget_config = self.widget.get("config", {})

            # Merge widget config into widget_config dict (widget config takes precedence)
            self.widget_config = {**self.widget_config, **widget_config}
            self.widget_key = widget_key

            self.widget = None

        # A live callable in widget_config (e.g. {"options": self.method} for a
        # dynamic dropdown) is intentional and works at render time, but it
        # cannot survive JSON serialization. A promoted port never serializes
        # its widget_config (it round-trips through the descriptor), so a
        # callable there is always safe. A plain port IS its own only copy,
        # so a callable would crash json.dumps at save time. Fail here instead —
        # at construction (node.add during init()), naming the port and key.
        # Reuses the same serializability check normalize_and_validate_default
        # uses for default= values.
        if not self.promoted and self.widget_config:
            from haywire.core.types.utils import is_cattrs_serializable

            ok, error_msg = is_cattrs_serializable(self.widget_config)
            if not ok:
                raise TypeError(
                    f"DataPort {self.id!r}: 'widget_config' must be JSON serializable. "
                    f"Got {self.widget_config!r} which is not serializable: {error_msg}\n"
                    f"A live callable in widget_config (e.g. a dynamic-options method) is "
                    f"only safe on a setting() field promoted to a port — the descriptor is "
                    f"re-applied fresh on every load, so the callable is never serialized. "
                    f"A plain (non-promoted) port has no such fallback: use a literal value, "
                    f"or move this field into a Settings bag and promote it."
                )

        # Create data field — DataPort always needs a type_cls to be functional.
        if self.type_cls is None:
            raise ValueError(
                f"DataPort '{self.id}' constructed without type_cls. "
                f"DataPort instances must be created via from_spec()."
            )
        self._data = self.type_cls.create_field(default_override=self.default)
        self.incoming = LinkSet(self, is_incoming=True)
        self.outgoing = LinkSet(self, is_incoming=False)
        # Cache the immutable inlet/outlet role for the set_value hot path.
        self._is_inlet = self.port_type in (PortType.INLET, PortType.SWINGLET)
        self._derive_wire()

    # ========================================================================
    # CALLBACK TRIGGERING
    # ========================================================================

    def _trigger_callback(self, callback_name: str | None, *args):
        """
        Invoke a node callback by name.

        ``callback_name`` is the node method name held by one of this port's
        callback attributes (``on_change`` / ``on_connect`` / ``on_disconnect``).
        Callers pass the attribute value directly — they have already read and
        truthiness-checked it — so this method does not re-resolve it.

        Examples:
            self._trigger_callback(self.on_change, old, new)
            # → node.<on_change>(port, old, new)
        """
        if not callback_name or not self._wrapper or self._wrapper.is_cleaned_up:
            # A graph's teardown detaches edges after cleaning up their nodes; there is nothing to call.
            return

        node = self._wrapper.node
        if hasattr(node, callback_name):
            method = getattr(node, callback_name)
            method(self, *args)
        else:
            raise ReferenceError(f"Node callback '{callback_name}' not found on node")

    # ========================================================================
    # VALUE MANAGEMENT
    # ========================================================================

    @property
    def data(self) -> DataField:
        """The port's underlying ``DataField`` (typed storage + ``on_changed``).

        Public accessor for the field; compound fields expose shape-specific
        helpers (``get_values_list()``, ``get_source_ids()``, ``get_item()``).
        """
        return self._data

    @property
    def stored_type(self) -> type[IType]:
        """The ``IType`` actually stored by this port's field (see ``DataField.get_stored_type``)."""
        return self._data.get_stored_type()

    def get_value(self) -> Any:
        """
        Get unwrapped value for worker convenience.

        Returns:
            - For PrimitiveField: Unwrapped primitive (42.0)
            - For BaseField: BaseType instance (MeshData(...))
            - For CompoundField: Container (dict, list, etc.)
            - None if no data
        """
        if self._data is None:
            return None

        return self._data.get_value()

    def set_value(self, new_value: Any, edge_id: str | None = None) -> None:
        """
        Set port value. Single entry point for all value updates.

        ``on_change`` reports only what the port receives: an edge's write or a
        widget or programmatic write. ``out()`` and ``_emit`` never fire it,
        ``as_outlet`` refuses an ``on_change``, and no port built with
        ``as_outlet`` carries one. A fold wrapping outlets may carry one, and
        its own write through ``set_value`` fires it.

        For inlets and swinglets:
        - an edge's write to an immediate port goes through ``_fire_immediate``
        - an own write (no edge_id) while an edge feeds the port changes only
          the own value: no on_change, no dirty mark
        - any other own write fires on_change immediately
        - any other edge's write defers to resolve_dirty_data()
        - an edge's write is stored as the linked value and stops there; it
          leaves the node-set mark as it is

        For config ports:
        - Fire on_change immediately

        For outlets:
        - Store the value, then propagate to downstream inlets

        A swinglet's own write through ``out()`` goes to ``_emit`` instead, which
        passes it on to the edges at the swinglet's outlet end.

        Args:
            new_value: Value to set (can be IType instance or raw value)
            edge_id: Source identifier (set when value comes via Pipe.pull())
        """
        if self._data is None:
            return

        # _is_immediate first: on a data or control port the hot path pays one attribute read.
        if self._is_immediate and self._is_inlet and edge_id is not None:
            self._fire_immediate(lambda: self._data.set_value(new_value, source_id=edge_id), new_value)
            return

        self._data.set_value(new_value, source_id=edge_id)

        if self._is_inlet:
            if edge_id is None:
                # An own write is a widget or programmatic set, never the node's, so
                # it clears the node-set flag; an edge's write leaves it.
                self._is_set_by_node = False
                if self._data.has_linked_value():
                    # The own value changed behind the linked one; the node sees no change.
                    return
                if self.on_change is not None:
                    # Widget/programmatic change → fire on_change immediately
                    self._trigger_callback(self.on_change, new_value)
                    return
            # Edge-driven OR no callback → defer to resolve_dirty_data()
            self._mark_as_data_dirty()
        else:
            # Configs, and a fold wrapping outlets, report their write.
            if self.on_change is not None:
                self._trigger_callback(self.on_change, new_value)
            self._after_node_write()

    def _emit(self, new_value: Any) -> None:
        """Store the node's own write and run the pipes: the outlet half of ``set_value``.

        Stores the own value, marks the port node-set and propagates to the edges
        leaving it. Fires no ``on_change``: that reports only what the port receives.
        """
        if self._data is None:
            return
        self._data.set_value(new_value)
        self._after_node_write()

    def _after_node_write(self) -> None:
        """Mark the port node-set and run its pipes, the tail shared by outlet writes."""
        self._is_set_by_node = True
        if self._pipes is not None:
            self._pipes.propagate()

    def get_own_value(self) -> Any:
        """Get the node's own value, ignoring a linked value that stands in front of it.

        A pipe reads this from its source port. For an outlet it equals ``get_value()``.

        Returns:
            The own value, or None without a field.
        """
        if self._data is None:
            return None
        return self._data.get_own_value()

    def _fire_immediate(self, store: Callable[[], None], value: Any) -> None:
        """Store a write to this immediate inlet and tell the node only when what it sees changed.

        *store* writes the field; ``on_change`` receives *value*. Nothing fires when
        ``get_value()`` is the same before and after the store. A write that reaches
        this inlet while its own ``on_change`` is still running on this thread closes
        a loop of immediate edges: it is dropped without being stored and logged as a
        warning. Without ``on_change``, a change marks the port data-dirty.
        """
        firing = _firing_inlets()
        key = id(self)
        if key in firing:
            node_id = self._wrapper.node_id if self._wrapper is not None else "?"
            logger.warning(
                "Dropped a write to immediate inlet %r of node %s: it closes a loop of immediate edges",
                self.id,
                node_id,
            )
            return
        before = self._data.get_value()
        store()
        if _same_value(before, self._data.get_value()):
            return
        if self.on_change is None:
            self._mark_as_data_dirty()
            return
        firing.add(key)
        try:
            self._trigger_callback(self.on_change, value)
        finally:
            firing.discard(key)

    # ========================================================================
    # FIELD BINDING (promotion — one cell, two views)
    # ========================================================================

    def bind_field(self, field: DataField) -> None:
        """Share *field* as this port's ``_data`` by reference (promotion spine).

        A promoted port does not own a value — it becomes a second view of the
        setting's P4 ``DataField`` cell, so a write on either side is seen by both.

        On an OUTLET this also subscribes ``field.on_changed →
        self._on_shared_field_changed`` so that when anything writes the shared
        cell (widget edit, or a registry sync) the port propagates its own pipes.
        This is the *trigger* half of the freshness mechanism: the
        ``is_linked_lazy`` flag alone is inert — a lazy pipe only pulls once its
        sink is marked dirty via ``propagate()``.
        """
        self._data = field
        if self.is_outlet():
            field.on_changed.append(self._on_shared_field_changed)

    def unbind_field(self) -> None:
        """Release the shared cell reference and recreate a private field.

        Called by demote and by port cleanup (symmetric lifecycle). Removes
        the outlet's ``on_changed`` subscription (no dangling handler on the
        shared cell), then rebuilds a fresh field from ``type_cls`` so the
        port is self-owned again — the new field starts at ``type_cls``'s
        default, not the value the shared cell held.
        """
        assert self.type_cls is not None  # __post_init__ enforces this
        if self.is_outlet() and self._data is not None:
            self._data.on_changed.remove(self._on_shared_field_changed)
        self._data = self.type_cls.create_field(default_override=self.default)

    def _on_shared_field_changed(self, _value: Any) -> None:
        """Propagate this outlet's pipes when its shared cell changes.

        Lazy edges (locked by ``is_linked_lazy``) just queue the sink pipe + mark
        it dirty; the consumer pulls the fresh value on its next execution frame.
        No-op when the outlet has no pipes (unlinked)."""
        if self._pipes is not None:
            self._pipes.propagate()

    # ========================================================================
    # Lazy Propagation
    # ========================================================================

    def resolve_dirty_data(self) -> None:
        """
        Resolve dirty data: pull lazy pipes, then fire deferred on_change.

        Called at the start of node execution, before on_validate and worker.
        """
        # 1. Pull data from lazy pipes
        while self._pending_lazy_pipes:
            pipe = self._pending_lazy_pipes.pop()
            pipe.pull()

        # 2. Fire deferred on_change (covers both eager pushes and lazy pulls)
        if self.on_change is not None:
            self._trigger_callback(self.on_change, self.get_value())

    def _mark_as_data_dirty(self, pipe: "Pipe | None" = None) -> None:
        """
        Mark the port as data dirty and inform the node.

        Args:
            pipe: Pipe instance for lazy pull (only set for lazy edges)
        """
        if self._node:
            if pipe is not None:
                self._pending_lazy_pipes.add(pipe)
            self._node.mark_port_as_dirty(self)

    # ========================================================================
    # LINK MANAGEMENT
    # ========================================================================

    def is_linked(self) -> bool:
        """Check if port has any linked edges, at either end."""
        return bool(self.incoming.linked) or bool(self.outgoing.linked)

    def should_show_widget(self) -> bool:
        """
        Resolve whether this port's inline widget should be rendered, given its
        ``show_widget`` strategy and current link state.

        Note: this does NOT check ``widget_key`` — a caller must still confirm the
        port has a widget to render. It answers only the strategy-vs-link question.
        """
        strategy = self.show_widget
        if strategy == ShowWidgetStrategy.ALWAYS:
            return True
        if strategy == ShowWidgetStrategy.NEVER:
            return False
        # An outlet's widget follows its outgoing edges; an inlet's or swinglet's, its incoming ones.
        linked = bool(self.outgoing.linked if self.port_type is PortType.OUTLET else self.incoming.linked)
        if strategy == ShowWidgetStrategy.WHEN_LINKED:
            return linked
        # NOT_LINKED
        return not linked

    def set_show_widget(self, strategy: ShowWidgetStrategy) -> None:
        """Set this port's widget-visibility strategy at runtime.

        ADR 0003 makes ``show_widget`` an *authoring* decision, injected per
        direction and overridable through the ``as_*`` factories. This is the
        one runtime write path, and it exists for **promoted** ports only:
        a promoted port has no author behind its strategy (``promote_setting``
        applies a blanket per-direction default), so the user who created it
        owns that choice. The pin menu is its only caller; nothing calls this
        on an author-declared port.

        Callers are responsible for redrawing — the strategy is read at render
        time by ``should_show_widget()``, so a card already on screen keeps its
        old rendering until the node is redrawn.
        """
        self.show_widget = strategy

    def set_widget_config(self, key: str, value: Any) -> bool:
        """Set one property of this port's widget config, e.g. a slider's ``max``.

        The node's card is redrawn when the property changed, and its widgets are
        built again from the new config. Live reconfiguration of a drawn widget is
        not part of this method yet.

        Args:
            key: The widget property, one the port's widget documents (``"max"``).
            value: The new value; ``None`` removes the property, so the widget
                falls back to its own default.

        Returns:
            Whether the config changed. An unchanged value redraws nothing.

        Example::

            self.ports["value"].set_widget_config("max", 10.0)   # the slider ends at 10
            self.ports["value"].set_widget_config("min", None)   # no lower bound
        """
        current = self.widget_config.get("properties", {})
        if value is None:
            if key not in current:
                return False
        elif key in current and current[key] == value:
            return False
        # A copy: the declaration's properties dict may be shared with other ports.
        properties = {k: v for k, v in current.items() if k != key}
        if value is not None:
            properties[key] = value
        self.widget_config = {**self.widget_config, "properties": properties}
        if self._wrapper is not None:
            self._wrapper.redraw()
        return True

    @classmethod
    def _refreshable_fields(cls) -> tuple[str, ...]:
        """The field names ``refresh_from`` copies, computed once per class."""
        cached = cls.__dict__.get("_REFRESHABLE")
        if cached is None:
            cached = tuple(
                f.name
                for f in fields(cls)
                if f.metadata.get("serialize", True)
                and f.name not in ("order", "port_type", "_is_dirty_structural")
            )
            cls._REFRESHABLE = cached  # type: ignore[attr-defined]
        return cached

    def refresh_from(self, spec_port: "DataPort") -> None:
        """Apply a freshly built port's declarative fields to this live port.

        The same-type half of a ``rejig`` refresh: ``NodeData.add`` calls this
        instead of substituting ``spec_port``, so this object survives the
        reconfiguration and every reference to it stays valid — an
        ``EdgeWrapper``'s endpoints, an upstream ``Pipe``'s sink, a panel
        holding the port it is drawing.

        Declarative fields are the ones a port serializes: label, colors, icons,
        widget, callbacks, flow and link rules. Live state is not touched —
        value, edges, pipes and dirty flags all belong to this object and are
        already correct. Three serializable fields are handled apart:

        - ``order`` is user-owned. A graph user's arrangement outlives a node
          reconfiguring itself, so a node re-adding a port does not move it.
        - ``_is_dirty_structural`` is live state that only looks declarative;
          taking the fresh port's value would clear a pending rebuild.
        - ``port_type`` goes through ``adopt_port_type`` so the ``_is_inlet``
          cache that ``set_value`` reads follows a port refreshed across
          directions.
        """
        for name in self._refreshable_fields():
            setattr(self, name, getattr(spec_port, name))

        if spec_port.port_type is not self.port_type:
            self.adopt_port_type(spec_port.port_type)

        self._derive_wire()

    def adopt_state_from(self, existing: "DataPort") -> None:
        """Transplant edge state and display order from a port being replaced.

        Called by ``NodeData.add`` when a re-added port id resolves to a
        different type, which is the one case a refresh cannot express in
        place: the field, and whatever ``_configure_port`` derives from the
        type, genuinely differ. A same-type refresh keeps the live object
        instead — see ``refresh_from``.

        Order is user-owned: a graph user's arrangement outlives a node
        reconfiguring itself, so a node re-adding a port does not move it. A port
        the node adds for the first time takes a fresh order, and so appends.

        Each transplanted edge is re-pointed at this port, and this port's
        pipes are rebuilt, before the method returns. Both are state the swap
        invalidates, and both are otherwise repaired only by the next
        validation batch — which never comes in time for a node that rejigs
        itself *inside* a validation callback (``GraphNode.reconcile_interface``
        is the one in the codebase). Their failures are silent and different:
        a stale ``EdgeWrapper`` endpoint makes ``detach()`` unlink an orphan
        and leaves this port linked for good, while a missing ``Pipes`` makes
        an outlet stop delivering values with nothing to see at either end.
        """
        self.incoming.adopt(existing.incoming)
        self.outgoing.adopt(existing.outgoing)
        self.order = existing.order

        for link_set in (self.incoming, self.outgoing):
            for edge in link_set.all.values():
                if edge._inlet_port is existing:
                    edge._inlet_port = self
                if edge._outlet_port is existing:
                    edge._outlet_port = self

        # `_pipes` is derived from the links above and belongs to the port
        # object, so the replacement starts with none. Rebuilt here rather
        # than left to housekeeping, which only reaches a node the current
        # batch is validating.
        self._is_dirty_structural = True
        self._housekeeping()

    def _get_linked_edges_uuid(self) -> list[str]:
        """
        Get list of linked edge UUIDs.

        Returns:
            List of EdgeWrapper UUIDs linked to this port
        """
        return [*self.incoming.linked, *self.outgoing.linked]

    def _reveal_own_value_if_unlinked(self) -> None:
        """Show the own value again once no edge feeds this inlet.

        An immediate inlet goes through ``_fire_immediate``; a deferred one is
        marked dirty for its node's next execution. Nothing happens while another
        edge still feeds the inlet, or when the own value equals the linked one.
        """
        if not self._is_inlet or self.incoming.linked or not self._data.has_linked_value():
            return
        if self._is_immediate:
            self._fire_immediate(self._data.clear_linked, self._data.get_own_value())
            return
        linked = self._data.get_value()
        self._data.clear_linked()
        if not _same_value(linked, self._data.get_value()):
            self._mark_as_data_dirty()

    def get_valid_edges(self) -> list[EdgeWrapper]:
        """Return the valid linked EdgeWrappers at either end of this port."""
        return [*self.incoming.valid_edges(), *self.outgoing.valid_edges()]

    def _mark_as_structuraly_dirty(self) -> None:
        """Mark the port's node as structurally dirty."""
        self._is_dirty_structural = True

    def _housekeeping(self) -> None:
        """
        Called during graph housekeeping phase.
        Rebuild connection pipes after structural changes (like reconnecting edges).
        This cannot be done immediately upon link changes since
        at the time of a link change, the edges are not yet validated.
        """
        if self._is_dirty_structural:
            self._refresh_pipes()
            # as soon as we refresh pipes, propagate current value
            if self._pipes:
                self._pipes.propagate()
        self._is_dirty_structural = False

    def _refresh_pipes(self) -> None:
        """
        Refresh pipes based on the port's outgoing linked edges.
        With outgoing linked edges, ensure pipes exist and are up-to-date.
        Without any, clear pipes.
        Called during graph housekeeping phase.
        """
        if self.outgoing.linked:
            if self._pipes is None:
                self._pipes = Pipes(outlet_port=self)
            self._pipes.clear()
            # An is_linked_lazy outlet's edges report LAZY themselves; see
            # EdgeWrapper.locked_propagation.
            for wrapper in self.outgoing.valid_edges():
                # A VISUAL edge gets no pipe: nothing travels on it.
                if wrapper.carries_values:
                    self._pipes.add_pipe(wrapper)
        elif self._pipes:
            self._pipes.clear()
            self._pipes = None

    # ========================================================================
    # PORT TYPE CHECKS
    # ========================================================================

    def has_pin(self) -> bool:
        """Whether this port renders a connection pin on the canvas.

        Config ports are panel-only (no pin), and a fold carries the
        ``port_type`` of its children without being connectable itself — its
        disclosure triangle is the whole control. Every other inlet/outlet
        renders one.
        """
        return not self.is_config() and not self.is_fold

    def _derive_wire(self) -> None:
        """Set ``wire_type`` from the port's type, and the immediacy cache from its role.

        A config port and a fold have no wire type.
        """
        self.wire_type = None if self.is_config() or self.is_fold else wire_type_of(self.type_cls)
        self._is_immediate = self.has_role(WireRole.IMMEDIATE)

    @property
    def wire_key(self) -> str | None:
        """The key this pin matches other pins by: its wire type's id, ``WILDCARD`` for a
        bare ``ADD`` slot, or ``None`` for a port without a wire type. See ``wires_match``."""
        if self.wire_type is not None:
            return self.wire_type.id
        if self.has_pin() and self.type_cls is not None and self.type_cls._is_any:
            return WILDCARD
        return None

    @property
    def on_stage(self) -> bool:
        """Whether this pin appears on a stage: its wire type is an ``on_stage`` one."""
        return self.wire_type is not None and self.wire_type.on_stage

    def has_role(self, role: WireRole) -> bool:
        """True if this port's wire type has *role*; False for a port without a wire type."""
        return self.wire_type is not None and self.wire_type.role is role

    @property
    def is_dependent(self) -> bool:
        """True for a port on a ``DEPENDENT`` wire, and for a bare ``ADD`` slot, which
        counts as one until it grows."""
        return self.has_role(WireRole.DEPENDENT) or self.wire_key == WILDCARD

    @property
    def takes_many_links(self) -> bool:
        """Whether this port may hold more than one linked edge at a time.

        Reads ``outgoing`` for an outlet and ``incoming`` for any other port; see
        ``LinkSet.takes_many`` for the ceiling each end has.
        """
        if self.port_type is PortType.OUTLET:
            return self.outgoing.takes_many
        return self.incoming.takes_many

    @property
    def is_immediate(self) -> bool:
        """True when a write to this port takes effect on write: its wire type's role is ``IMMEDIATE``."""
        return self._is_immediate

    # ========================================================================
    # FACTORY
    # ========================================================================

    @classmethod
    def from_spec(
        cls,
        spec: dict,
        type_registry: "TypeRegistry",
        wrapper: "NodeWrapper",
        node: "NodeData",
    ) -> "DataPort":
        """
        Create a DataPort from a PortSpec dict.

        Resolves the type from the spec and creates a DataPort instance
        with wrapper reference available immediately.

        Note: CompoundType validation is done at spec creation time (as_inlet/as_outlet),
        so we trust the spec here.

        Args:
            spec: PortSpec from as_inlet/as_outlet/as_config or to_dict
            type_registry: Registry to resolve type classes
            wrapper: NodeWrapper to attach to the port
            node: BaseNode to attach to the port
        Returns:
            Instantiated DataPort
        """
        kwargs = spec["kwargs"].copy()

        type_cls = type_registry.resolve_type_from_spec(spec["recipe"])

        # Build port kwargs - spec already contains merged identity + user values
        # Keys saved before wire types and link ceilings; a port derives both.
        kwargs.pop("flow_type", None)
        kwargs.pop("allow_multiple_links", None)
        port_type = PortType(kwargs.pop("port_type", PortType.UNDEFINED.value))

        # show_widget arrives as a raw string from JSON; reconstruct the enum.
        # Absent means the field's static default applies (as_inlet/as_outlet/
        # as_config inject the per-direction default at spec-creation time).
        if "show_widget" in kwargs:
            kwargs["show_widget"] = ShowWidgetStrategy(kwargs["show_widget"])

        # store_strategy serializes to a raw int (IntFlag); reconstruct the enum
        # so the round-tripped port keeps its should_store() behaviour. Absent
        # means the field's static default applies.
        if "store_strategy" in kwargs:
            kwargs["store_strategy"] = StoreStrategy(kwargs["store_strategy"])

        # A spec says promoted=True (the promotion path, and graphs saved before
        # origin existed); origin is the field that carries it.
        if kwargs.pop("promoted", False):
            kwargs.setdefault("origin", PortOrigin.PROMOTED.value)
        if "origin" in kwargs:
            kwargs["origin"] = PortOrigin(kwargs["origin"])

        # Freeform constructor-kwargs bag (mirrors PortSpec.kwargs: Dict[str, Any]).
        # Annotated explicitly so the merge of the Any-valued spec kwargs with the
        # typed literals below stays Any rather than widening to a concrete union
        # that a type checker would then check key-by-key against cls.__init__.
        port_kwargs: dict[str, Any] = {
            **kwargs,  # Spec already has identity + user overrides
            "port_type": port_type,
            "type_cls": type_cls,
            "_wrapper": wrapper,
            "_node": node,
        }

        # Create port
        port = cls(**port_kwargs)

        # Let type configure port (for compound types, etc.)
        type_cls._configure_port(port)

        if "field_data" in spec:
            port._data.from_dict(spec["field_data"])

        return port

    def to_dict(self, include_data: bool = True) -> dict:
        """
        Serialize port using field metadata for control.

        Args:
            include_data: If True, includes field values (when store_data is also True)

        Returns:
            dict: Serialized port representation
        """
        assert self.type_cls is not None  # __post_init__ enforces this
        result: dict[str, Any] = {"kwargs": {}}
        # Every port serializes its type recipe. A promoted port omits only its VALUE
        # (field_data below) — the value round-trips via the shared setting cell.
        result["recipe"] = serialize_element_type(self.type_cls)

        # Iterate over dataclass fields
        for f in fields(self):
            # Skip fields marked as non-serializable
            if not f.metadata.get("serialize", True):
                continue

            value = getattr(self, f.name)

            # Skip if default value
            if f.default is not MISSING and value == f.default:
                continue
            if f.default_factory is not MISSING and value == f.default_factory():
                continue

            # Transform enums
            if isinstance(value, PortType):
                value = value.value
            if isinstance(value, ShowWidgetStrategy):
                value = value.value
            if isinstance(value, StoreStrategy):
                value = value.value
            if isinstance(value, PortOrigin):
                value = value.value

            result["kwargs"][f.name] = value

        # Optionally serialize field data. A promoted port never persists its
        # value here — the shared setting cell round-trips via the settings block
        # (single-writer).
        if include_data and self._data is not None and not self.promoted:
            if self.store_strategy.should_store(
                has_widget=self.widget_key is not None,
                node_set=self._is_set_by_node,
            ):
                result["field_data"] = self._serialize_value()

        return result

    def _serialize_value(self) -> dict | None:
        """Return the field's ``to_dict()``; ``None`` for an absent value.

        Raises:
            HaywireException: The field holds a value the port's type rejects; names the port.
        """
        assert self._data is not None and self.type_cls is not None
        try:
            return self._data.to_dict()
        except (TypeError, ValueError) as e:
            raise HaywireException.from_exception(
                exception=e,
                operation="Serialize port",
                message=(
                    f"Port '{self.id}' holds {self._data.get_value()!r}, "
                    f"which is not a valid {self.type_cls.__name__}"
                ),
            ).enrich(
                suggestions=[f"Give port '{self.id}' a {self.type_cls.__name__} value or default."]
            ) from e
