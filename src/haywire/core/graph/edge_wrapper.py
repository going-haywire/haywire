import logging
import time
from typing import Any, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from ...ui.utils import generate_connection_uuid
from ..data.enums import FlowType
from ..adapter.base import IAdapter
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
    warning_chain_rebuild: str = ""
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
    chain_adapter_keys: List[str] = field(default_factory=list)
    """Registry keys of adapters in the chain"""


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
            edge_type: edge type
        """
        self.output_node_id = output_node_id
        self.outlet_port_id = outlet_port_id
        self.input_node_id = input_node_id
        self.inlet_port_id = inlet_port_id

        # Edge type (may be overridden during registration)
        self._edge_type = edge_type

        # Generate connection UUID
        self.connection_uuid = generate_connection_uuid(
            output_node_id, outlet_port_id, input_node_id, inlet_port_id
        )
        
        # Reference to parent graph
        self._graph: Optional['BaseGraph'] = None

        # Adapter factory reference
        self._adapter_factory: Optional['AdapterFactory'] = None
               
        # Node wrapper references (set during registration)
        self._output_wrapper: Optional['NodeWrapper'] = None
        self._input_wrapper: Optional['NodeWrapper'] = None
        
        # DataPort references (set during registration)
        self._outlet_port: Optional['DataPort'] = None
        self._inlet_port: Optional['DataPort'] = None

        # First adapter in chain (created during registration)
        self._first_adapter: Optional[IAdapter] = None

        # State management
        self.state = EdgeWrapperState(creation_time=time.time())
        
        # Lifecycle event subscribers (for UIEdge)
        self._lifecycle_subscribers: List[LiveCycleBatchCallback] = []
        
        # Create Edge instance in any case
        self._edge = Edge(
            output_node_id=self.output_node_id,
            outlet_pin_id=self.outlet_port_id,
            input_node_id=self.input_node_id,
            inlet_pin_id=self.inlet_port_id,
            edge_type=self._edge_type,
            chain_adapter_keys=([]),
            connection_uuid=self.connection_uuid
        )

    def initialize(self, graph: 'BaseGraph') -> Optional['EdgeWrapper']:
        """
        Initialize edge wrapper 
                
        Does neiter add wrapper to graph nor build the adapter chain - that's the caller's responsibility.
        
        Args:
            graph: The graph containing this edge
            
        Returns:
            Self if initialization successful, None otherwise
        """
        self._graph = graph
        self._adapter_factory = graph.adapter_factory

        # Subscribe to adapter factory for hot reload 
        self._adapter_factory.register_edge_callback(
            self.connection_uuid,
            self._on_adapter_lifecycle_event
        )

        return self

    def rebuild(self):
        """
        Build edge wrapper (including rebuild adapter chain).        
        Does **not** notify lifecycle subscribers.
        """
        logger.debug(
            f"Start edge rebuilding: {self.connection_uuid} ... "
        )
        self._validate_port_types()

        self._build_adapter_chain()
            
        self.refresh_state()        

        logger.debug(
            f".. rebuilding edge done."
        )


    def refresh(self):
        """
        Refresh edge wrapper state without rebuilding adapter chain.  
        Does notify lifecycle subscribers.      
        """
        logger.debug(
            f"Start edge refreshing: {self.connection_uuid} ... "
        )
        self._validate_port_types()
            
        self.refresh_state()        

        self._notify_lifecycle_subscribers()

        logger.debug(
            f".. refreshing edge done."
        )

    def _build_adapter_chain(self):
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
                                               
                # Create new chain
                first_adapter, error = self._adapter_factory.create_chain(
                    source_type,
                    target_type,
                    self.connection_uuid
                )
                
                if first_adapter:
                    # Check for chain changes on rebuild
                    if self.state.chain_adapter_keys is not None:
                        old_adapter_keys = set(self.state.chain_adapter_keys)
                        new_adapter_keys = set(first_adapter._get_registry_keys())
                        if old_adapter_keys != new_adapter_keys:
                            self.state.warning_chain_rebuild = (
                                f"Adapter chain composition changed during hot reload. "
                                f"From {' > '.join(old_adapter_keys)} "
                                f"to {' > '.join(new_adapter_keys)}. "
                                f"Graph behavior may differ!"
                            )
                    # Set first adapter
                    self._first_adapter = first_adapter
                    self.state.chain_adapter_keys = first_adapter._get_registry_keys()
                    
                else:
                    self.state.error_build = HaywireException.create(
                        message=f"Edge adapter creation failed: {error}",
                    ).enrich(
                        operation="Adapter Chain Creation",
                        suggestions=[
                            "Check if libraries with required adapters are registered",
                            "Create custom adapters if needed for your data types"]
                    )
                    self.state.error_build.log()
                    self.state.is_built = False
                    self.state.warning_chain_rebuild = ""
                    return
                                            
            self.state.is_built = True
            self.state.error_build = None
                                    
        except Exception as e:
            self.state.error_build = HaywireException.from_exception(
                exception=e,
                message=f"Edge adapter creation failed for edge {self.connection_uuid}: {e}",
                operation="Adapter Chain Creation",
                category="Adapter Creation Error"
            ).enrich(
                suggestions=[
                    "Check if libraries with required adapters are registered",
                    "Create custom adapters if needed for your data types"]
            )
            self.state.error_build.log()
            self.state.is_built = False
            self.state.warning_chain_rebuild = ""


    def _validate_port_types(self):
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
            self._output_wrapper = self._graph.get_node_wrapper(self.output_node_id)
            self._input_wrapper = self._graph.get_node_wrapper(self.input_node_id)
            
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
            

    def test(self) -> bool:
        """
        test adapter chain with test value.
        
        This method will be referenced by the outlet DataPort for
        data transformation during graph execution.
        
        Returns:
            True if test passes, False otherwise
            
        """

        try:
            # Execute adapter chain with performance tracking
            start_time = time.perf_counter()
            self.state.is_executing = True

            result = self._first_adapter.execute(34)
            
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
                self.state.warning_chain_rebuild = ""

                self.refresh_state()
                self._notify_lifecycle_subscribers()

                return  # abort on first warning/error           

        self.rebuild()

        self._graph.validate_edge_wrapper(self)

        self._notify_lifecycle_subscribers()

    def refresh_state(self, validate: bool = True):
        """
        Refresh edge state without notifying lifecycle subscribers.
        """

        # Update Edge instance with new adapter keys
        if self._edge and self._first_adapter:
            self._edge.chain_adapter_keys = (
                self._first_adapter._get_registry_keys()
            )

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
        elif self.state.warning_chain_rebuild:
            self.state.warning_main = self.state.warning_chain_rebuild
        else:
            self.state.warning_main = ""


    def _notify_lifecycle_subscribers(self):
        """
        Notify all subscribers of lifecycle event
        These are most likely UIEdge instances.
        """
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
            not self._first_adapter
        ):
            errors.append("DATA edge missing adapter chain")
        
        if self.state.warning_chain_rebuild:
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
        
        if self._first_adapter:
            metrics.update({
                'adapter_chain': (
                    self._first_adapter._get_registry_keys()
                ),
                'chain_length': len(self._first_adapter._get_registry_keys()),
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
        self._first_adapter = None
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
    def first_adapter(self) -> Optional[IAdapter]:
        """Get the first adapter in the chain"""
        return self._first_adapter
    
    def __repr__(self) -> str:
        status = "valid" if self.state.is_valid else "invalid"
        
        # Build chain description from linked adapters
        if self._first_adapter:
            adapter_names = []
            current = self._first_adapter
            while hasattr(current, '_chain'):
                adapter_names.append(current.__class__.__name__)
                current = current._chain
                if current.__class__.__name__ == 'ReturnAdapter':
                    break
            chain_desc = " → ".join(adapter_names) if adapter_names else "direct"
        else:
            chain_desc = "none"
            
        return (
            f"EdgeWrapper({self.connection_uuid}, "
            f"type={self._edge_type.value if self._edge_type else 'unknown'}, "
            f"status={status}, chain={chain_desc})"
        )
