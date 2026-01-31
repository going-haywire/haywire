from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import asdict, dataclass, field
from abc import abstractmethod
from contextlib import contextmanager

from haywire.core.execution.event_source import EventSource
from haywire.core.settings.builtins import register_node_instance_settings

from ..data.enums import FlowType
from ..execution.execution_context import ExecutionContext
from ..registry.identity import BaseIdentity
from ..library.identity import LibraryIdentity
from ..types.ports import DataPort
from .behavior import NodeBehaviorFlags
from .user_data import NodeCache, NodeStore
from .ui_state import NodeUI, NodeUIState
from haywire.core.settings import SettingsHolder

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper
    from haywire.core.types.registry import TypeRegistry

T = TypeVar('T')


T = TypeVar('T')

@dataclass
class NodeIdentity(BaseIdentity):
    """Core identifying attributes of a node"""
    search_tags: list[str] = field(default_factory=lambda: ['add', 'sub', 'math', 'vector'])
    menu: str = 'misc/custom'
    help_md: str | None = None
    help_url: str = 'https://haywire.io/docs/node-help'
    _is_error: bool = False
    _error_priority: int = 0


class NodeMeta(type):
    """Metaclass for nodes"""
    def __new__(cls, name, bases, attrs):
        new_class = super().__new__(cls, name, bases, attrs)
        return new_class


from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Set

class NodeData:
    """
    Node data management with unified port collection and dynamic reconfiguration.
    
    Provides:
    - Unified port storage (inlets and outlets in single dict)
    - Dynamic port reconfiguration (push/pop pattern)
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
        from haywire.core.di.config import get_library_system

        self.node_id = node_id
        self.wrapper = wrapper

        self.event_subscription: EventSource | None = None 
        # TODO: CallbackSystem
        """event nodes store here the event subscription"""
        
        # Cache type registry for port instantiation
        self._type_registry: 'TypeRegistry' = (
            get_library_system().get_type_registry()
        )
        
        # ---------------------------------------------------------------------
        # Core containers
        # ---------------------------------------------------------------------
        
        # Ports
        self.ports: Dict[str, DataPort] = {}
        """Single source of truth for all ports (inlets and outlets)."""
        
        # Settings (GUI-facing, serialized)
        self._settings: SettingsHolder = SettingsHolder(
            registry=get_library_system().get_settings_registry(),
            owner=wrapper,
            owner_name=f"Node:{node_id}"
        )
        # Register node-instance-specific local settings
        register_node_instance_settings(self._settings)
        
        # Cache (transient, NOT serialized)
        self._cache: NodeCache = NodeCache()
        
        # Store (persistent, serialized, NOT GUI-facing)
        self._store: NodeStore = NodeStore()
        
        # UI state (position, dimensions)
        self._ui: NodeUI = NodeUI(self)
        

        # ---------------------------------------------------------------------
        # Internal state
        # ---------------------------------------------------------------------
               
        self._push_stack: List[set[str]] = []
        """Stack of port ID sets for push/pop operations."""
        
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

    @property
    def settings(self) -> SettingsHolder:
        """
        Access node settings with dynaconf-style API.
        
        Examples:
            # Read resolved value
            color = self.settings.ui.node.bg_color
            color = self.settings['ui.node.bg_color']
            
            # Write local override
            self.settings.ui.node.bg_color = '#ff0000'
            self.settings['ui.node.bg_color'] = '#ff0000'
            
            # Check if globally overridden
            info = self.settings.get_info('ui.node.bg_color')
            if info.is_overridden:
                # Cannot change locally
                pass
            
            # Reset to inherit from global
            self.settings.reset('ui.node.bg_color')
            
            # Define local-only setting
            self.settings.define('my_cache_size', 100, scope=SettingScope.LOCAL_ONLY)
        """
        return self._settings

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
    
    @property
    def ui(self) -> NodeUI:
        """
        UI state container.
        
        Contains position, dimensions, and convenience methods
        for collapse/expand/mute operations.
        
        Example:
            self.ui.set_position(100, 200)
            self.ui.collapse()
        """
        return self._ui
    
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
        - Unflags the port if in a push/pop context
        
        Args:
            spec: specification dict
        
        Returns:
            The added DataPort
        
        Raises:
            ValueError: If port ID already exists (unless in push/pop context)
        
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
        port = DataPort.from_spec(
            spec, 
            self._type_registry, 
            self.wrapper
        )

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
            port._edge_wrappers = existing._edge_wrappers.copy()
        
        # Add to ports collection
        self.ports[port.id] = port

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
    
    def push(self, filter_ids: Optional[List[str]] = None) -> None:
        # TODO: More sophisticated filtering...
        """
        Mark existing ports for potential removal (start of reconfiguration).
        
        Flags all ports (or a filtered subset) as candidates for removal.
        Ports that are re-added via add() before pop() is called will be
        preserved with their connections intact. Ports not re-added will
        be removed by pop().
        
        This enables dynamic port reconfiguration based on user input while
        preserving connections to ports that remain.
        
        Args:
            filter_ids: Optional list of port IDs to flag. If None, flags all ports.
        
        Examples:
            # Flag all ports
            self.push()
            self.add(FLOAT.as_inlet('value'))  # Refreshed, not removed
            removed = self.pop()  # Removes all other ports
            
            # Flag specific ports
            self.push(['old_param1', 'old_param2'])
            self.add(FLOAT.as_inlet('new_param'))
            removed = self.pop()  # Only removes old_param1 and old_param2
            
            # Preserve static ports
            mode = self.value('mode_selector')
            self.push()  # Flags all ports
            
            # Re-add static ports (won't be removed)
            self.add(STRING.as_inlet('mode_selector', ...))
            
            # Add dynamic ports based on mode
            if mode == 'simple':
                self.add(FLOAT.as_inlet('value'))
            elif mode == 'advanced':
                self.add(FLOAT.as_inlet('min'))
                self.add(FLOAT.as_inlet('max'))
            
            removed = self.pop()  # Removes only ports not re-added
        """
        if filter_ids is None:
            # Flag all current ports
            flagged = set(self.ports.keys())
        else:
            # Flag only specified ports that exist
            flagged = set(filter_ids) & set(self.ports.keys())
        
        self._push_stack.append(flagged)
    
    def pop(self) -> List[str]:
        """
        Remove flagged ports that weren't refreshed (end of reconfiguration).
        
        Completes a push/pop reconfiguration cycle by removing all ports
        that were flagged by push() and not re-added. Connections to removed
        ports are cleaned up automatically.
        
        Returns:
            List of removed port IDs
        
        Raises:
            RuntimeError: If pop() called without matching push()
        
        Examples:
            self.push()
            # ... reconfigure ports ...
            removed = self.pop()
            if removed:
                print(f"Removed ports: {removed}")
        """
        if not self._push_stack:
            raise RuntimeError("pop() called without matching push()")
        
        flagged = self._push_stack.pop()
        removed = []
        
        for port_id in flagged:
            if port_id in self.ports:
                port = self.ports[port_id]
                
                # Clean up all connections
                port._clear_all_links()
                
                # Remove port
                del self.ports[port_id]
                removed.append(port_id)

                self.wrapper.mark_as_structuraly_dirty()
        
        self._executor = None
        return removed

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
        if port.is_inlet:
            raise ValueError(f"Port '{id}' is not an outlet")
        
        port.set_value(value)

    # =========================================================================
    # Port Querying and Organization
    # =========================================================================

    def get_visible_ports(self, 
                          include_sections: bool = False) -> List[DataPort]:
        """
        Get ports visible in the node UI (respecting group collapse state).
        
        Returns only ports that should be rendered in the node's visual
        representation. Handles:
        - Filtering by group expansion state (collapsed groups hide children)
        - Filtering section-marked ports (optional)
        - Sorting by display order
        
        Args:
            include_sections: If True, include ports marked with sections.
                            If False, section ports are excluded from node UI
                            (but still available for property panels).
        
        Returns:
            List of visible ports in display order
        
        Examples:
            # Get ports for node rendering
            visible = self.get_visible_ports()
            for port in visible:
                render_port(port)
            
            # Include section ports for property panel
            all_ui_ports = self.get_visible_ports(include_sections=True)
        """
        visible = []
        
        for port in sorted(self.ports.values(), key=lambda p: p.order):
            
            # Skip section-marked ports if not requested
            if not include_sections and port.section:
                continue
            
            # Check if parent groups are expanded
            if port.parent_group:
                parent = self.ports.get(port.parent_group)
                if parent:
                    # Parent exists - check if expanded
                    try:
                        is_expanded = self.value(port.parent_group)
                        if not is_expanded:
                            # Parent group is collapsed, skip this port
                            continue
                    except (KeyError, Exception):
                        # If we can't get parent state, assume visible
                        pass
            
            visible.append(port)
        
        return visible
    
    def get_section_ports(self, 
                         section: Optional[str] = None) -> Dict[str, List[DataPort]]:
        """
        Get ports organized by section for property panel rendering.
        
        Returns ports grouped by their section assignment, useful for
        building property panels with organized sections.
        
        Args:
            section: Specific section name to filter by, or None for all sections
        
        Returns:
            Dict mapping section names to lists of ports in display order
        
        Examples:
            # Get all sections
            sections = self.get_section_ports()
            # Returns: {
            #     'validation': [port1, port2],
            #     'performance': [port3, port4]
            # }
            
            # Get specific section
            validation_ports = self.get_section_ports('validation')
            # Returns: {'validation': [port1, port2]}
            
            # Render property panel
            sections = self.get_section_ports()
            for section_name, ports in sections.items():
                render_section_header(section_name)
                for port in ports:
                    render_property(port)
        """
        sections = {}
        
        for port in sorted(self.ports.values(), key=lambda p: p.order):
            
            # Only process ports with section assignment
            if port.section:
                section_name = port.section
                
                # Filter by requested section if specified
                if section is None or section_name == section:
                    if section_name not in sections:
                        sections[section_name] = []
                    sections[section_name].append(port)
        
        return sections
    
    def get_group_children(self, group_id: str) -> List[DataPort]:
        """
        Get all direct children of a group.
        
        Args:
            group_id: ID of the group port
        
        Returns:
            List of ports that are direct children of the group
        
        Examples:
            # Get children of a group
            children = self.get_group_children('advanced')
            print(f"Group has {len(children)} children")
        """
        return [
            port for port in sorted(self.ports.values(), key=lambda p: p.order)
            if port.parent_group == group_id
        ]
    
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

    def get_control_outlets(self) -> list[DataPort]:
        """
        Get all control outlet ports (EXEC type outlets).
        
        Returns:
            List of control outlet ports
        """
        return [
            port for port in self.ports.values()
            if port.flow_type == FlowType.CONTROL and port.is_outlet
        ]
    
    def get_control_inlets(self) -> list[DataPort]:
        """
        Get all control inlet ports (EXEC type inlets).
        
        Returns:
            List of control inlet ports
        """
        return [
            port for port in self.ports.values()
            if port.flow_type == FlowType.CONTROL and port.is_inlet
        ]
    
    def get_callback_outlets(self) -> list[DataPort]:
        """
        Get all callback outlet ports (CALLBACK type outlets).
        
        Returns:
            List of callback outlet ports
        """
        return [
            port for port in self.ports.values()
            if port.flow_type == FlowType.CALLBACK and port.is_outlet
        ]

    def get_hidden_connected_ports(self, is_inlet: bool) -> List[DataPort]:
        """
        Get ports that are hidden but have active connections.
        
        These ports need ghost pins rendered near the title to maintain
        visual connection endpoints. A port is considered hidden if:
        - It's not in the visible ports list, OR
        - Any ancestor group in its hierarchy is collapsed
        
        Args:
            is_inlet: True to get hidden inlets, False for outlets
            
        Returns:
            List of hidden ports with connections, sorted by order
        """
        visible_ports = self.get_visible_ports()
        visible_port_ids: Set[str] = {port.id for port in visible_ports}
        
        hidden_connected: List[DataPort] = []
        
        for port in self.ports.values():
            # Skip if wrong direction
            if port.is_inlet != is_inlet:
                continue
            
            # Skip section markers and group ports
            if port.section or port.is_group:
                continue
            
            # Check if port is truly hidden (not visible OR any ancestor collapsed)
            is_hidden = port.id not in visible_port_ids
            
            # Also check full ancestor chain for collapsed groups
            if not is_hidden:
                is_hidden = self._is_any_ancestor_collapsed(port)
            
            # Include if port is hidden and has connections
            if is_hidden and port.is_linked():
                hidden_connected.append(port)
        
        return sorted(hidden_connected, key=lambda p: p.order)
    
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
        hierarchy_parts.append('root')
        
        return '>>'.join(hierarchy_parts)

    # =========================================================================
    # Worker Signature Analysis and Execution
    # =========================================================================

    def _analyze_worker_signature(self) -> None:
        """
        Analyze worker signature and create optimized extractor.
        Called after ports are configured (end of initialize or after port changes).
        """
        worker_method = getattr(self, 'worker', None)
        if not worker_method:
            return
        
        sig = inspect.signature(worker_method)
        params = dict(sig.parameters)
        params.pop('self', None)
        params.pop('context', None)
        
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
                raise ValueError(
                    f"Required worker parameter '{name}' has no matching port."
                )
            
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
            return lambda ctx: self.worker(
                ctx, p0.get_value(), p1.get_value()
            )
        elif n == 3:
            p0, p1, p2 = ports
            return lambda ctx: self.worker(
                ctx, p0.get_value(), p1.get_value(), p2.get_value()
            )
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
    
    def execute(self, context: 'ExecutionContext') -> Optional[str]:
        """
        Execute the worker with optimized value extraction.
        
        This is the single entry point

        Args:
            context: Execution context
        
        Returns:
            Outlet ID to follow, or None
        """
        if self._executor is None:
            self._analyze_worker_signature()

        result = self._executor(context)
        return self._parse_worker_result(result)

    def _parse_worker_result(self, result: str | None) -> str | None:
        """Parse worker result - just flow control."""
        if result is not None and not isinstance(result, str):
            raise ValueError(
                f"Worker must return str (outlet ID) or None, "
                f"got {type(result).__name__}: {result!r}"
            )
        return result

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

    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def _serialize_ports(self) -> Dict[str, Any]:
        """
        Serialize all ports to dictionary.
        
        Returns:
            Dictionary mapping port IDs to PortSpec-format dicts
        """
        return {port_id: port.to_dict() for port_id, port in self.ports.items()}
    
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
            port = DataPort.from_spec(spec, self._type_registry, self.wrapper)
            
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
    """
    
    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        """
        Initialize node.
        
        Args:
            node_id: Unique identifier for this node instance
            wrapper: NodeWrapper managing this node
        """
        super().__init__(node_id, wrapper)

    
    @abstractmethod
    def initialize(self):
        """
        Initialize Node to its default setup

        This method needs to be overwritten by every node and is
        called when the node is created or rebuilt. It should be only used to
        add ports and set default values. 
        
        For any setup that depends on the current port configuration, 
        use the setup() method.
        """
        pass

    def setup(self) -> None:
        """
        Perform any setup logic after ports are configured.
        
        This method is called right after 
            - initialize() or
            - the deserialization of ports after a load operation.
        
        It should be used to perform any additional setup that
        depends on the current port configuration.

        Do not use it for performative operations or as a preparation for the
        worker execution - the startup() method should be used for that purpose.

        Override this method in subclasses to implement custom setup logic.
        """
        pass

    def test_run(self) -> tuple[bool, str | None]:
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

    def on_changed_async(self, context: ExecutionContext) -> None:
        """
        Handle asynchronous changes to the node.
        
        This method needs to be overridden when the node's configuration changes
        in a way that requires asynchronous handling, such as updating
        external resources or performing long-running tasks.
        
        Override this method in subclasses to implement custom async change handling.
        """
        pass

    def on_validation_input(self, context: ExecutionContext) -> None:
        """
        Handle validation of inputs before execution.
        
        This method is called to validate input values before the node
        executes. It can be used to check for valid ranges, types,
        or other constraints on input data.
        
        Override this method in subclasses to implement custom input validation.

        TODO: what shall we do on validation failure? Raise exception?
        """
        pass

    def startup(self, context: ExecutionContext) -> None:
        """
        Perform any startup logic when the node is executing for the first time.
        It is called once before the first execution of the worker.
        
        Override this method in subclasses to implement custom startup logic.
        """
        pass


    def shutdown(self, context: ExecutionContext) -> None:
        """
        Perform any shutdown logic when the graph stops executing.
        
        Override this method in subclasses to implement custom shutdown logic.
        """
        pass

    def teardown(self) -> None:
        """
        Clean up resources when node is destroyed.
        
        Override this method in subclasses to implement custom cleanup logic.
        This is called when the node is removed from the graph and should
        release any resources held by the node.
        """
        pass


    def _cleanup(self) -> None:
        """Clean up resources when node is destroyed."""
        self.teardown()
        # Clean up settings
        self._settings.cleanup()        

    # =========================================================================
    # SERIALIZATION (updated)
    # =========================================================================

    def _to_dict(self) -> dict:
        """
        Serialize node to dictionary. 
        This also includes identity and library info.
        
        Returns:
            Dict representation of the node
        """
        return {
            'node_id': self.node_id,
            'ports': self._serialize_ports(),
            'settings': self._settings.to_dict(),
            'store': self._store.to_dict(),
            'ui': self._ui.to_dict(),
            'identity': self.identity.to_dict(),
            'library': self.library.to_dict(),
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
        if 'ports' in data:
            self._deserialize_ports(data['ports'])

        # Restore settings
        if 'settings' in data:
            self._settings.from_dict(data['settings'])

        if 'store' in data:
            self._store.from_dict(data['store'])
        
        if 'ui' in data:
            self._ui.from_dict(data['ui'])
        
