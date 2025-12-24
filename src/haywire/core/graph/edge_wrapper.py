import logging
import time
from typing import Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from ...ui.utils import generate_connection_uuid
from ..data.enums import FlowType
from ..adapter.chain import AdapterChain
from ..errors import HaywireException
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback
)
from ..types.interface import IType
from .edge import Edge

if TYPE_CHECKING:
    from .base import BaseGraph
    from ..adapter.factory import AdapterFactory
    from ..node.node_wrapper import NodeWrapper
    from ..types.ports import DataPort

logger = logging.getLogger(__name__)

@dataclass
class EdgeWrapperState:
    """Lifecycle state of wrapper and its edge instance"""
    is_valid: bool = False
    """The edge is valid (is active connection)"""
    is_inlet_validated: bool = False
    """The inlet port has been validated"""
    is_outlet_validated: bool = False
    """The outlet port has been validated"""
    is_port_type_validated: bool = False
    """The edge port types have been validated (are compatible)"""
    is_built: bool = False
    """The edge adapter chain has been built (inlets/outlets are compatible)"""
    is_registered: bool = False
    """The edge has been registered with the graph"""
    is_executing: bool = False
    """Edge is currently transforming data"""
    warning_rebuild: str = ""
    """rebuilding adapter chain produced a different chain"""
    warning_port_validation: str = ""
    """port validation warning message"""
    warning_main: str = ""
    """main warning message"""
    error_port_type: Optional[HaywireException] = None
    """port type error"""
    error_build: Optional[HaywireException] = None
    """build error"""
    error_main: Optional[HaywireException] = None
    """Main error state"""
    creation_time: float = 0.0
    """When edge was created"""
    execution_count: int = 0
    """Number of times transform() was called"""
    total_execution_time_ms: float = 0.0
    """Total time spent in transform() execution"""
    last_execution_time_ms: float = 0.0
    """Last transform() execution time"""
    average_execution_time_ms: float = 0.0
    """Average transform() execution time"""
    error_count: int = 0
    """Number of transform() errors"""
    last_error: Optional[str] = None
    """Last transform() error message"""


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
        outlet_port_id: str,
        input_node_id: str,
        inlet_port_id: str,
        edge_type: FlowType
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
        self.outlet_port_id = outlet_port_id
        self.input_node_id = input_node_id
        self.inlet_port_id = inlet_port_id
                
        # Generate connection UUID
        self.connection_uuid = generate_connection_uuid(
            output_node_id, outlet_port_id, input_node_id, inlet_port_id
        )
        
        # Reference to parent graph
        self._graph: Optional['BaseGraph'] = None

        # Adapter factory reference
        self._adapter_factory: Optional['AdapterFactory'] = None
       
        # Adapter chain (created during registration)
        self._adapter_chain: Optional[AdapterChain] = None
        
        # Node wrapper references (set during registration)
        self._output_wrapper: Optional['NodeWrapper'] = None
        self._input_wrapper: Optional['NodeWrapper'] = None
        
        # DataPort references (set during registration)
        self._outlet_port: Optional['DataPort'] = None
        self._inlet_port: Optional['DataPort'] = None
        
        # State management
        self.state = EdgeWrapperState(creation_time=time.time())
        
        # Lifecycle event subscribers (for UIEdge)
        self._lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Edge type (may be overridden during registration)
        self._edge_type = edge_type

        # Create Edge instance in any case
        self._edge = Edge(
            output_node_id=self.output_node_id,
            outlet_pin_id=self.outlet_port_id,
            input_node_id=self.input_node_id,
            inlet_pin_id=self.inlet_port_id,
            edge_type=self._edge_type,
            adapter_registry_keys=([]),
            connection_uuid=self.connection_uuid
        )

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
        self._graph = graph
        self._adapter_factory = graph.adapter_factory

        self._validate_port_types(graph)

        self._build_adapter_chain(False)

        self.refresh_state()

        return self

    def _build_adapter_chain(self, rebuild: bool = False):
        """
        Build adapter chain for this edge.
        Args:
            rebuild: Whether this is a rebuild (hot reload) or initial build
        """
        try:
            # create adapter chain (only for DATA edges)
            if self._edge_type == FlowType.DATA:
                # Inlet determines what type it needs from outlet
                target_type = self._inlet_port.data.get_compatible_type()
                
                outlet_field = self._outlet_port.data
                source_type = outlet_field.type_cls
                    
                if rebuild:
                    chain, error, chain_changed = self._adapter_factory.rebuild_chain(
                        source_type,
                        target_type,
                        self.connection_uuid,
                    )
                    # Warn if chain changed
                    if chain_changed:
                        self.state.warning_rebuild = str(
                            f"Edge {self.connection_uuid} adapter chain composition changed "
                            f"during hot reload - graph behavior may differ!"
                        )
                        
                        # Update Edge instance with new adapter keys
                        if self._edge:
                            self._edge.adapter_registry_keys = (
                                chain.get_registry_keys()
                            )
                    else:
                        self.state.warning_rebuild = ""
                else:
                    chain, error, chain_changed = self._adapter_factory.create_chain(
                        source_type,
                        target_type,
                        self.connection_uuid
                    )
                    if chain:
                        # Subscribe to adapter factory for hot reload 
                        self._adapter_factory.register_edge_callback(
                            self.connection_uuid,
                            self._on_adapter_lifecycle_event
                        )

                if chain:
                    self._adapter_chain = chain
                else:
                    raise Exception(
                        f"Adapter chain creation failed: {error}"
                    )
                                    
            self.state.is_built = True
            self.state.error_build = None
                                    
        except Exception as e:
            logger.error(
                f"Failed to build adapter chain for edge {self.connection_uuid}: {e}"
            )
            self.state.error_build = HaywireException.from_exception(
                exception=e,
                message=f"Edge adapter creation failed: {e}",
            )
            self.state.is_built = False
            self.state.warning_rebuild = ""


    def _validate_port_types(self, graph: 'BaseGraph'):
        """
        Validate connection between ports.

        This formally validates that the connection between 
        the two ports is possible based on their existence and types.
        
        set flag is_port_type_validated to True if successful.

        Args:
            graph: The graph containing this edge
        Raises:
            Exception: If validation fails
        """

        try:
            # Get node wrapper references
            self._output_wrapper = graph.get_node_wrapper(self.output_node_id)
            self._input_wrapper = graph.get_node_wrapper(self.input_node_id)
            
            if not self._output_wrapper or not self._input_wrapper:
                raise Exception(
                    f"Nodes not found for edge: "
                    f"{self.connection_uuid} | "
                    f" (output_node_id={self.output_node_id}, input_node_id={self.input_node_id})"
                )
            
            # Get DataPort references
            outlet_node = self._output_wrapper.node
            inlet_node = self._input_wrapper.node
            
            self._outlet_port = outlet_node.outlets.get(self.outlet_port_id)
            self._inlet_port = inlet_node.inlets.get(self.inlet_port_id)
            
            # Determine edge type if not set
            if self._edge_type is None:
                self._edge_type = self._outlet_port.flow_type

            if not self._outlet_port or not self._inlet_port:
                raise Exception(
                    f"Ports not found for edge: "
                    f"{self.connection_uuid} | "
                    f"(outlet_pin_id={self.outlet_port_id}, inlet_pin_id={self.inlet_port_id})"
                )

            # Check if this is an inlet (sanity check)
            if self._outlet_port.is_inlet() == self._inlet_port.is_inlet():
                raise Exception(
                    f"Cannot connect inlet to inlet or outlet to outlet"
                )

            if self._outlet_port.flow_type != self._inlet_port.flow_type:
                raise Exception(
                    f"Flow type mismatch between outlet "
                    f"({self._outlet_port.flow_type}) and inlet "
                    f"({self._inlet_port.flow_type}) on edge "
                    f"{self.connection_uuid}"
                )
            
            self.state.is_port_type_validated = True
            self.state.error_port_type = None

        except Exception as e:
            logger.error(
                f"Failed to validate port types on edge {self.connection_uuid}: {e}"
            )
            self.state.error_port_type = HaywireException(
                message=f"Port type validation failed: {e}",
            )
            self.state.is_port_type_validated = False            
            

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

        try:
            # Execute adapter chain with performance tracking
            start_time = time.perf_counter()
            self.state.is_executing = True

            result = self._adapter_chain.execute(value)
            
            # Update metrics
            execution_time = (time.perf_counter() - start_time) * 1000
            self.state.execution_count += 1
            self.state.last_execution_time_ms = execution_time
            self.state.total_execution_time_ms += execution_time
            self.state.average_execution_time_ms = (
                self.state.total_execution_time_ms / 
                self.state.execution_count
            )
            self.state.is_executing = False
            
            return result
        except Exception as e:
            self.state.error_count += 1
            self.state.last_error = str(e)
            raise
        finally:
            self.state.is_executing = False
    
    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events.
        
        Called by AdapterFactory when adapters in our chain are reloaded.
        """
        logger.debug(
            f"Edge {self.connection_uuid} received adapter lifecycle "
            f"events: {len(batch)} events"
        )

        # before attempting rebuild, check for warnings/errors
        for event in batch:
            if event.is_warning_event():
                self.state.error_build = HaywireException.from_exception(
                    exception=event.error,
                    message=f"Adapter hot reload error on edge {self.connection_uuid}",
                    operation="Adapter Hot Reload: {event.event_type}",
                ).enrich(
                    library_identity=event.library_identity,
                    module_name=event.module_name,
                    registry_key=event.registry_key
                )
                
                self.state.error_build.log()
                self.state.is_built = False
                self.state.warning_rebuild = ""

                self.refresh_state()
                return  # abort on first warning/error           

        self._validate_port_types(self._graph)

        self._build_adapter_chain(True)

        self._graph.validate_edge_wrapper(self)
            
        self.refresh_state()

    def refresh_state(self, validate: bool = True):
        """
        Refresh edge state and notify lifecycle subscribers.
        """
        if (self.state.is_port_type_validated
            and self.state.is_built 
            and self.state.is_inlet_validated 
            and self.state.is_outlet_validated):
            self.state.is_valid = True
        else:
            self.state.is_valid = False
            
        # Update main error state
        if self.state.error_port_type:
            self.state.error_main = self.state.error_port_type
        elif self.state.error_build:
            self.state.error_main = self.state.error_build
        else:
            self.state.error_main = None

        if not self.state.is_inlet_validated:
            self.state.warning_port_validation = "port inlet connection refused due to connection limit"
        elif not self.state.is_outlet_validated:
            self.state.warning_port_validation = "port outlet connection refused due to connection limit"
        else:
            self.state.warning_port_validation = ""

        if self.state.warning_port_validation:
            self.state.warning_main = self.state.warning_port_validation
        elif self.state.warning_rebuild:
            self.state.warning_main = self.state.warning_rebuild
        else:
            self.state.warning_main = ""

        # Notify subscribers
        self._notify_lifecycle_event()

    def _notify_lifecycle_event(self):
        """Notify all subscribers of lifecycle event"""
        for callback in self._lifecycle_subscribers:
            try:
                callback()
            except Exception as e:
                logger.error(f"Lifecycle subscriber error: {e}")


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
            errors.append(f"Edge invalid: {self.state.error_main.message if self.state.error_main else 'unknown error'}")
        
        if (
            self._edge_type == FlowType.DATA and 
            not self._adapter_chain
        ):
            errors.append("DATA edge missing adapter chain")
        
        if self.state.warning_rebuild:
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
            'chain_changed_warning': self.state.warning_main,
            'error': self.state.error_main if self.state.error_main else None,  # Include error for context menu display
        }
        
        if self._adapter_chain:
            metrics.update({
                'adapter_chain': (
                    self._adapter_chain.get_chain_description()
                ),
                'chain_length': len(self.edge.adapter_registry_keys),
                'avg_time_ms': self.state.average_execution_time_ms,
                'last_time_ms': self.state.last_execution_time_ms,
                'total_time_ms': self.state.total_execution_time_ms,
                'error_count': self.state.error_count,
                'last_error': self.state.last_error,
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
