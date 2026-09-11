from __future__ import annotations
import inspect
import re
from typing import TYPE_CHECKING, Iterator, Any, Callable, ClassVar, Dict, List, Optional, cast
from contextlib import contextmanager

from haywire.core.execution.event_source import EventSource
from haywire.core.node import NodeIdentity
from ..types.enums import FlowType, PortType
from ..execution.execution_context import ExecutionContext
from ..library.identity import LibraryIdentity
from ..types import DataPort, PortSpec
from .behavior import NodeBehaviorFlags
from .user_data import NodeCache, NodeStore
from haywire.core.settings import NodeSettings, Settings

if TYPE_CHECKING:
    from haywire.core.node import NodeWrapper
    from haywire.core.types.registry import TypeRegistry


class NodeData:
    """Port storage and reconfiguration for a node.

    Every port — inlet, outlet and config — lives in one ``ports`` dict.
    ``rejig()`` reconfigures them while keeping the edges of those that come
    back, ``group()`` nests them under a collapsible group port on the node
    card, and ``section()`` groups them for the Properties panel.
    """

    # Class-level attributes (set by @node decorator)
    _settings_bags: ClassVar[dict[str, type[NodeSettings]]] = {}
    class_identity: ClassVar[NodeIdentity]
    class_behavior: ClassVar[NodeBehaviorFlags]
    class_library: ClassVar[LibraryIdentity]

    def worker(self, context: ExecutionContext, *args: Any, **kwargs: Any) -> "str | None":
        """Subclass hook — override to define node behaviour. See BaseNode.worker for details."""
        raise NotImplementedError(f"{type(self).__name__} must override worker()")

    def __init__(self, node_id: str, wrapper: NodeWrapper):
        """Initialize unified port collection and management state"""
        from haywire.core.di.context import get_type_registry, get_settings_registry

        self.node_id = node_id
        self.wrapper = wrapper

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

        self._group_stack: List[str] = []
        """Stack of active group IDs for nested groups."""

        self._section_stack: List[str] = []
        """Stack of active section names for property organization."""

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
        """Node behavior flags (read-only, from class)."""
        return self.__class__.class_behavior

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

        The port joins the enclosing ``group()`` and ``section()`` blocks, if
        any, and is ordered after the ports added before it. Inside ``rejig()``,
        re-adding a port ID the block flagged replaces that port and keeps its
        edges (see ``DataPort.adopt_state_from``); any other existing ID raises
        ``ValueError``::

            self.add(FLOAT.as_inlet("value"))
        """
        port = DataPort.from_spec(cast(dict, spec), self._type_registry, self.wrapper, self)

        if self._group_stack:
            port.parent_group = self._group_stack[-1]

        if self._section_stack:
            port.section = self._section_stack[-1]

        port.order = self._port_order_counter
        self._port_order_counter += 1

        if port.id in self.ports:
            existing = self.ports[port.id]

            # Flagged by the enclosing rejig(): this add refreshes it.
            if self._push_stack and port.id in self._push_stack[-1]:
                self._push_stack[-1].remove(port.id)
            else:
                raise ValueError(f"Port ID already exists: {port.id}")

            # Preserve edges (and value, if types match) from the replaced port.
            port.adopt_state_from(existing)

        self.ports[port.id] = port

        if self.wrapper:
            self.wrapper.mark_as_structuraly_dirty()
        self._executor = None

        return port

    @contextmanager
    def group(self, spec: "dict[Any, Any] | PortSpec"):
        """Add a collapsible group port; every port added inside becomes its child.

        The group is itself a boolean port on the node card, and its value is
        the expanded state. While it is collapsed, child ports are hidden but
        their edges are kept and drawn to a ghost pin. Groups nest.

        Raises:
            ValueError: If the group port's ID already exists.

        Examples:
            # Simple group
            with self.group(GROUP.as_inlet('advanced', label='Advanced Options')):
                self.add(FLOAT.as_inlet('param1'))
                self.add(FLOAT.as_inlet('param2'))

            # Nested groups
            with self.group(GROUP.as_inlet('input', label='Input Configuration')):
                self.add(FLOAT.as_inlet('value'))

                with self.group(GROUP.as_inlet('validation', label='Validation')):
                    self.add(BOOL.as_inlet('validate'))
                    self.add(FLOAT.as_inlet('tolerance'))

            # Initially collapsed
            with self.group(GROUP.as_inlet('expert', label='Expert Settings', default=False)):
                self.add(FLOAT.as_inlet('epsilon'))
        """
        group_port = self.add(spec)

        group_port.is_group = True

        self._group_stack.append(group_port.id)
        try:
            yield
        finally:
            self._group_stack.pop()

    @contextmanager
    def section(self, name: str):
        """Group the ports added inside under ``name`` in the Properties panel.

        A section creates no port of its own, and its ports are left out of the
        node card unless a caller asks for them (see ``iter_visible_ports``).

        Examples:
            # Ports in validation section
            with self.section('validation'):
                self.add(FLOAT.as_inlet('min_value'))
                self.add(FLOAT.as_inlet('max_value'))
                self.add(BOOL.as_inlet('clamp'))

            # Nested sections and groups
            with self.group(GROUP.as_inlet('advanced')):
                with self.section('performance'):
                    self.add(INT.as_inlet('max_iterations'))
        """
        self._section_stack.append(name)
        try:
            yield
        finally:
            self._section_stack.pop()

    def _push(
        self, include: Optional[List[str] | str] = None, exclude: Optional[List[str] | str] = None
    ) -> None:
        """Internal: flag ports for potential removal. Use rejig() instead."""

        if include is None:
            flagged = set(self.ports.keys())
        elif isinstance(include, str):
            pattern = re.compile(include)
            flagged = {port_id for port_id in self.ports.keys() if pattern.search(port_id)}
        else:
            flagged = set(include) & set(self.ports.keys())

        if exclude is not None:
            if isinstance(exclude, str):
                pattern = re.compile(exclude)
                flagged = {port_id for port_id in flagged if not pattern.search(port_id)}
            else:
                flagged -= set(exclude)

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
    def rejig(self, include: Optional[List[str] | str] = None, exclude: Optional[List[str] | str] = None):
        """Flag ports for removal, yield for re-adding them, then remove the rest.

        Edges on re-added ports are preserved, and the removal pass runs even if
        the body raises.

        Args:
            include: Ports to flag, applied first — ``None`` for every port, a
                list of port IDs, or a regex searched against each port ID.
            exclude: Ports to drop from the flagged set, applied second, in the
                same three forms.

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
        """
        self._push(include=include, exclude=exclude)
        try:
            yield
        finally:
            self._pop()

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

        # set_value() flags the outlet as node-set (out() is its only caller).
        port.set_value(value)

    # =========================================================================
    # Port Querying and Organization
    # =========================================================================

    def _iter_ports(self) -> Iterator[DataPort]:
        """All ports in display order. Single source of ordered iteration."""
        yield from sorted(self.ports.values(), key=lambda p: p.order)

    def iter_visible_ports(self, include_sections: bool = False) -> Iterator[DataPort]:
        """Yield the ports drawn on the node card, in display order.

        A port inside a collapsed group is skipped.

        Args:
            include_sections: When True, also yield ports assigned to a section;
                by default those reach only the Properties panel.
        """
        for port in self._iter_ports():
            if not include_sections and port.section:
                continue
            if port.parent_group and self._is_any_ancestor_collapsed(port):
                continue
            yield port

    def get_visible_ports(self, include_sections: bool = False) -> List[DataPort]:
        """The ports drawn on the node card, as a list. See ``iter_visible_ports``."""
        return list(self.iter_visible_ports(include_sections=include_sections))

    def get_all_ports(self) -> List[DataPort]:
        """Every port in display order, ignoring group collapse and sections."""
        return list(self._iter_ports())

    def get_folded_ports(self) -> List[DataPort]:
        """The ports a folded node card draws: every linked port, whatever its group state.

        Group collapse is ignored so that an edge always finds its endpoint on a
        folded card. Unlinked ports, sectioned ports and group control ports are
        left out.
        """
        return [
            port
            for port in self.get_all_ports()
            if not port.section and not port.is_group and port.is_linked()
        ]

    def iter_section_ports(self, section: Optional[str] = None) -> Iterator[DataPort]:
        """Yield the ports assigned to a section, in display order.

        Args:
            section: Section name to filter by, or ``None`` for every section.
        """
        for port in self._iter_ports():
            if not port.section:
                continue
            if section is not None and port.section != section:
                continue
            yield port

    def get_section_ports(self, section: Optional[str] = None) -> Dict[str, List[DataPort]]:
        """Return the ports grouped by section name, each list in display order.

        Args:
            section: Section name to filter by, or ``None`` for every section.

        Examples:
            sections = self.get_section_ports()
            for section_name, ports in sections.items():
                render_section_header(section_name)
                for port in ports:
                    render_property(port)
        """
        sections: Dict[str, List[DataPort]] = {}
        for port in self.iter_section_ports(section):
            assert port.section is not None, "iter_section_ports yields only sectioned ports"
            sections.setdefault(port.section, []).append(port)
        return sections

    def iter_group_children(self, group_id: str) -> Iterator[DataPort]:
        """Yield the direct children of group ``group_id``, in display order."""
        for port in self._iter_ports():
            if port.parent_group == group_id:
                yield port

    def is_group_expanded(self, group_id: str) -> bool:
        """Return whether a group is currently expanded.

        Raises:
            KeyError: If no port has this ID.
            ValueError: If the port is not a group.
        """
        port = self.ports.get(group_id)
        if not port:
            raise KeyError(f"Group '{group_id}' not found")
        if not port.is_group:
            raise ValueError(f"Port '{group_id}' is not a group")

        return self.value(group_id)

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
        """Yield linked ports that a collapsed ancestor group hides, in display order.

        Their pins are drawn near the node title so an edge keeps an endpoint.
        Sectioned ports and group control ports are left out.

        Args:
            is_inlet: Selects the opposite side: ``True`` yields the hidden ports
                that are not inlets, ``False`` the hidden inlets.
        """
        visible_ids = {p.id for p in self.iter_visible_ports()}

        for port in self._iter_ports():
            if port.is_inlet() == is_inlet:
                continue
            if port.section or port.is_group:
                continue
            if port.id not in visible_ids and port.is_linked():
                yield port

    def get_hidden_connected_ports(self, is_inlet: bool) -> List[DataPort]:
        """Hidden linked ports as a list. See ``iter_hidden_connected_ports``."""
        return list(self.iter_hidden_connected_ports(is_inlet))

    def _is_any_ancestor_collapsed(self, port: DataPort) -> bool:
        """Return whether any ancestor group of *port* is collapsed."""
        current_group_id = port.parent_group

        while current_group_id is not None:
            group_port = self.ports.get(current_group_id)
            if not group_port:
                # Broken hierarchy - assume visible
                break

            # group_port is in self.ports (checked above), so value() cannot KeyError.
            if not self.value(current_group_id):
                return True

            current_group_id = group_port.parent_group

        return False

    def get_port_hierarchy(self, port_id: str) -> str:
        """Return the port's path up to ``'root'``, its parent groups joined with ``'>>'``.

        Raises:
            KeyError: If no port has this ID.

        Examples:
            # Top-level port
            path = self.get_port_hierarchy('value')
            # Returns: 'value>>root'

            # Port in a group
            path = self.get_port_hierarchy('tolerance')
            # Returns: 'tolerance>>advanced>>root'

            # Port in nested groups
            path = self.get_port_hierarchy('epsilon')
            # Returns: 'epsilon>>validation>>advanced>>root'
        """
        port = self.ports.get(port_id)
        if not port:
            raise KeyError(f"Port '{port_id}' not found")

        hierarchy_parts = [port_id]
        current_port = port

        while current_port.parent_group is not None:
            parent_id = current_port.parent_group
            parent_port = self.ports.get(parent_id)

            if not parent_port:
                # Broken hierarchy: stop where the chain ends.
                break

            hierarchy_parts.append(parent_id)
            current_port = parent_port

        hierarchy_parts.append("root")

        return ">>".join(hierarchy_parts)

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
