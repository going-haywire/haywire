from __future__ import annotations
import inspect
from typing import TYPE_CHECKING, Any, Callable, Dict, TypeVar, Union
from abc import abstractmethod
from dataclasses import dataclass, field, asdict

from ..data.enums import FlowType
from ..execution.execution_context import ExecutionContext
from ..registry.identity import BaseIdentity
from ..library.identity import LibraryIdentity
from ..types.ports import DataPort
from .dataclasses import (
    NodeBehavior, 
    NodeErrorInfo, 
    NodeUIConfig, 
    NodeUIState, 
    NodeUserMetadata
)

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper

T = TypeVar('T')

# Worker return type: None | str | (str | None, tuple of (outlet_id, value) pairs)
WorkerResult = (
    None | str | tuple[str | None, tuple[tuple[str, Any], ...]]
)

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
    # IDENTITY ATTRIBUTES (set by @type decorator)
    class_identity: NodeIdentity
    class_library: LibraryIdentity
    
    def __init__(self, node_id: str, wrapper: NodeWrapper):
        """Initialize unified port collection and management state"""

        self.node_id = node_id
        self.wrapper = wrapper

        # Port storage
        self.ports: Dict[str, DataPort] = {}
        """Single source of truth for all ports (inlets and outlets)"""
        
        self._cache_dirty = True
        """Flag indicating port cache needs rebuilding"""
        
        # Dynamic reconfiguration state (transient - not serialized)
        self._push_stack: List[Set[str]] = []
        """Stack of port ID sets for push/pop operations"""
        
        # Grouping state (transient - not serialized)
        self._group_stack: List[str] = []
        """Stack of active group IDs for nested groups"""
        
        self._section_stack: List[str] = []
        """Stack of active section names for property organization"""
        
        self._port_order_counter: int = 0
        """Counter for assigning display order to ports"""

        # Worker execution cache
        self._executor: Optional[Callable] = None
        """Optimized execution callable (combines extraction + worker call)"""

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

    def add(self, port: DataPort) -> DataPort:
        """
        Add a port (inlet or outlet) to the node with automatic hierarchy tracking.
        
        This is the primary method for adding ports. It automatically:
        - Assigns the port to the current group (if in a group context)
        - Assigns the port to the current section (if in a section context)
        - Assigns a display order
        - Preserves connections if replacing an existing port (during reconfiguration)
        - Unflags the port if in a push/pop context
        
        Args:
            port: DataPort to add (PortInlet or PortOutlet)
        
        Returns:
            The added port
        
        Raises:
            ValueError: If port ID already exists (unless in push/pop context)
        
        Examples:
            # Simple port
            self.add(FLOAT.as_inlet('value'))
            
            # Port in group
            with self.group('advanced'):
                self.add(FLOAT.as_inlet('param'))  # Auto-assigned to 'advanced' group
            
            # Port with section
            with self.section('validation'):
                self.add(FLOAT.as_inlet('tolerance'))  # Auto-assigned to 'validation' section
        """
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
            port._edges = existing._edges.copy()
            port._edge_wrappers = existing._edge_wrappers.copy()
        
        # Add to ports collection
        self.ports[port.id] = port
        
        port._wrapper = self.wrapper

        self._cache_dirty = True

        self.wrapper.mark_as_structuraly_dirty()
        self._executor = None

        return port
    
    @contextmanager
    def group(self, group_port: DataPort):
        """
        Context manager for creating collapsible port groups.
        
        Creates a special group port with a boolean widget that controls
        visibility of all ports added within the context. Groups can be nested.
        
        The group itself is a port (boolean inlet) that appears in the node UI.
        When collapsed (False), child ports are hidden but connections are
        preserved and drawn to a ghost pin.
        
        Args:
            group_port: DataPort as group (PortInlet or PortOutlet)

        Raises:
            ValueError: If group_port is not an inlet or id already exists
        
        Yields:
            None (context manager)
        
        Examples:
            # Simple group
            with self.group('advanced', label='Advanced Options'):
                self.add(FLOAT.as_inlet('param1'))
                self.add(FLOAT.as_inlet('param2'))
            
            # Nested groups
            with self.group('input', label='Input Configuration'):
                self.add(FLOAT.as_inlet('value'))
                
                with self.group('validation', label='Validation'):
                    self.add(BOOL.as_inlet('validate'))
                    self.add(FLOAT.as_inlet('tolerance'))
            
            # Initially collapsed
            with self.group('expert', label='Expert Settings', is_expanded=False):
                self.add(FLOAT.as_inlet('epsilon'))
        """
        
        # Mark as group
        group_port.is_group = True
        
        # Add group port
        self.add(group_port)
        
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
        self._cache_dirty = True
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
        if port.is_inlet():
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
            if port.flow_type == FlowType.CONTROL and port.is_outlet()
        ]
    
    def get_control_inlets(self) -> list[DataPort]:
        """
        Get all control inlet ports (EXEC type inlets).
        
        Returns:
            List of control inlet ports
        """
        return [
            port for port in self.ports.values()
            if port.flow_type == FlowType.CONTROL and port.is_inlet()
        ]
    
    def get_callback_outlets(self) -> list[DataPort]:
        """
        Get all callback outlet ports (CALLBACK type outlets).
        
        Returns:
            List of callback outlet ports with event_filter
        """
        return [
            port for port in self.ports.values()
            if port.flow_type == FlowType.CALLBACK and port.is_outlet()
        ]

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

    def _parse_worker_result(self, result: Any) -> Optional[str]:
        """
        Parse worker function result to extract next outlet ID.
        
        Strict pattern - exceptions on invalid format:
        - None: No continuation, no outputs
        - str: Control flow to outlet_id, no outputs
        - (str | None, tuple): Control flow + outputs
            - First element: outlet_id for control flow (or None)
            - Second element: tuple of (outlet_id, value) pairs (can be empty)
        
        Args:
            result: Worker function return value
            
        Returns:
            Outlet ID to follow, or None
            
        Raises:
            ValueError: If result doesn't match expected pattern
            
        Examples:
            return None  # No flow, no outputs
            return 'next'  # Flow only
            return ('next', ())  # Flow, no outputs (explicit)
            return (None, (('out1', 10), ('out2', 20)))  # Outputs, no flow
            return ('next', (('out1', 10), ('out2', 20)))  # Flow + outputs
        """
        if result is None:
            return None
                
        if isinstance(result, str):
            return result
        
        try:
            next_outlet, outputs = result
                       
            # Set all outputs
            for item in outputs:
                outlet_id, value = item
                self.out(outlet_id, value)
            
            return next_outlet
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"Worker result must be None, str, or (str|None, tuple), "
                f"got {type(result)}"
            ) from e

    @abstractmethod
    def worker(self, context: ExecutionContext, *args, **kwargs) -> WorkerResult:
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
            WorkerResult:
            - None  # No flow, no outputs
            - 'next'  # Flow only
            - ('next', ())  # Flow, no outputs (explicit)
            - (None, (('out1', 10), ('out2', 20)))  # Outputs, no flow
            - ('next', (('out1', 10), ('out2', 20)))  # Flow + outputs
        
        Examples:
            Simple node with required inputs:
            
            .. code-block:: python
            
                def worker(self, context, value: float, multiplier: float):
                    result = value * multiplier
                    return (None, (('result', result),))
            
            Node with optional inputs (default if port missing):
            
            .. code-block:: python
            
                def worker(self, context, value: float, offset: float = 0.0):
                    result = value + offset
                    return (None, (('result', result),))
            
            Control flow node:
            
            .. code-block:: python
            
                def worker(self, context, condition: bool):
                    return 'true_branch' if condition else 'false_branch'
            
            Multi-output with control flow:
            
            .. code-block:: python
            
                def worker(self, context, x: float, y: float):
                    return ('next', (
                        ('sum', x + y),
                        ('product', x * y),
                        ('difference', x - y),
                    ))
            
            No parameters (slower, access via self.value()):
            
            .. code-block:: python
            
                def worker(self, context):
                    value = self.value('input')
                    self.out('output', value * 2)
                    return None
            """
        pass

    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def _serialize_ports(self) -> Dict[str, Any]:
        """
        Serialize all ports to dictionary.
        
        Returns:
            Dictionary mapping port IDs to serialized port data
        """
        return {port_id: port.to_dict() for port_id, port in self.ports.items()}
    
    def _deserialize_ports(self, ports_data: Dict[str, Any]) -> bool:
        """
        Deserialize ports from dictionary and restore them.
        
        This recreates ports using their from_dict() method, which replays
        the original creation call from the recipe format.
        
        Args:
            ports_data: Dictionary of serialized port data
            
        Returns:
            True if deserialization succeeded, False otherwise
        Raises:
            ValueError: If deserialization fails
        """
        from haywire.core.types.ports import DataPort
        from haywire.core.di.config import get_library_system
        type_registry = get_library_system().get_type_registry()
        # Clear existing ports
        self.ports.clear()
        self._port_order_counter = 0
        
        # Recreate each port from serialized data
        for port_id, port_data in ports_data.items():
            # Use DataPort.from_dict() to recreate the port
            port = DataPort.from_dict(port_data, type_registry)
            
            # Add to ports collection
            self.ports[port_id] = port
            port._wrapper = self.wrapper
            
            # Update order counter
            if port.order >= self._port_order_counter:
                self._port_order_counter = port.order + 1
        
        self._cache_dirty = True
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
        self.error_info: NodeErrorInfo | None = None
        
        self.behavior = NodeBehavior()
        self.ui_config = NodeUIConfig()
        self.ui_state = NodeUIState()
        self.metadata = NodeUserMetadata()
    
    @property
    def identity(self) -> NodeIdentity:
        """Get node identity from class"""
        return self.__class__.class_identity
    
    @property
    def library(self) -> LibraryIdentity:
        """Get library identity from class"""
        return self.__class__.class_library
    
    @abstractmethod
    def initialize(self):
        """
        Initialize Node to its default setup

        This method needs to be overwritten by every node and is
        called when the node is created or rebuilt.
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

    def startup(self) -> None:
        """
        Perform any startup logic when the node is executing for the first time.
        It is called once before the first execution of the worker.
        
        Override this method in subclasses to implement custom startup logic.
        """
        pass


    def shutdown(self) -> None:
        """
        Perform any shutdown logic when the graph stops executing.
        
        Override this method in subclasses to implement custom shutdown logic.
        """
        pass

    def destroy(self) -> None:
        """
        Clean up resources when node is destroyed.
        
        Override this method in subclasses to implement custom cleanup logic.
        This is called when the node is removed from the graph and should
        release any resources held by the node.
        """
        pass

    def _to_dict(self) -> dict:
        """
        Serialize node to dictionary.
        
        Returns:
            Dict representation of the node
        """
        return {
            'node_id': self.node_id,
            'registry_key': self.identity.registry_key,
            'library': asdict(self.library) if self.library else None,
            'identity': asdict(self.identity),
            'behavior': asdict(self.behavior),
            'ui_config': asdict(self.ui_config),
            'ui_state': asdict(self.ui_state),
            'metadata': asdict(self.metadata),
            'ports': self._serialize_ports()  # Delegate to NodeData
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
        - metadata.custom IS a defined field, so it IS fully preserved!
        - All user data in metadata.custom dict will be restored correctly
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
        # Helper to restore fields from dict to dataclass
        def restore_dataclass_fields(target_obj, source_dict):
            """
            Restore dataclass fields from dictionary.
            Only sets fields that exist in the dataclass definition.
            
            Important: This DOES restore dict/list fields completely!
            - metadata.custom dict → Fully restored with all contents
            - metadata.notes list → Fully restored with all items
            """
            for key, value in source_dict.items():
                if hasattr(target_obj, key):
                    setattr(target_obj, key, value)
                # Silently ignore unknown fields for forward compatibility
        
        # Restore dataclass fields from serialized data
        if 'identity' in data:
            restore_dataclass_fields(self.identity, data['identity'])
        
        if 'behavior' in data:
            restore_dataclass_fields(self.behavior, data['behavior'])
        
        if 'ui_config' in data:
            restore_dataclass_fields(self.ui_config, data['ui_config'])
        
        if 'ui_state' in data:
            restore_dataclass_fields(self.ui_state, data['ui_state'])
        
        if 'metadata' in data:
            restore_dataclass_fields(self.metadata, data['metadata'])
        
        # Deserialize ports (uses existing deserialize_ports method)
        if 'ports' in data:
            self._deserialize_ports(data['ports'])
