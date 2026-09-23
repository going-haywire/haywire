from __future__ import annotations
import inspect
import re
from typing import TYPE_CHECKING, Iterator, Any, Callable, ClassVar, Dict, List, Optional, cast
from contextlib import contextmanager
from dataclasses import replace

from haywire.core.execution.event_source import EventSource
from haywire.core.node import NodeIdentity
from ..types.enums import FlowType, PortOrigin, PortType
from ..execution.execution_context import ExecutionContext
from ..library.identity import LibraryIdentity
from ..types import DataPort, PortSpec
from .behavior import NodeBehaviorFlags, NodeType
from .user_data import NodeCache, NodeStore
from haywire.core.settings import NodeSettings, Settings

if TYPE_CHECKING:
    from haywire.core.node import NodeWrapper
    from haywire.core.types.registry import TypeRegistry

#: One criterion a :meth:`NodeData.rejig` filter selects ports by: an exact
#: port id, every port of one :class:`PortOrigin`, or a compiled pattern
#: searched against each port id.
PortCriterion = str | PortOrigin | re.Pattern[str]

#: What ``rejig``'s ``include`` / ``exclude`` take: a bare ``str`` is a regex
#: (kept for the single-pattern spelling), and a list holds ``PortCriterion``
#: values whose matches are unioned.
PortFilter = str | List[PortCriterion]


class NodeData:
    """Port storage and reconfiguration for a node.

    Every port — inlet, outlet and config — lives in one ``ports`` dict.
    ``rejig()`` reconfigures them while keeping the edges of those that come
    back, and ``fold()`` nests them under a collapsible fold port on the node
    card.
    """

    # Class-level attributes (set by @node decorator)
    _settings_bags: ClassVar[dict[str, type[NodeSettings]]] = {}
    class_identity: ClassVar[NodeIdentity]
    # Defaulted, unlike class_identity/class_library: __init__ stamps _behavior
    # from this unconditionally, and a bare NodeData (no @node) is a supported
    # stand-in in widget-only tests that never reach the decorator.
    class_behavior: ClassVar[NodeBehaviorFlags] = NodeBehaviorFlags()
    class_library: ClassVar[LibraryIdentity]

    def worker(self, context: ExecutionContext, *args: Any, **kwargs: Any) -> "str | None":
        """Subclass hook — override to define node behaviour. See BaseNode.worker for details."""
        raise NotImplementedError(f"{type(self).__name__} must override worker()")

    def __init__(self, node_id: str, wrapper: NodeWrapper):
        """Initialize unified port collection and management state"""
        from haywire.core.di.context import get_type_registry, get_settings_registry

        self.node_id = node_id
        self.wrapper = wrapper

        # Stamped here rather than read off the class on every access, because
        # a node whose shape decides its role restamps it — and because a read
        # can land before init() (structural validation does one).
        self._behavior: NodeBehaviorFlags = self.__class__.class_behavior

        self.event_subscription: EventSource | None = None
        # TODO: CallbackSystem
        """event nodes store here the event subscription"""

        # Cache type registry for port instantiation
        self._type_registry: "TypeRegistry" = get_type_registry()

        # ---------------------------------------------------------------------
        # Core containers
        # ---------------------------------------------------------------------

        # Ports
        self.ports: Dict[str, DataPort] = {}
        """Single source of truth for all ports (inlets and outlets)."""

        # Each Settings subclass declared in the node class body becomes an instance
        # attribute, so node authors write self.filter.threshold.
        _registry = get_settings_registry()
        for _bag_name, _bag_cls in type(self)._settings_bags.items():
            _bag_instance: Settings = _bag_cls(registry=_registry, node=self)
            _bag_instance._subscribe_settings()
            object.__setattr__(self, _bag_name, _bag_instance)

        self._cache: NodeCache = NodeCache()

        self._store: NodeStore = NodeStore()

        # Keyed by port id: a str caches its hash at C level, while a set of
        # DataPort would call the Python-level DataPort.__hash__ on every mark.
        self._has_dirty_ports: Dict[str, DataPort] = {}

        # ---------------------------------------------------------------------
        # Internal state
        # ---------------------------------------------------------------------

        self._push_stack: List[set[str]] = []
        """Stack of port ID sets for rejig operations."""

        self._fold_stack: List[str] = []
        """Stack of active group IDs for nested groups."""

        self._fold_direction: Dict[str, PortType] = {}
        """The direction each open fold has committed to, by fold port id."""

        self._port_order_counter: int = 0
        """Counter for assigning display order to ports."""

        self._executor: Optional[Callable] = None
        """Optimized execution callable."""

    @property
    def identity(self) -> NodeIdentity:
        """Node identity (read-only, from class)."""
        return self.__class__.class_identity

    @property
    def behavior(self) -> NodeBehaviorFlags:
        """This node's behavior flags (read-only).

        Stamped from the class at construction. Every field is the class's
        except ``node_type``, which a node whose shape decides its role
        restamps through :meth:`set_node_type`.
        """
        return self._behavior

    def set_node_type(self, node_type: NodeType) -> None:
        """Give this node a ``node_type`` of its own, leaving its other flags alone.

        For a node whose execution role follows its ports rather than its
        class — a Graph-node is CONTROL when control crosses its Subgraph and
        DATA when only data does.

        Call it whenever the shape it is derived from changes, and before
        anything reads the role: structural validation reads it as the node is
        added, and assembly reads it to place the node in a flow. A flow
        already built is not revisited, so a call after assembly reaches the
        next one, not the frame in flight.
        """
        self._behavior = replace(self._behavior, node_type=node_type)

    @property
    def library(self) -> LibraryIdentity:
        """Library identity (read-only, from class)."""
        return self.__class__.class_library

    def list_setting_bags(self) -> dict[str, Settings]:
        """Return every user-declared ``Settings`` instance on this node, keyed by accessor name.

        A node author reads and writes a bag through its instance attribute
        instead::

            self.filter.threshold         # read
            self.filter.threshold = 0.8   # write a local override
        """
        return {name: getattr(self, name) for name in type(self)._settings_bags}

    @property
    def cache(self) -> NodeCache:
        """The node's transient cache. See ``NodeCache``."""
        return self._cache

    @property
    def store(self) -> NodeStore:
        """The node's persistent store. See ``NodeStore``."""
        return self._store

    # =========================================================================
    # Housekeeping
    # =========================================================================

    def _housekeeping(self) -> None:
        """Refresh every port's internal state, rebuilding its connection pipes."""
        for port in self.ports.values():
            port._housekeeping()

    # =========================================================================
    # Port Addition and Management
    # =========================================================================

    def add(self, spec: "dict[Any, Any] | PortSpec") -> DataPort:
        """Add an inlet or outlet from a port spec and return the built port.

        The port joins the enclosing ``fold()`` block, if any, and is ordered
        after the ports added before it. Inside ``rejig()``, re-adding a port
        ID the block flagged refreshes that port and keeps its edges; any other
        existing ID raises ``ValueError``::

            self.add(FLOAT.as_inlet("value"))

        A refresh (using this function within a rejig()) keeps the live ``DataPort``
        if possible. Changes of the field or port type produces a genuinely different
        port object and triggerst a housekeeping pass to reattach edges to the new port.

        Returns:
            The live port carrying the spec: the refreshed existing object, or
            the new one when the port is new or its type changed.
        """
        port = DataPort.from_spec(cast(dict, spec), self._type_registry, self.wrapper, self)

        if self._fold_stack:
            port.parent_fold = self._fold_stack[-1]

        if port.parent_fold:
            self._commit_fold_direction(port.parent_fold, port.id, port.port_type)

        port.order = self._port_order_counter
        self._port_order_counter += 1

        if port.id in self.ports:
            existing = self.ports[port.id]

            # Flagged by the enclosing rejig(): this add refreshes it.
            if self._push_stack and port.id in self._push_stack[-1]:
                self._push_stack[-1].remove(port.id)
            else:
                raise ValueError(f"Port ID already exists: {port.id}")

            if existing.type_cls is port.type_cls:
                existing.refresh_from(port)
                port = existing
            else:
                # Preserve edges from the replaced port.
                port.adopt_state_from(existing)

        self.ports[port.id] = port

        if self.wrapper:
            self.wrapper.mark_as_structuraly_dirty()
        self._executor = None

        return port

    @staticmethod
    def _fold_id(label: str) -> str:
        """Return the port id a fold takes from its ``label``."""
        return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")

    def _commit_fold_direction(self, fold_id: str, port_id: str, port_type: PortType) -> None:
        """Record ``port_id``'s direction as fold ``fold_id``'s, or raise.

        A fold renders in one lane. Two lanes would need its header drawn
        twice, so a mixed fold is an authoring error, not a layout to resolve
        at render time.

        Raises:
            ValueError: If the fold already committed to another direction.
        """
        committed = self._fold_direction.setdefault(fold_id, port_type)
        if committed is not port_type:
            raise ValueError(
                f"Fold {fold_id!r} holds {committed.value} ports; "
                f"{port_id!r} is {port_type.value}. A fold holds one direction."
            )

    @contextmanager
    def fold(self, label: str, *, default: bool = True, **kwargs):
        """Add a collapsible fold; every port added inside becomes its child.

        The fold is a port with no pin and no widget: the disclosure triangle on
        the node card is its only control, and its value is the open state. It
        persists, so a node reopens as the user left it, and a node may read it
        or pass ``on_change=`` to reconfigure itself when the user folds.

        Its id is derived from ``label``. The fold takes the direction of the
        ports inside it, so that it renders in their lane; mixing directions
        inside one fold raises, and so does an empty one. A fold holds ports,
        not other folds — nesting one raises.

        Label a fold as a section ("Custom Name"), not as an imperative
        ("Use Custom Name") — it names what is inside, and the user opens it
        rather than deciding something.

        Args:
            label: The header text, and the source of the fold's port id.
            default: Whether the fold starts open.
            **kwargs: Forwarded to the port spec — ``on_change``, ``description``
                and the rest of ``as_config``'s keywords. ``description`` shows
                under the label in the header's hover tooltip.

        Raises:
            ValueError: If the fold's id already exists on this node, if it is
                declared inside another fold, if the ports inside it disagree
                on direction, or if it holds none.

        Examples:
            # A fold over two config ports
            with self.fold('Solver'):
                self.add(INT.as_config('substeps', default=10))
                self.add(INT.as_config('iterations', default=1))

            # Closed until the user opens it
            with self.fold('Advanced', default=False):
                self.add(FLOAT.as_config('epsilon', default=1e-6))

            # Reconfigure the node when the user folds
            with self.fold('Custom Name', on_change='hb_change'):
                self.add(STRING.as_config('name', default='my_callback'))
        """
        from haywire.barn.builtin.types import FOLD

        fold_id = self._fold_id(label)
        spec = FOLD.as_config(fold_id, label=label, default=default, **kwargs)
        if self._fold_stack:
            raise ValueError(
                f"Fold {fold_id!r} is declared inside fold {self._fold_stack[-1]!r}. "
                f"A fold holds ports, not other folds."
            )

        fold_port = self.add(spec)
        fold_port.is_fold = True

        self._fold_stack.append(fold_port.id)
        try:
            yield fold_port
        finally:
            self._fold_stack.pop()
            committed = self._fold_direction.pop(fold_port.id, None)

        # Only on a clean exit: raising here on the exception path would mask
        # whatever the body raised (the mixing ValueError above, most often).
        if committed is None:
            raise ValueError(
                f"Fold {fold_port.id!r} holds no ports. A fold takes its direction "
                f"from the ports inside it, so it must hold at least one."
            )
        # The fold renders in its children's lane, not in the config band its
        # as_config() spec would otherwise put it in. It stays pinless through
        # is_fold — see DataPort.has_pin().
        fold_port.adopt_port_type(committed)

    def _match_filter(self, spec: PortFilter) -> set[str]:
        """Internal: the ids ``spec`` selects. A list's criteria are OR'd."""
        if isinstance(spec, str):
            pattern = re.compile(spec)
            return {port_id for port_id in self.ports if pattern.search(port_id)}

        matched: set[str] = set()
        for criterion in spec:
            if isinstance(criterion, PortOrigin):
                matched |= {pid for pid, port in self.ports.items() if port.origin is criterion}
            elif isinstance(criterion, re.Pattern):
                matched |= {pid for pid in self.ports if criterion.search(pid)}
            else:
                # An exact id inside a list; a regex there is a compiled Pattern.
                if criterion in self.ports:
                    matched.add(criterion)
        return matched

    def _push(self, include: Optional[PortFilter] = None, exclude: Optional[PortFilter] = None) -> None:
        """Internal: flag ports for potential removal. Use rejig() instead."""
        flagged = set(self.ports) if include is None else self._match_filter(include)
        if exclude is not None:
            flagged -= self._match_filter(exclude)
        self._push_stack.append(flagged)

    def _pop(self) -> List[str]:
        """Internal: remove flagged ports not refreshed. Use rejig() instead."""
        if not self._push_stack:
            raise RuntimeError("_pop() called without matching _push()")

        flagged = self._push_stack.pop()
        removed = []

        for port_id in flagged:
            if port_id in self.ports:
                port = self.ports[port_id]

                # Detach all edges from the destroyed port
                detached = port._detach_all_edges()
                for edge in detached:
                    if port.is_inlet():
                        # Inlet destroyed → inform source outlet (needs pipe update)
                        if edge._outlet_port and edge._outlet_port is not port:
                            edge._outlet_port._remove_edge(edge.edge_id)
                            edge._update_link_state()
                            edge._outlet_port._housekeeping()
                    else:
                        # Outlet destroyed: the sink inlet is not informed (asymmetric).
                        edge._update_link_state()
                    edge.redraw()

                del self.ports[port_id]
                removed.append(port_id)

        self.wrapper.mark_as_structuraly_dirty()
        self._executor = None
        return removed

    @contextmanager
    def rejig(self, include: Optional[PortFilter] = None, exclude: Optional[PortFilter] = None):
        """Flag ports for removal, yield for re-adding them, then remove the rest.

        Edges on re-added ports are preserved, and the removal pass runs even if
        the body raises.

        **Flag only what this call owns.** Whatever is flagged and not re-added
        inside the block is destroyed, so a call that rebuilds one set of ports
        must exclude every other set. A bare ``rejig()`` flags **every** port,
        which is right only when the block re-adds the node's whole port list.
        Two cases need a filter:

        - ports declared in ``init()`` that this call does not rebuild —
          config ports, and the **growing slot** of a node whose interface is
          stamped from outside. ``exclude=[PortOrigin.DECLARED]`` spares them
          all.
        - ports grown or promoted by the user, when the call rebuilds only what
          the author declared. ``exclude=[PortOrigin.RESOLVED,
          PortOrigin.PROMOTED]``.

        Filter by :class:`PortOrigin` rather than by an id pattern where the
        distinction is ownership: ``exclude=r"^slot_"`` holds only as long as
        the naming convention does, while the origin is the property that
        actually separates an authored port from a stamped one.

        A port is flagged when it matches ``include`` and does not match
        ``exclude``, so a port named by both is spared. Each filter is
        ``None``, a regex string, or a list whose criteria are OR'd: an exact
        port id, a :class:`PortOrigin` standing for every port of that origin,
        or a compiled pattern. ``include=None`` means every port;
        ``include=[]`` means none.

        Args:
            include: Ports to flag, applied first.
            exclude: Ports to drop from the flagged set, applied second.

        Examples:
            Reconfigure all ports except a config port:

            .. code-block:: python

                with self.rejig(exclude=['config_port']):
                    self.add(FLOAT.as_inlet('value'))
                    self.add(FLOAT.as_outlet('result'))

            Reconfigure only dynamic ports by regex:

            .. code-block:: python

                with self.rejig(include=r'^dynamic_'):
                    for i in range(count):
                        self.add(INT.as_inlet(f'dynamic_inlet_{i}'))

            Rebuild an interface stamped from outside, sparing the growing
            slot this node declared (it is not part of the interface, and a
            bare rejig would take it):

            .. code-block:: python

                with self.rejig(exclude=[PortOrigin.DECLARED]):
                    for port in interface:
                        self.add(port.spec())

            Several criteria in one filter — they are OR'd, so this spares one
            named port as well as everything declared:

            .. code-block:: python

                with self.rejig(exclude=['add_port', PortOrigin.DECLARED]):
                    ...

            Rebuild only what the user grew, leaving the rest alone:

            .. code-block:: python

                with self.rejig(include=[PortOrigin.RESOLVED]):
                    ...
        """
        self._push(include=include, exclude=exclude)
        try:
            yield
        finally:
            self._pop()

    def reorder_ports(self, ordered_ids: list[str]) -> None:
        """Set the display order of one sibling group from ``ordered_ids``.

        Siblings are the ports sharing a direction lane and a fold — the group
        the user can actually rearrange. Ports outside the list keep the order
        they had, so reordering one lane leaves every other lane alone.

        Ids naming no port are skipped, and an empty list changes nothing.

        Args:
            ordered_ids: Every sibling in the group, in the order they should
                display.
        """
        known = [pid for pid in ordered_ids if pid in self.ports]
        if not known:
            return

        # Reuse the slots the group already occupies, so only these ports move.
        slots = sorted(self.ports[pid].order for pid in known)
        for slot, pid in zip(slots, known, strict=True):
            self.ports[pid].order = slot

        from haywire.core.node.promotion import set_promoted_order

        for pid in known:
            port = self.ports[pid]
            if port.promoted:
                set_promoted_order(self, pid, port.order)

        if self.wrapper:
            self.wrapper.mark_layout_changed()

    # =========================================================================
    # Port Value Access
    # =========================================================================

    def value(self, id: str) -> Any:
        """Return a port's value unwrapped, in the shape its field type yields.

        A ``PrimitiveField`` yields the bare primitive, a ``BaseField`` the
        ``BaseType`` instance, a ``PooledField`` a dict of unwrapped values, and
        an ``ArrayField`` a list of them.

        Raises:
            KeyError: If no port has this ID.

        Examples:
            # Primitive inlet
            value = self.value('float_input')  # Returns: 42.0

            # Complex inlet
            mesh = self.value('mesh_input')  # Returns: MeshData(...)

            # Pooled inlet
            temps = self.value('temperature_pool')  # Returns: {"node1": 20.0, "node2": 25.0}

            # Array inlet
            numbers = self.value('number_array')  # Returns: [1.0, 2.0, 3.0]

            # Group state
            is_advanced = self.value('advanced_group')  # Returns: True/False
        """
        port = self.ports.get(id)
        if not port:
            raise KeyError(f"Port '{id}' not found")

        return port.get_value()

    def out(self, id: str, value: Any) -> None:
        """Set an outlet's value from the worker, taking the value unwrapped.

        Raises:
            KeyError: If no port has this ID.
            ValueError: If the port is an inlet.

        Examples:
            # Primitive outlet
            self.out('result', 42.0)  # Just pass the float!

            # Complex outlet
            self.out('mesh_out', MeshData(...))  # Pass the instance

            # Array outlet
            self.out('sorted', [1.0, 2.0, 3.0])  # Pass the list
        """
        port = self.ports.get(id)
        if not port:
            raise KeyError(f"Port '{id}' not found")
        if port.is_inlet():
            raise ValueError(f"Port '{id}' is an inlet and cannot be set via out()")

        # set_value() flags the outlet as node-set. Subgraph Output's worker is
        # the one other caller, writing the Graph-node card's outlets.
        port.set_value(value)

    # =========================================================================
    # Port Querying and Organization
    # =========================================================================

    def _iter_ports(self) -> Iterator[DataPort]:
        """All ports in display order. Single source of ordered iteration."""
        yield from sorted(self.ports.values(), key=lambda p: p.order)

    def iter_visible_ports(self) -> Iterator[DataPort]:
        """Yield the ports drawn on the node card, in display order.

        A port inside a closed fold is skipped.
        """
        for port in self._iter_ports():
            if port.parent_fold and self._is_any_ancestor_collapsed(port):
                continue
            yield port

    def get_visible_ports(self) -> List[DataPort]:
        """The ports drawn on the node card, as a list. See ``iter_visible_ports``."""
        return list(self.iter_visible_ports())

    def get_all_ports(self) -> List[DataPort]:
        """Every port in display order, ignoring fold collapse."""
        return list(self._iter_ports())

    def get_folded_ports(self) -> List[DataPort]:
        """The ports a folded node card draws: every linked port, whatever its fold state.

        Fold collapse is ignored so that an edge always finds its endpoint on a
        folded card. Unlinked ports and fold control ports are left out.
        """
        return [port for port in self.get_all_ports() if not port.is_fold and port.is_linked()]

    def get_ports(
        self,
        is_port_type: Optional[PortType] = None,
        has_pin: Optional[bool] = None,
        is_flow_type: Optional[FlowType] = None,
        is_not_flow_type: Optional[FlowType] = None,
        has_widget: Optional[bool] = None,
    ) -> list[DataPort]:
        """Return the ports matching every filter given. ``None`` disables a filter.

        Args:
            is_port_type: Keep ports of this ``PortType``.
            has_pin: Keep ports that do, or do not, draw a visual pin.
            is_flow_type: Keep ports of this ``FlowType``.
            is_not_flow_type: Drop ports of this ``FlowType``.
            has_widget: Keep ports that do, or do not, carry a widget.
        """
        return [
            port
            for port in self.ports.values()
            if (is_port_type is None or is_port_type == port.port_type)
            and (has_pin is None or has_pin == port.has_pin())
            and (is_flow_type is None or is_flow_type == port.flow_type)
            and (is_not_flow_type is None or is_not_flow_type != port.flow_type)
            and (has_widget is None or has_widget == port.widget_key is not None)
        ]

    def iter_hidden_connected_ports(self, is_inlet: bool) -> Iterator[DataPort]:
        """Yield linked ports that a collapsed ancestor fold hides, in display order.

        Their pins are drawn near the node title so an edge keeps an endpoint.
        Fold control ports are left out.

        Args:
            is_inlet: Selects the opposite side: ``True`` yields the hidden ports
                that are not inlets, ``False`` the hidden inlets.
        """
        visible_ids = {p.id for p in self.iter_visible_ports()}

        for port in self._iter_ports():
            if port.is_inlet() == is_inlet:
                continue
            if port.is_fold:
                continue
            if port.id not in visible_ids and port.is_linked():
                yield port

    def get_hidden_connected_ports(self, is_inlet: bool) -> List[DataPort]:
        """Hidden linked ports as a list. See ``iter_hidden_connected_ports``."""
        return list(self.iter_hidden_connected_ports(is_inlet))

    def _is_any_ancestor_collapsed(self, port: DataPort) -> bool:
        """Return whether any ancestor fold of *port* is collapsed."""
        current_fold_id = port.parent_fold

        while current_fold_id is not None:
            fold_port = self.ports.get(current_fold_id)
            if not fold_port:
                # Broken hierarchy - assume visible
                break

            # fold_port is in self.ports (checked above), so value() cannot KeyError.
            if not self.value(current_fold_id):
                return True

            current_fold_id = fold_port.parent_fold

        return False

    def mark_port_as_dirty(self, port: DataPort) -> None:
        """Record that *port* changed, so the node's worker runs on the next execution."""
        self._has_dirty_ports[port.id] = port

    # =========================================================================
    # Worker Signature Analysis and Execution
    # =========================================================================

    def _analyze_worker_signature(self) -> Callable:
        """Build a callable that takes a context and invokes ``self.worker`` with the
        unwrapped values of the ports its signature names.

        Raises:
            ValueError: If a worker parameter without a default names no existing
                port.
            RuntimeError: If ``self`` has no ``worker`` method.
        """
        worker_method = getattr(self, "worker", None)
        if not worker_method:
            raise RuntimeError(
                f"{type(self).__name__} has no worker method. Concrete BaseNode "
                f"subclasses must override worker()."
            )

        sig = inspect.signature(worker_method)
        params = dict(sig.parameters)
        params.pop("self", None)
        params.pop("context", None)

        if not params:
            return lambda ctx: self.worker(ctx)

        param_names_with_ports = []

        for name, param in params.items():
            has_port = name in self.ports
            is_required = param.default is inspect.Parameter.empty

            if is_required and not has_port:
                raise ValueError(f"Required worker parameter '{name}' has no matching port.")

            if has_port:
                param_names_with_ports.append(name)

        return self._create_executor(param_names_with_ports)

    def _create_executor(self, param_names: List[str]) -> Callable:
        ports = [self.ports[name] for name in param_names]
        n = len(ports)

        if n == 0:
            return lambda ctx: self.worker(ctx)
        elif n == 1:
            p0 = ports[0]
            return lambda ctx: self.worker(ctx, p0.get_value())
        elif n == 2:
            p0, p1 = ports
            return lambda ctx: self.worker(ctx, p0.get_value(), p1.get_value())
        elif n == 3:
            p0, p1, p2 = ports
            return lambda ctx: self.worker(ctx, p0.get_value(), p1.get_value(), p2.get_value())
        elif n == 4:
            p0, p1, p2, p3 = ports
            return lambda ctx: self.worker(
                ctx, p0.get_value(), p1.get_value(), p2.get_value(), p3.get_value()
            )
        elif n == 5:
            p0, p1, p2, p3, p4 = ports
            return lambda ctx: self.worker(
                ctx, p0.get_value(), p1.get_value(), p2.get_value(), p3.get_value(), p4.get_value()
            )
        else:
            port_refs = list(zip(param_names, ports, strict=False))
            cache: dict[str, Any] = {name: None for name in param_names}

            def extract_dict():
                for name, port in port_refs:
                    cache[name] = port.get_value()
                return cache

            return lambda ctx: self.worker(ctx, **extract_dict())

    def _parse_worker_result(self, result: str | None) -> str | None:
        """Return the worker's outlet ID unchanged, raising ``ValueError`` for any non-``str``."""
        if result is not None and not isinstance(result, str):
            raise ValueError(
                f"Worker must return str (outlet ID) or None, got {type(result).__name__}: {result!r}"
            )
        return result

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def _serialize_ports(self, include_data: bool = True) -> Dict[str, Any]:
        """Return each non-promoted port's ``to_dict()``, keyed by port ID.

        A promoted port is omitted: its promotion is recorded in the owning
        settings bag and the port is regenerated on load (see ADR 0019).

        Args:
            include_data: When True, port field values are included.
        """
        return {
            port_id: port.to_dict(include_data=include_data)
            for port_id, port in self.ports.items()
            if not port.promoted
        }

    def _deserialize_ports(self, ports_data: Dict[str, Any]) -> bool:
        """Replace every port with the ones *ports_data* describes, and return True.

        Args:
            ports_data: Port specs keyed by port ID, as ``_serialize_ports``
                produces them.

        Raises:
            ValueError: If a spec names a type the registry cannot resolve.
        """
        self.ports.clear()
        self._port_order_counter = 0

        for _port_id, spec in ports_data.items():
            port = DataPort.from_spec(cast(dict, spec), self._type_registry, self.wrapper, self)

            # Bypass add() so the display order stored in the spec survives.
            self.ports[port.id] = port

            if port.order >= self._port_order_counter:
                self._port_order_counter = port.order + 1

        self._executor = None
        return True

    def _regenerate_promoted_ports(self) -> None:
        """Regenerate this node's promoted ports from its settings bags."""
        from haywire.core.node.promotion import regenerate_promoted_ports

        regenerate_promoted_ports(self)
