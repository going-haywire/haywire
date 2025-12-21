"""
EdgeWrapper - Complete lifecycle management for Haywire edges.

This wrapper manages the complete lifecycle of an Edge instance,
including creation, adapter chain management, hot reload, validation,
serialization, and cleanup.

Parallel to NodeWrapper design.
"""

import logging
import time
from typing import Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from .edge import Edge, EdgeType
from ..adapter.chain import AdapterChain
from ..errors import HaywireException
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from ..types.ports import DataPort

if TYPE_CHECKING:
    from .base import BaseGraph
    from ..adapter.factory import AdapterFactory
    from ..node.node_wrapper import NodeWrapper

logger = logging.getLogger(__name__)


@dataclass
class EdgeWrapperState:
    """Lifecycle state of wrapper and its edge instance"""
    is_registered: bool = False
    """The edge has been registered with the graph"""
    is_valid: bool = True
    """The edge connection is valid (adapter chain exists)"""
    is_executing: bool = False
    """Edge is currently transforming data"""
    last_hot_reload: float = 0.0
    """Timestamp of last adapter hot reload"""
    history: List[LifeCycleEvent] = field(default_factory=list)
    """Lifecycle event history"""
    error: Optional[HaywireException] = None
    """Current error state"""
    creation_time: float = 0.0
    """When edge was created"""
    execution_count: int = 0
    """Number of times transform() was called"""
    hot_reload_count: int = 0
    """Number of adapter chain rebuilds"""
    chain_changed_warning: bool = False
    """True if adapter chain changed during hot reload"""


class EdgeWrapper:
    """
    Manages the complete lifecycle of an Edge instance.
    
    Responsibilities:
    - Edge instance management and lifecycle
    - Adapter chain creation and hot reload
    - Data transformation execution
    - State validation and error handling
    - Change notifications (for UIEdge)
    - Serialization/deserialization
    - Resource management
    
    Similar to NodeWrapper but for edges.
    """
    
    def __init__(
        self,
        output_node_id: str,
        outlet_pin_id: str,
        input_node_id: str,
        inlet_pin_id: str,
        adapter_factory: 'AdapterFactory',
        edge_type: Optional[EdgeType] = None
    ):
        """
        Initialize EdgeWrapper (similar to NodeWrapper.__init__).
        
        Args:
            output_node_id: Source node ID
            outlet_pin_id: Source outlet ID
            input_node_id: Target node ID
            inlet_pin_id: Target inlet ID
            adapter_factory: Factory for creating adapter chains
            edge_type: Optional edge type (determined during registration)
        """
        self.output_node_id = output_node_id
        self.outlet_pin_id = outlet_pin_id
        self.input_node_id = input_node_id
        self.inlet_pin_id = inlet_pin_id
        
        self._adapter_factory = adapter_factory
        
        # Generate connection UUID
        from ...ui.utils import generate_connection_uuid
        self.connection_uuid = generate_connection_uuid(
            output_node_id, outlet_pin_id, input_node_id, inlet_pin_id
        )
        
        # Edge instance (created during registration)
        self._edge: Optional[Edge] = None
        
        # Adapter chain (created during registration)
        self._adapter_chain: Optional[AdapterChain] = None
        
        # Node wrapper references (set during registration)
        self._output_wrapper: Optional['NodeWrapper'] = None
        self._input_wrapper: Optional['NodeWrapper'] = None
        
        # DataPort references (set during registration)
        self._outlet_port: Optional[DataPort] = None
        self._inlet_port: Optional[DataPort] = None
        
        # State management
        self.state = EdgeWrapperState(creation_time=time.time())
        
        # Lifecycle event subscribers (for UIEdge)
        self._lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Edge type (may be overridden during registration)
        self._edge_type = edge_type
    
    def initialize(self, graph: 'BaseGraph') -> Optional['EdgeWrapper']:
        """
        Initialize edge wrapper (similar to NodeWrapper.initialize).
        
        This is the second initialization step where we:
        1. Get node wrapper references
        2. Get DataPort references
        3. Determine edge type
        4. Validate compatibility
        5. Create adapter chain
        6. Create Edge instance
        7. Subscribe to adapter factory
        
        Does NOT add wrapper to graph - that's the caller's responsibility.
        
        Args:
            graph: The graph containing this edge
            
        Returns:
            Self if initialization successful, None otherwise
        """
        try:
            # Get node wrapper references
            self._output_wrapper = graph.get_node_wrapper(self.output_node_id)
            self._input_wrapper = graph.get_node_wrapper(self.input_node_id)
            
            if not self._output_wrapper or not self._input_wrapper:
                raise HaywireException(
                    message=(
                        f"Node wrappers not found for edge "
                        f"{self.connection_uuid}"
                    )
                )
            
            # Get DataPort references
            outlet_node = self._output_wrapper.node
            inlet_node = self._input_wrapper.node
            
            self._outlet_port = outlet_node.outlets.get(self.outlet_pin_id)
            self._inlet_port = inlet_node.inlets.get(self.inlet_pin_id)
            
            if not self._outlet_port or not self._inlet_port:
                raise HaywireException(
                    message=(
                        f"Ports not found for edge {self.connection_uuid}"
                    )
                )
            
            # Determine edge type if not set
            if self._edge_type is None:
                self._edge_type = self._determine_edge_type()
            
            # Validate and create adapter chain (only for DATA edges)
            if self._edge_type == EdgeType.DATA:
                success, error = self._create_adapter_chain()
                if not success:
                    self.state.is_valid = False
                    self.state.error = error
                    # Still create edge but mark invalid
            
            # Create Edge instance
            self._edge = Edge(
                output_node_id=self.output_node_id,
                outlet_pin_id=self.outlet_pin_id,
                input_node_id=self.input_node_id,
                inlet_pin_id=self.inlet_pin_id,
                edge_type=self._edge_type,
                adapter_registry_keys=(
                    self._adapter_chain.get_registry_keys() 
                    if self._adapter_chain else []
                ),
                connection_uuid=self.connection_uuid
            )
            
            # Subscribe to adapter factory for hot reload
            self._adapter_factory.register_edge_callback(
                self.connection_uuid,
                self._on_adapter_lifecycle_event
            )
            
            self.state.is_registered = True
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_INSTANTIATED,
                affected_class=Edge,
                library_identity=None
            ))
            
            return self
            
        except Exception as e:
            logger.error(
                f"Failed to initialize edge {self.connection_uuid}: {e}"
            )
            self.state.error = HaywireException(
                message=f"Edge initialization failed: {e}",
                original_exception=e
            )
            self.state.is_valid = False
            return None
    
    def _determine_edge_type(self) -> EdgeType:
        """Determine edge type from outlet's flow type"""
        from ..data.enums import FlowType
        
        flow_type = self._outlet_port.flow_type
        
        if flow_type == FlowType.CTRL:
            return EdgeType.CONTROL
        elif flow_type == FlowType.DATA:
            return EdgeType.DATA
        elif flow_type == FlowType.CALLBACK:
            return EdgeType.CALLBACK
        else:
            # Default to DATA
            return EdgeType.DATA
    
    def _create_adapter_chain(
        self
    ) -> Tuple[bool, Optional[HaywireException]]:
        """
        Validate connection and create adapter chain.
        
        Two-step validation process:
        1. Port-level rules (connection count, state, direction)
        2. Field compatibility with adapter chain creation
        
        Fields declare their compatible types via get_compatible_type(),
        which handles both structural validation (via ValueError) and
        type compatibility determination (returns type for adapter checking).
        
        Returns:
            (success, error)
        """
        # Step 1: Validate port-level rules (no type checking)
        is_valid, error_msg = self._inlet_port.validate_connection_rules(
            self._outlet_port
        )
        if not is_valid:
            error = HaywireException(
                message=f"Port validation failed: {error_msg}"
            )
            return (False, error)
        
        # Step 2: Get compatible types and create adapter chain
        # Fields determine what to compare (type_cls vs element_type_cls)
        # and perform structural validation (raise ValueError if incompatible)
        try:
            # Inlet determines what type it needs from outlet
            target_type = self._inlet_port.data.get_compatible_type(
                self._outlet_port.data
            )
            
            # Outlet determines what type it provides to inlet
            # For scalar fields: returns type_cls
            # For compound fields: returns element_type_cls
            outlet_field = self._outlet_port.data
            source_type = outlet_field.type_cls
                
        except ValueError as e:
            # Structural incompatibility (e.g., scalar → array)
            error = HaywireException(
                message=f"Field structural incompatibility: {str(e)}"
            )
            return (False, error)
        
        # Step 3: Create adapter chain
        # (SINGLE SOURCE OF TRUTH for type compatibility via registry)
        chain, error_msg = self._adapter_factory.create_chain(
            source_type,
            target_type,
            self.connection_uuid
        )
        
        if chain:
            self._adapter_chain = chain
            return (True, None)
        else:
            # Type incompatible - no adapter chain exists
            error = HaywireException(
                message=(
                    f"Type incompatible: "
                    f"{error_msg or 'Unknown error'}"
                )
            )
            return (False, error)
    
    def transform(self, value: Any) -> Any:
        """
        Transform value through adapter chain.
        
        This method will be referenced by the outlet DataPort for
        data transformation during graph execution.
        
        Args:
            value: Source value from outlet
            
        Returns:
            Transformed value ready for inlet
            
        Raises:
            HaywireException: If edge is invalid or transformation fails
            
        Example:
            # Store reference in outlet port
            outlet_port.edge_transform = edge_wrapper.transform
            
            # During execution
            transformed = outlet_port.edge_transform(raw_value)
            inlet_port.set_value(transformed)
        """
        if not self.state.is_valid:
            raise HaywireException(
                message=(
                    f"Cannot transform - edge {self.connection_uuid} "
                    f"is invalid"
                ),
                error=self.state.error
            )
        
        # For CONTROL edges, pass through unchanged
        if self._edge_type != EdgeType.DATA:
            return value
        
        # No adapter chain needed (direct type match)
        if (
            not self._adapter_chain or 
            self._adapter_chain.chain_length == 0
        ):
            return value
        
        # Execute adapter chain
        self.state.is_executing = True
        try:
            result = self._adapter_chain.execute(value)
            self.state.execution_count += 1
            return result
        finally:
            self.state.is_executing = False
    
    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events.
        
        Called by AdapterFactory when adapters in our chain are reloaded.
        """
        logger.info(
            f"Edge {self.connection_uuid} received adapter lifecycle "
            f"events: {len(batch)} events"
        )
        
        # Attempt to rebuild chain
        source_type = self._outlet_port.type_cls
        target_type = self._inlet_port.type_cls
        
        chain, error, chain_changed = self._adapter_factory.rebuild_chain(
            self.connection_uuid,
            source_type,
            target_type
        )
        
        self.state.last_hot_reload = time.time()
        self.state.hot_reload_count += 1
        
        if chain:
            # Successfully rebuilt
            old_chain = self._adapter_chain
            self._adapter_chain = chain
            self.state.is_valid = True
            self.state.error = None
            
            # Warn if chain changed
            if chain_changed:
                self.state.chain_changed_warning = True
                logger.warning(
                    f"Edge {self.connection_uuid} adapter chain changed "
                    f"during hot reload - graph behavior may differ!"
                )
                
                # Update Edge instance with new adapter keys
                if self._edge:
                    self._edge.adapter_registry_keys = (
                        chain.get_registry_keys()
                    )
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_RELOADED,
                affected_class=Edge,
                library_identity=None
            ))
        else:
            # Failed to rebuild
            self.state.is_valid = False
            self.state.error = HaywireException(
                message=f"Failed to rebuild adapter chain: {error}",
                error=None
            )
            
            logger.error(
                f"Edge {self.connection_uuid} became invalid - "
                f"no adapter chain available"
            )
            
            # Notify subscribers
            self._notify_lifecycle_event(LifeCycleEvent(
                registry_key=self.connection_uuid,
                event_type=LifeCycleEventType.CLASS_RELOAD_FAILED,
                affected_class=Edge,
                library_identity=None,
                error=self.state.error
            ))
    
    def add_lifecycle_subscriber(self, callback: LiveCycleBatchCallback):
        """Add subscriber for lifecycle events (for UIEdge)"""
        if callback not in self._lifecycle_subscribers:
            self._lifecycle_subscribers.append(callback)
    
    def remove_lifecycle_subscriber(
        self, 
        callback: LiveCycleBatchCallback
    ):
        """Remove lifecycle subscriber"""
        if callback in self._lifecycle_subscribers:
            self._lifecycle_subscribers.remove(callback)
    
    def _notify_lifecycle_event(self, event: LifeCycleEvent):
        """Notify all subscribers of lifecycle event"""
        self.state.history.append(event)
        
        # Batch notification (similar to NodeWrapper)
        batch = [event]
        for callback in self._lifecycle_subscribers:
            try:
                callback(batch)
            except Exception as e:
                logger.error(f"Lifecycle subscriber error: {e}")
    
    def validate(self) -> List[str]:
        """
        Validate edge state.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        if not self.state.is_registered:
            errors.append("Edge not registered with graph")
        
        if not self.state.is_valid:
            errors.append(f"Edge invalid: {self.state.error}")
        
        if (
            self._edge_type == EdgeType.DATA and 
            not self._adapter_chain
        ):
            errors.append("DATA edge missing adapter chain")
        
        if self.state.chain_changed_warning:
            errors.append(
                "WARNING: Adapter chain changed during hot reload - "
                "graph behavior may differ"
            )
        
        return errors
    
    def get_metrics(self) -> dict:
        """
        Get edge execution metrics (for UIEdge display).
        
        Returns:
            Dict with execution statistics
        """
        metrics = {
            'connection_uuid': self.connection_uuid,
            'edge_type': (
                self._edge_type.value if self._edge_type else None
            ),
            'is_valid': self.state.is_valid,
            'execution_count': self.state.execution_count,
            'hot_reload_count': self.state.hot_reload_count,
            'chain_changed_warning': self.state.chain_changed_warning,
        }
        
        if self._adapter_chain:
            metrics.update({
                'adapter_chain': (
                    self._adapter_chain.get_chain_description()
                ),
                'chain_length': self._adapter_chain.chain_length,
                'chain_metrics': {
                    'execution_count': (
                        self._adapter_chain.metrics.execution_count
                    ),
                    'avg_time_ms': (
                        self._adapter_chain.metrics
                        .average_execution_time_ms
                    ),
                    'last_time_ms': (
                        self._adapter_chain.metrics
                        .last_execution_time_ms
                    ),
                    'error_count': (
                        self._adapter_chain.metrics.error_count
                    ),
                }
            })
        
        return metrics
    
    def cleanup(self):
        """Clean up edge resources"""
        # Unsubscribe from adapter factory
        self._adapter_factory.unregister_edge_callback(
            self.connection_uuid
        )
        
        # Clear references
        self._adapter_chain = None
        self._output_wrapper = None
        self._input_wrapper = None
        self._outlet_port = None
        self._inlet_port = None
        self._edge = None
        
        # Clear subscribers
        self._lifecycle_subscribers.clear()
    
    @property
    def edge(self) -> Optional[Edge]:
        """Get the Edge instance"""
        return self._edge
    
    @property
    def is_valid(self) -> bool:
        """Check if edge is valid"""
        return self.state.is_valid
    
    @property
    def adapter_chain(self) -> Optional[AdapterChain]:
        """Get the adapter chain"""
        return self._adapter_chain
    
    def __repr__(self) -> str:
        status = "valid" if self.state.is_valid else "invalid"
        chain_desc = (
            self._adapter_chain.get_chain_description() 
            if self._adapter_chain 
            else "none"
        )
        return (
            f"EdgeWrapper({self.connection_uuid}, "
            f"type={self._edge_type.value if self._edge_type else 'unknown'}, "
            f"status={status}, chain={chain_desc})"
        )
