from __future__ import annotations
import inspect
import re
from typing import TYPE_CHECKING, Iterator, Set, Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import asdict
from abc import abstractmethod
from contextlib import contextmanager

from haywire.core.execution.event_source import EventSource
from haywire.core.node import NodeIdentity
from haywire.core.node.properties import NodeProperties  # re-exported for type hints
from ..types.enums import FlowType, PortType
from ..execution.execution_context import ExecutionContext
from ..library.identity import LibraryIdentity
from ..types import DataPort
from .behavior import NodeBehaviorFlags
from .user_data import NodeCache, NodeStore
from haywire.core.settings import Settings, NodeSettings

if TYPE_CHECKING:
    from haywire.core.node import NodeWrapper
    from haywire.core.types.registry import TypeRegistry

T = TypeVar("T")


class NodeMeta(type):
    """Metaclass for nodes"""

    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        return new_class


class NodeData:
    """
    Node data management with unified port collection and dynamic reconfiguration.

    Provides:
    - Unified port storage (inlets and outlets in single dict)
    - Dynamic port reconfiguration (rejig context manager)
    - Hierarchical grouping (nested groups with context managers)
    - Section organization (for property panels)
    - Clean API for port access
    """

    # Class-level attributes (set by @node decorator)
    class_identity: NodeIdentity
    class_behavior: NodeBehaviorFlags
    class_library: LibraryIdentity

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

        # Settings bags (GUI-facing, serialized)
        # Each Settings subclass declared in the node class body is instantiated with
        # the global registry injected (extended mode), then bound directly as a
        # node instance attribute so node authors can write self.filter.threshold.
        _registry = get_settings_registry()
        for _bag_name, _bag_cls in getattr(type(self), "_settings_bags", {}).items():
            _bag_instance: Settings = _bag_cls(registry=_registry)
            _bag_instance._subscribe_mirrors()
            object.__setattr__(self, _bag_name, _bag_instance)

        # Cache (transient, NOT serialized)
        self._cache: NodeCache = NodeCache()

        # Store (persistent, serialized, NOT GUI-facing)
        self._store: NodeStore = NodeStore()

        self._has_dirty_ports: Set[DataPort] = set()

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
        """
        Return all user-declared Settings instances keyed by name.

        Used by panels and framework code to discover and render node settings.
        Node authors access bags directly via the instance attribute instead::

            class filter(Settings):
                threshold: float = setting(0.5)

            self.filter.threshold         # read
            self.filter.threshold = 0.8   # write local override
            self.filter.reset('threshold')
        """
        return {name: getattr(self, name) for name in getattr(type(self), "_settings_bags", {})}

    @property
    def cache(self) -> NodeCache:
        """
        Transient cache (NOT serialized).

        Use for temporary data that can be safely lost:
        - Computation caches
        - Temporary buffers
        - Runtime-only state

        Example:
            self.cache.lookup = {}
            self.cache.last_input = None
        """
        return self._cache

    @property
    def store(self) -> NodeStore:
        """
        Persistent store (serialized, NOT GUI-facing).

        Use for internal state that must persist but users
        don't need to see or edit:
        - Counters
        - Accumulated results
        - Internal state machines

        Example:
            self.store.execution_count = 0
            self.store.history = []
        """
        return self._store

    # =========================================================================
    # Housekeeping
    # =========================================================================

    def _housekeeping(self) -> None:
        """
        Perform housekeeping tasks for the node.

        This method is called during the graph housekeeping phase
        to allow the node to refresh its internal state, such as
        rebuilding connection pipes after structural changes.
        """
        for port in self.ports.values():
            port._housekeeping()

    # =========================================================================
    # Port Addition and Management
    # =========================================================================

    def add(self, spec: dict) -> DataPort:
        """
        Add a port (inlet or outlet) to the node with automatic hierarchy tracking.

        Accepts either:
        - PortSpec dict (from FLOAT.as_inlet(), etc.) - instantiates port
        - DataPort instance (backward compatibility)

        When given a PortSpec, instantiates the port with wrapper reference
        available immediately - no race condition!

        This method automatically:
        - Assigns the port to the current group (if in a group context)
        - Assigns the port to the current section (if in a section context)
        - Assigns a display order
        - Preserves connections if replacing an existing port (during reconfiguration)
        - Unflags the port if in a rejig context

        Args:
            spec: specification dict

        Returns:
            The added DataPort

        Raises:
            ValueError: If port ID already exists (unless in rejig context)

        Examples:
            # Recommended: pass spec (returns PortSpec dict)
            self.add(FLOAT.as_inlet('value'))

            # Port in group
            with self.group('advanced'):
                self.add(FLOAT.as_inlet('param'))  # Auto-assigned to 'advanced' group

            # Port with section
            with self.section('validation'):
                self.add(FLOAT.as_inlet('tolerance'))  # Auto-assigned to section
        """
        # Resolve spec to port instance if needed
        port = DataPort.from_spec(spec, self._type_registry, self.wrapper, self)

        # Set parent from current group stack
        if self._group_stack:
            port.parent_group = self._group_stack[-1]

        # Set section from current section stack
        if self._section_stack:
            port.section = self._section_stack[-1]

        # Assign display order
        port.order = self._port_order_counter
        self._port_order_counter += 1

        # Handle existing port (reconfiguration case)
        if port.id in self.ports:
            existing = self.ports[port.id]

            # If in push context, unflag it (it's being refreshed)
            if self._push_stack and port.id in self._push_stack[-1]:
                self._push_stack[-1].remove(port.id)
            else:
                raise ValueError(f"Port ID already exists: {port.id}")

            # Preserve connections from existing port
            port._linked_edges = existing._linked_edges.copy()
            port._all_edges = existing._all_edges.copy()

            # Preserve value if types are compatible
            if existing._data is not None and port._data is not None:
                if existing.type_cls is port.type_cls:
                    port._data = existing._data

        # Add to ports collection
        self.ports[port.id] = port

        if self.wrapper:
            self.wrapper.mark_as_structuraly_dirty()
        self._executor = None

        return port

    @contextmanager
    def group(self, spec: dict):
        """
        Context manager for creating collapsible port groups.

        Creates a special group port with a boolean widget that controls
        visibility of all ports added within the context. Groups can be nested.

        The group itself is a port (boolean inlet) that appears in the node UI.
        When collapsed (False), child ports are hidden but connections are
        preserved and drawn to a ghost pin.

        Args:
            spec: specification dict for group port

        Raises:
            ValueError: If group_port is not an inlet or id already exists

        Yields:
            None (context manager)

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
            with self.group(GROUP.as_inlet('expert', label='Expert Settings', is_expanded=False)):
                self.add(FLOAT.as_inlet('epsilon'))
        """
        # Add group port
        group_port = self.add(spec)

        # Mark as group
        group_port.is_group = True

        # Push group context (all ports added in this context become children)
        self._group_stack.append(group_port.id)
        try:
            yield
        finally:
            self._group_stack.pop()

    @contextmanager
    def section(self, name: str):
        """
        Context manager for organizing ports into property panel sections.

        Sections don't create visible ports in the node itself - they only
        affect how ports are organized in the property panel/inspector.
        This is useful for grouping related configuration options.

        Args:
            name: Section name for property panel

        Yields:
            None (context manager)

        Examples:
            # Ports in validation section
            with self.section('validation'):
                self.add(FLOAT.as_inlet('min_value'))
                self.add(FLOAT.as_inlet('max_value'))
                self.add(BOOL.as_inlet('clamp'))

            # Nested sections and groups
            with self.group('advanced'):
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

        # Step 1: Build include set
        if include is None:
            flagged = set(self.ports.keys())
        elif isinstance(include, str):
            pattern = re.compile(include)
            flagged = {port_id for port_id in self.ports.keys() if pattern.search(port_id)}
        else:
            flagged = set(include) & set(self.ports.keys())

        # Step 2: Apply exclusions
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
                        # Outlet destroyed → do NOT inform sink inlet (asymmetric)
                        edge._update_link_state()
                    edge.redraw()

                # Remove port
                del self.ports[port_id]
                removed.append(port_id)

        self.wrapper.mark_as_structuraly_dirty()
        self._executor = None
        return removed

    @contextmanager
    def rejig(self, include: Optional[List[str] | str] = None, exclude: Optional[List[str] | str] = None):
        """
        Context manager for dynamic port reconfiguration.

        Flags existing ports for potential removal, yields control for
        re-adding ports, then removes any ports that weren't refreshed.
        Edges on refreshed ports are preserved automatically.

        This is the recommended API over raw _push()/_pop() calls — it
        guarantees _pop() runs even if an exception occurs during
        reconfiguration.

        Args:
            include: Ports to flag (applied first):
                - None: Start with all ports
                - List[str]: Start with these specific port IDs
                - str: Regex pattern to match port IDs
            exclude: Ports to exclude from flagging (applied second):
                - None: No exclusions
                - List[str]: Exclude these specific port IDs
                - str: Regex pattern to exclude matching port IDs

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
        """
        Get the unwrapped value of a port for worker access.

        This is the primary method workers use to read port values.
        Returns data in its most convenient form:
        - PrimitiveField: Unwrapped primitive (42.0, "hello")
        - BaseField: BaseType instance (MeshData(...))
        - PooledField: Dict[str, T] of unwrapped values
        - ArrayField: List[T] of unwrapped values

        Args:
            id: The ID of the port

        Returns:
            Unwrapped value appropriate for the field type

        Raises:
            KeyError: If port not found

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
        """
        Set the value of an outlet from worker.

        This is the primary method workers use to write output values.
        Accepts unwrapped values - no need to wrap in IType!

        Args:
            id: The ID of the outlet
            value: Unwrapped value to set

        Raises:
            KeyError: If port not found
            ValueError: If port is not an outlet

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

        port.set_value(value)

        # this indicates to the port that the value was set by the node
        port._is_set_by_node = True

    # =========================================================================
    # Port Querying and Organization
    # =========================================================================

    def _iter_ports(self) -> Iterator[DataPort]:
        """All ports in display order. Single source of ordered iteration."""
        yield from sorted(self.ports.values(), key=lambda p: p.order)

    def iter_visible_ports(self, include_sections: bool = False) -> Iterator[DataPort]:
        """
        Yield ports visible in the node UI (respecting group collapse state).

        Handles:
        - Filtering by group expansion state (collapsed groups hide children)
        - Filtering section-marked ports (optional)
        - Sorted by display order

        Args:
            include_sections: If True, include ports marked with sections.
                            If False, section ports are excluded from node UI
                            (but still available for property panels).

        Yields:
            Visible ports in display order

        Examples:
            # Iterate ports for node rendering
            for port in node.iter_visible_ports():
                render_port(port)

            # Collect as list when needed
            visible = list(node.iter_visible_ports())
        """
        for port in self._iter_ports():
            if not include_sections and port.section:
                continue
            if port.parent_group and self._is_any_ancestor_collapsed(port):
                continue
            yield port

    def get_visible_ports(self, include_sections: bool = False) -> List[DataPort]:
        """Get ports visible in the node UI as a list.

        Convenience wrapper around iter_visible_ports().
        """
        return list(self.iter_visible_ports(include_sections=include_sections))

    def iter_section_ports(self, section: Optional[str] = None) -> Iterator[DataPort]:
        """
        Yield ports that belong to sections, in display order.

        Args:
            section: Specific section name to filter by, or None for all sections

        Yields:
            Section-assigned ports in display order
        """
        for port in self._iter_ports():
            if not port.section:
                continue
            if section is not None and port.section != section:
                continue
            yield port

    def get_section_ports(self, section: Optional[str] = None) -> Dict[str, List[DataPort]]:
        """
        Get ports organized by section for property panel rendering.

        Returns ports grouped by their section assignment, useful for
        building property panels with organized sections.

        Args:
            section: Specific section name to filter by, or None for all sections

        Returns:
            Dict mapping section names to lists of ports in display order

        Examples:
            sections = self.get_section_ports()
            for section_name, ports in sections.items():
                render_section_header(section_name)
                for port in ports:
                    render_property(port)
        """
        sections: Dict[str, List[DataPort]] = {}
        for port in self.iter_section_ports(section):
            sections.setdefault(port.section, []).append(port)
        return sections

    def iter_group_children(self, group_id: str) -> Iterator[DataPort]:
        """
        Yield direct children of a group in display order.

        Args:
            group_id: ID of the group port

        Yields:
            Ports that are direct children of the group
        """
        for port in self._iter_ports():
            if port.parent_group == group_id:
                yield port

    def get_group_children(self, group_id: str) -> List[DataPort]:
        """Get all direct children of a group as a list.

        Convenience wrapper around iter_group_children().
        """
        return list(self.iter_group_children(group_id))

    def is_group_expanded(self, group_id: str) -> bool:
        """
        Check if a group is currently expanded.

        Args:
            group_id: ID of the group port

        Returns:
            True if expanded, False if collapsed

        Raises:
            KeyError: If group not found
            ValueError: If port is not a group
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
        """
        Get ports matching optional filter criteria.

        Only filters by criteria that are explicitly provided (not None).
        If all parameters are None, returns all ports.

        Args:
            is_port_type: Filter by PortType. None = no filter.
            is_flow_type: Filter by flow type (CONTROL, DATA, CALLBACK, NONE). None = no filter.
            is_not_flow_type: Exclude this flow type. None = no filter.
            has_widget: Filter by presence of widget. None = no filter.
            has_pin: Filter by presence of visual pin. None = no filter.
        Returns:
            List of ports matching all specified criteria

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
        """
        Yield ports that are hidden but have active connections, in display order.

        These ports need ghost pins rendered near the title to maintain
        visual connection endpoints. A port is considered hidden if it
        has any ancestor group that is collapsed.

        Args:
            is_inlet: True to get hidden inlets, False for outlets

        Yields:
            Hidden ports with connections, in display order
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
        """Get hidden connected ports as a list.

        Convenience wrapper around iter_hidden_connected_ports().
        """
        return list(self.iter_hidden_connected_ports(is_inlet))

    def _is_any_ancestor_collapsed(self, port: DataPort) -> bool:
        """
        Check if any ancestor group in the port's hierarchy is collapsed.

        Traverses the parent chain from the port up to the root,
        checking if any group along the way is collapsed.

        Args:
            port: The port to check

        Returns:
            True if any ancestor group is collapsed, False otherwise
        """
        current_group_id = port.parent_group

        while current_group_id is not None:
            group_port = self.ports.get(current_group_id)
            if not group_port:
                # Broken hierarchy - assume visible
                break

            # Check if this group is collapsed
            try:
                if not self.value(current_group_id):
                    return True
            except (KeyError, Exception):
                # If we can't get state, assume expanded
                pass

            # Move up to parent group
            current_group_id = group_port.parent_group

        return False

    def get_port_hierarchy(self, port_id: str) -> str:
        """
        Get the hierarchical path of a port from bottom to root.

        Returns a string showing the port hierarchy delineated with '>>'
        and ending with 'root' when there is no parent group.

        Args:
            port_id: ID of the port to get hierarchy for

        Returns:
            Hierarchy string in format 'port_id>>parent_id>>root'

        Raises:
            KeyError: If port_id not found

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

        # Build hierarchy from bottom up
        hierarchy_parts = [port_id]
        current_port = port

        # Traverse up the parent chain
        while current_port.parent_group is not None:
            parent_id = current_port.parent_group
            parent_port = self.ports.get(parent_id)

            if not parent_port:
                # Parent group not found - broken hierarchy
                break

            hierarchy_parts.append(parent_id)
            current_port = parent_port

        # Add 'root' at the end
        hierarchy_parts.append("root")

        return ">>".join(hierarchy_parts)

    def mark_port_as_dirty(self, port: DataPort) -> None:
        """
        Called by ports when their value changes to indicate
        the requirement for executing the worker method
        """
        self._has_dirty_ports.add(port)

    # =========================================================================
    # Worker Signature Analysis and Execution
    # =========================================================================

    def _analyze_worker_signature(self) -> None:
        """
        Analyze worker signature and create optimized extractor.
        Called after ports are configured (end of initialize or after port changes).
        """
        worker_method = getattr(self, "worker", None)
        if not worker_method:
            return

        sig = inspect.signature(worker_method)
        params = dict(sig.parameters)
        params.pop("self", None)
        params.pop("context", None)

        if not params:
            # Legacy: no params, call worker(context) directly
            self._executor = lambda ctx: self.worker(ctx)
            return

        # Collect params that have matching ports (in signature order)
        param_names_with_ports = []

        for name, param in params.items():
            has_port = name in self.ports
            is_required = param.default is inspect.Parameter.empty

            if is_required and not has_port:
                raise ValueError(f"Required worker parameter '{name}' has no matching port.")

            if has_port:
                param_names_with_ports.append(name)

        self._executor = self._create_executor(param_names_with_ports)

    def _create_executor(self, param_names: List[str]) -> Callable:
        """
        Create optimized executor based on port count.

        Returns:
            Executor callable that combines extraction + worker call
        """
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
                ctx,
                p0.get_value(),
                p1.get_value(),
                p2.get_value(),
                p3.get_value(),
            )
        elif n == 5:
            p0, p1, p2, p3, p4 = ports
            return lambda ctx: self.worker(
                ctx,
                p0.get_value(),
                p1.get_value(),
                p2.get_value(),
                p3.get_value(),
                p4.get_value(),
            )
        else:
            # Reusable dict fallback for 6+ ports
            cache = {name: None for name in param_names}
            port_refs = list(zip(param_names, ports))

            def extract_dict():
                for name, port in port_refs:
                    cache[name] = port.get_value()
                return cache

            return lambda ctx: self.worker(ctx, **extract_dict())

    def _parse_worker_result(self, result: str | None) -> str | None:
        """Parse worker result - just flow control."""
        if result is not None and not isinstance(result, str):
            raise ValueError(
                f"Worker must return str (outlet ID) or None, got {type(result).__name__}: {result!r}"
            )
        return result

    # =========================================================================
    # SERIALIZATION
    # =========================================================================

    def _serialize_ports(self, include_data: bool = True) -> Dict[str, Any]:
        """
        Serialize all ports to dictionary, optionally with data.

        Args:
            include_data: If True, includes field values

        Returns:
            Dictionary mapping port IDs to PortSpec-format dicts
        """
        return {port_id: port.to_dict(include_data=include_data) for port_id, port in self.ports.items()}

    def _deserialize_ports(self, ports_data: Dict[str, Any]) -> bool:
        """
        Deserialize ports from PortSpec-format dictionaries.

        Uses the same _instantiate_port_from_spec() path as add(),
        ensuring consistent port creation.

        Args:
            ports_data: Dictionary of PortSpec-format port data

        Returns:
            True if deserialization succeeded
        """
        # Clear existing ports
        self.ports.clear()
        self._port_order_counter = 0

        # Recreate each port from PortSpec
        for port_id, spec in ports_data.items():
            # Use same instantiation path as add()
            port = DataPort.from_spec(spec, self._type_registry, self.wrapper, self)

            # Add directly to collection (skip add() to preserve order from spec)
            self.ports[port.id] = port

            # Update order counter
            if port.order >= self._port_order_counter:
                self._port_order_counter = port.order + 1

        self._executor = None
        return True


class BaseNode(NodeData, metaclass=NodeMeta):
    """
    Base class for all Haywire nodes.

    Combines NodeData (port management) with node lifecycle and execution.
    Subclasses must implement the worker() method for execution logic.

    The new architecture provides clean API:
    - inlet(id) - Get unwrapped value
    - set_outlet(id, value) - Set unwrapped value
    - No manual wrapping/unwrapping needed!

    Important: Nodes in modules that start with dev_*.py or end with *_dev.py are not
    automatically registered in the node registry. On a File change though they will
    be loaded and are available.
    This is useful for nodes under development that should not yet be part of the library.
    """

    class props(NodeProperties):
        """Per-instance observable props (muted, collapsed, skin, position, …)."""

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
            port = self._has_dirty_ports.pop()
            port.resolve_dirty_data()

        self.on_validate(context)

        if self._executor is None:
            self._analyze_worker_signature()

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
        self.on_teardown()
        self._store.clear()
        # Clean up settings bags (release global namespace subscriptions)
        for bag_name in getattr(type(self), "_settings_bags", {}):
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
            "settings": {
                name: getattr(self, name).to_dict() for name in getattr(type(self), "_settings_bags", {})
            },
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
        # Deserialize ports (uses existing deserialize_ports method)
        if "ports" in data:
            self._deserialize_ports(data["ports"])

        # Restore settings bags
        for bag_name, bag_data in data.get("settings", {}).items():
            bag = getattr(self, bag_name, None)
            if isinstance(bag, Settings):
                bag.from_dict(bag_data)

        # Restore reactive props
        if "props" in data:
            self.props.from_dict(data["props"])

        if "store" in data:
            self._store.from_dict(data["store"])
