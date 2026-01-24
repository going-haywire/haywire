import copy
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field

from ...ui.utils import generate_connection_uuid
from ..graph.types import ChangeReason
from ..validation.interface import IStructuralValidator
from ..data.enums import FlowType
from ..adapter.base import IAdapter
from ..errors import HaywireException
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleBatchCallback
)
from ..types.interface import IType
from .edge import Edge

if TYPE_CHECKING:
    from ..graph.base import BaseGraph
    from ..adapter.factory import AdapterFactory
    from ..node.node_wrapper import NodeWrapper
    from ..types.ports import DataPort

logger = logging.getLogger(__name__)

@dataclass
class EdgeWrapperState:
    """Lifecycle state of wrapper and its edge instance"""
    is_registered: bool = False
    """The edge has been registered with the graph"""
    is_formally_validated: bool = False
    """The edge is formally validated (node/port existence and type compatibility)"""
    is_built: bool = False
    """The edge adapter chain has been built (inlets/outlets are compatible)"""
    is_structural: bool = False
    """The edge has passed structural validation"""
    has_test_passed: bool = False
    """The edge adapter chain has been successfully tested"""
    is_inlet_linked: bool = False
    """The inlet port has been validated"""
    is_outlet_linked: bool = False
    """The outlet port has been validated"""
    is_linked: bool = False
    """The edge is linked to both ports"""
    is_executing: bool = False
    """Edge is currently transforming data"""
    warnings: List[str] = None
    """main warning message"""
    error_link: Optional[HaywireException] = None
    """port validation error message"""
    error_formal: Optional[HaywireException] = None
    """port type error"""
    error_build: Optional[HaywireException] = None
    """build error"""
    error_structural: Optional[HaywireException] = None
    """structural validation error"""
    error_test: Optional[HaywireException] = None
    """test error message"""
    creation_time: float = 0.0
    """When edge was created"""
    execution_count: int = 0
    """Number of times transform() was called"""
    last_execution_time_ns: float = 0.0
    """Last transform() execution time"""
    average_execution_time_ns: float = 0.0
    """Average transform() execution time"""
    example_test_value: str = None
    """Example test value used during test"""
    example_test_result: str = None
    """Example test result value used during test"""


    def has_warning(self) -> bool:
        """Check if connection has warnings"""
        return bool(len(self.warnings) > 0)

    def is_functional(self) -> bool:
        """Check if connection is functional (registered, port-type-validated and built)"""
        return (self.is_registered and 
            self.is_formally_validated and 
            self.is_built and
            self.has_test_passed
        )

    def is_valid(self) -> bool:
        """Check if connection is in valid state (functional and linked)"""
        return (self.is_functional() 
            and self.is_structural
            and self.is_linked)

    def get_error(self) -> Optional[HaywireException]:
        """Get main error"""
        if self.error_formal:
            return self.error_formal
        elif self.error_build:
            return self.error_build
        elif self.error_structural:
            return self.error_structural
        elif self.error_link:
            return self.error_link
        elif self.error_test:
            return self.error_test
        else:
            return None

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
        graph: 'BaseGraph',
        source_node_id: str,
        outlet_port_id: str,
        sink_node_id: str,
        inlet_port_id: str,
        edge_type: FlowType
    ):
        """
        Initialize EdgeWrapper (similar to NodeWrapper.__init__).
        
        Args:
            source_node_id: Source node ID
            outlet_port_id: Source outlet ID
            sink_node_id: Sink node ID
            inlet_port_id: Sink inlet ID
            edge_type: edge type
        """
        self.source_node_id = source_node_id
        self.outlet_port_id = outlet_port_id
        self.sink_node_id = sink_node_id
        self.inlet_port_id = inlet_port_id

        # Edge type (may be overridden during registration)
        self._edge_type = edge_type

        # Generate connection UUID
        self._connection_uuid = generate_connection_uuid(
            source_node_id, outlet_port_id, sink_node_id, inlet_port_id
        )
        
        # Reference to parent graph
        self._graph: Optional['BaseGraph'] = graph

        # Adapter factory reference from global DI service locator
        from haywire.core.di.config import get_library_system
        self._adapter_factory: Optional['AdapterFactory'] = get_library_system().get_adapter_factory()
               
        # Node wrapper references (set during registration)
        self._source_wrapper: Optional['NodeWrapper'] = None
        self._sink_wrapper: Optional['NodeWrapper'] = None
        
        # DataPort references (set during registration)
        self._outlet_port: Optional['DataPort'] = None
        self._inlet_port: Optional['DataPort'] = None

        # First adapter in chain (created during registration)
        self._first_adapter: Optional[IAdapter] = None

        # State management
        self._state = EdgeWrapperState(creation_time=time.time())
        
        # Lifecycle event subscribers (for UIEdge)
        self._lifecycle_subscribers: List[LifeCycleBatchCallback] = []
        
        # Create Edge instance in any case
        self._edge = Edge(
            source_node_id=self.source_node_id,
            outlet_port_id=self.outlet_port_id,
            sink_node_id=self.sink_node_id,
            inlet_port_id=self.inlet_port_id,
            edge_type=self._edge_type,
            chain_adapter_keys=([])
        )

        self._source_type: Optional[IType] = None

        # Subscribe to adapter factory for hot reload 
        self._adapter_factory.register_edge_callback(
            self._connection_uuid,
            self._on_adapter_lifecycle_event
        )

        self._structural_validator: Optional['IStructuralValidator'] = self._graph._structural

    def is_valid(self) -> bool:
        """Check if edge is valid"""
        return self._state.is_valid()

    def is_functional(self) -> bool:
        """Check if connection is functional (registered, formal-validated and built)"""
        return self._state.is_functional()

    def is_callback_edge(self) -> bool:
        """Check if this is a callback edge"""
        return self.edge_type == FlowType.CALLBACK
    
    def is_control_edge(self) -> bool:
        """Check if this is a control edge"""
        return self.edge_type == FlowType.CONTROL
    
    def is_data_edge(self) -> bool:
        """Check if this is a data edge"""
        return self.edge_type == FlowType.DATA

    @property
    def edge(self) -> Optional[Edge]:
        """Get the Edge instance"""
        return self._edge

    @property
    def connection_uuid(self) -> str:
        """Get the Edge id"""
        return self._connection_uuid

    @property
    def first_adapter(self) -> Optional[IAdapter]:
        """Get the first adapter in the chain"""
        return self._first_adapter

    @property
    def state(self) -> Optional[EdgeWrapperState]:
        """Get the Edge state"""
        return self._state

    def build(self):
        """
        Build edge wrapper (including rebuild adapter chain).        
        """
        logger.debug(
            f"Start edge rebuilding: {self._connection_uuid} ... "
        )

        self._state.error_formal = None
        self._state.error_build = None
        self._state.error_link = None
        self._state.error_test = None
        self._state.warnings = []

        if self._formal_validation():
            if self._structural_validation():
                if self._build_adapter_chain():
                    if self._test():                  
                        logger.debug(
                            f".. rebuilding edge done."
                        )
                        return

        logger.debug(
            f".. rebuilding failed with errors."
        )

    def validate_chain_for_changes(self, chain: List[str]):
        """
        Check if adapter chain has changed compared to given chain.
        Issues a warning to the state if so.
        
        Args:
            chain: List of adapter registry keys to compare against
        """
        if self._edge.chain_adapter_keys != chain:
            self._state.warnings.append(
                f"Adapter chain composition changed during hot reload. "
                f"From '{' -> '.join(chain)}' "
                f"to '{' -> '.join(self._edge.chain_adapter_keys)}'. "
                f"Graph behavior may differ!"
            )

    def _build_adapter_chain(self) -> bool:
        """
        Build adapter chain for this edge.
        Args:
            rebuild: Whether this is a rebuild (hot reload) or initial build
        """
        try:
            # create adapter chain (only for DATA edges)
            if self._edge_type == FlowType.DATA:
                # Inlet determines what type it needs from outlet
                sink_type = self._inlet_port.data.get_stored_type()
                
                outlet_field = self._outlet_port.data
                source_type = outlet_field.type_cls
                                               
                # Create new chain
                first_adapter, error = self._adapter_factory.create_chain(
                    source_type,
                    sink_type,
                    self._connection_uuid
                )
                
                if first_adapter:
                    # Check for chain changes on rebuild
                    if self._edge.chain_adapter_keys:
                        old_adapter_keys = list(self._edge.chain_adapter_keys)[::-1]
                        new_adapter_keys = list(first_adapter._get_registry_keys())[::-1]
                        if self._source_type == source_type and old_adapter_keys != new_adapter_keys:
                            # we only want to warn about adapter chain changes if 
                            # the source type is the same, otherwise it's expected that the chain changes
                            self._state.warnings.append(
                                f"Adapter chain composition changed during hot reload. "
                                f"From '{' -> '.join(old_adapter_keys)}' "
                                f"to '{' -> '.join(new_adapter_keys)}'. "
                                f"Graph behavior may differ!"
                            )
                    # Set first adapter
                    self._first_adapter = first_adapter
                    self._edge.chain_adapter_keys = first_adapter._get_registry_keys()

                    self._source_type = source_type

                else:
                    # creating the haywire exception in here to avoid missleading stack traces
                    self._state.error_build = HaywireException.create(
                        message=f"Edge adapter creation failed for {self._connection_uuid}: {error}",
                    ).enrich(
                        operation="Adapter Chain Creation",
                        category="Adapter Creation Error",
                        suggestions=[
                            "Check if libraries with required adapters are registered",
                            "Create custom adapters if needed for your data types"]
                    )
                    self._state.error_build.log()
                    self._state.is_built = False
                    self._state.warnings = []

                    return False
                                                        
            self._state.is_built = True
            self._state.error_build = None

            return True
                                    
        except Exception as e:
            self._state.error_build = HaywireException.from_exception(
                exception=e,
                message=f"Edge adapter creation failed for {self._connection_uuid}: {e}",
            ).enrich(
                operation="Adapter Chain Creation",
                category="Adapter Creation Error",
                suggestions=[
                    "Check if libraries with required adapters are registered",
                    "Create custom adapters if needed for your data types"]
            )
            self._state.error_build.log()
            self._state.is_built = False
            self._state.warnings = []

            return False


    def _formal_validation(self) -> bool:
        """
        Validate connection between ports.

        This formally validates that the connection between 
        the two ports is possible based on their existence and types.
        
        set flag is_formally_validated to True if successful.

        Args:
            graph: The graph containing this edge
        Returns:
            True if validation successful, False otherwise
        """

        try:
            # Get node wrapper references
            self._source_wrapper = self._graph.get_node_wrapper(self.source_node_id)
            self._sink_wrapper = self._graph.get_node_wrapper(self.sink_node_id)
            
            if not self._source_wrapper or not self._sink_wrapper:
                raise Exception(
                    f"Nodes not found for edge: "
                    f"{self._connection_uuid} | "
                    f" (source_node_id={self.source_node_id}, sink_node_id={self.sink_node_id})"
                )
            
            # Get DataPort references
            outlet_node = self._source_wrapper.node
            inlet_node = self._sink_wrapper.node
            
            self._outlet_port = outlet_node.ports.get(self.outlet_port_id)
            self._inlet_port = inlet_node.ports.get(self.inlet_port_id)
            
            # Determine edge type if not set
            if self._edge_type is None:
                self._edge_type = self._outlet_port.flow_type

            if not self._outlet_port or not self._inlet_port:
                raise Exception(
                    f"Ports not found for edge: "
                    f"{self._connection_uuid} | "
                    f"(outlet_port_id={self.outlet_port_id}, inlet_port_id={self.inlet_port_id})"
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
                    f"{self._connection_uuid}"
                )
            
            self._state.is_formally_validated = True
            self._state.error_formal = None
            return True

        except Exception as e:
            logger.error(
                f"Failed to validate port types on edge {self._connection_uuid}: {e}"
            )
            self._state.error_formal = HaywireException.create(
                message=f"Port type validation failed: {e}",
                category="Port type Validation Error"
            ).enrich(
                operation="Port Type Validation",
                suggestions=[
                    "Ensure both ports exist",
                    "Check port flow types for compatibility"
                ]
            )
            self._state.error_formal.log()
            self._state.is_formally_validated = False          

            return False  
            
    def _structural_validation(self) -> bool:
        """
        Validate structural constraints for this edge.
        
        Uses the graph's structural validator to check domain-specific rules
        such as callback edge constraints, control flow topology, etc.
        
        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Call structural validator
            (
                is_valid,
                error_message,
                suggestions
            ) = self._structural_validator.validate_edge(self)
            
            # Update state
            self._state.is_structural = is_valid
            
            # Create exception from error message if validation failed
            if not is_valid and error_message:
                self._state.error_structural = HaywireException.create(
                    message=error_message
                ).enrich(
                    connection_uuid=self._connection_uuid,
                    operation="Structural Validation",
                    category="Structural Validation Error",
                    suggestions=suggestions
                )
                self._state.error_structural.log()
            else:
                self._state.error_structural = None
            
            return is_valid
            
        except Exception as e:
            self._state.error_structural = HaywireException.from_exception(
                exception=e,
                message=f"Structural validation failed: {e}"
            ).enrich(
                operation="Structural Validation",
                category="Structural Validation Error",
                suggestions=[
                    "Check edge type and node constraints",
                    "Verify callback edge rules if applicable"
                ]
            )
            self._state.error_structural.log()
            self._state.is_structural = False
            return False

    def _test(self) -> bool:
        """
        test adapter chain with test value.
                
        Returns:
            True if test passes, False otherwise
            
        """

        try:
            # Execute adapter chain with performance tracking

            if self._first_adapter:
                self._state.execution_count = self._first_adapter.get_test_repetitions()
                self._state.example_test_value = self._first_adapter.get_test_value()
                if self._state.execution_count > 0:
                    start_time = time.perf_counter()
                    for i in range(self._state.execution_count):
                        self._state.example_test_result = self._first_adapter.test(self._state.example_test_value)
                
                    # Update metrics
                    execution_time = (time.perf_counter() - start_time) * 1000000.0
                    self._state.last_execution_time_ns = execution_time
                    self._state.average_execution_time_ns = (
                        self._state.last_execution_time_ns / 
                        self._state.execution_count
                    )

            self._state.has_test_passed = True
            self._state.error_test = None
            
            return True
        
        except Exception as e:

            self._state.error_test = HaywireException.from_exception(
                exception=e,
                message=f"Edge test execution failed: {e}"
            ).enrich(
                operation="Edge Test Execution",
                category="Edge Execution Error",
                suggestions=[
                    "Check adapter chain code for errors",
                    "Ensure data types are compatible"
                ]
            )
            self._state.error_test.log()
            self._state.has_test_passed = False
            return False

    def validate_link(self, port: 'DataPort') -> bool:
        """
        Validate if this edge is linked to the given port.
        This does not establish the link itself! 
        To initiate a link is the sole responsibility of the graph.
        An edge can be 'connected' to a port, but thats not the same as being 'linked'. 
        Only the port can accept or refuse the link depending on its connection rules.

        Once an edge is linked to both ports, for which it has to be functional, 
        it is considered valid.
        
        Args:
            port: The DataPort to validate against
        Returns:
            True if linked condition changed, False otherwise
        """
        is_linked = self._state.is_linked

        if port._is_linked(self._connection_uuid):
            if port.is_inlet():
                self._state.is_inlet_linked = True
            else:
                self._state.is_outlet_linked = True
        else:
            if port.is_inlet():
                self._state.is_inlet_linked = False
            else:
                self._state.is_outlet_linked = False

        if not self._state.is_inlet_linked:
            self._state.error_link = HaywireException.create(
                message="Port link refused due to link limit on inlet port.",
                category="Port Linking Error"
            ).enrich(
                operation="Port Linking Validation",
                suggestions=[
                    "Check port linking limits",
                    "Ensure port is not already linked"
                ]
            )
        elif not self._state.is_outlet_linked:
            self._state.error_link = HaywireException.create(
                message="Port link refused due to link limit on outlet port.",
                category="Port Linking Error"
            ).enrich(
                operation="Port Linking Validation",
                suggestions=[
                    "Check port linking limits",
                    "Ensure port is not already linked"
                ]
            )
        else:
            self._state.error_link = None

        self._state.is_linked = (self._state.is_inlet_linked and self._state.is_outlet_linked)

        return self._state.is_linked != is_linked


    def _on_adapter_lifecycle_event(self, batch: List[LifeCycleEvent]):
        """
        Handle adapter hot reload events.
        
        Called by AdapterFactory when adapters in our chain are reloaded.
        """
        logger.debug(
            f"Edge {self._connection_uuid} received adapter lifecycle "
            f"events: {len(batch)} events"
        )

        # before attempting rebuild, check for warnings/errors
        for event in batch:
            if event.is_warning_event():
                if event.error:
                    self._state.error_build = event.error
                else:
                    self._state.error_build = HaywireException.from_exception(
                        exception=event.error,
                        message=f"Adapter hot reload error on edge {self._connection_uuid}",
                        operation="Adapter Hot Reload: {event.event_type}",
                        category="Adapter Hot Reload Error"
                    ).enrich(
                        library_identity=event.library_identity,
                        module_name=event.module_name,
                        registry_key=event.registry_key
                    )

                self._state.error_build.log()
                self._state.is_built = False
                self._state.warnings = []

                # Tell graph about error 
                if self._graph:
                    self._graph._validation.mark_edge_dirty(
                        self._connection_uuid,
                        ChangeReason.EDGE_HOT_RELOAD_ERROR
                    )
                return  # abort on first warning/error           

        # Tell graph about successful reload 
        if self._graph:
            self._graph._validation.mark_edge_dirty(
                self._connection_uuid,
                ChangeReason.EDGE_ADAPTERS_RELOADED
            )

    def set_as_registered(self, is_registered: bool):
        """
        Set edge as registered or unregistered with graph.
        
        Args:
            is_registered: True to mark as registered, False otherwise
        """
        self._state.is_registered = is_registered

        
    def get_state(self) -> EdgeWrapperState:
        """
        Get metrics.
        
        Returns:
            shallow copy of internal EdgeWrapperState with execution statistics
        """
        return copy.copy(self._state)
    
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize edge wrapper state.
        
        Returns the edge data which includes adapter chain metadata.
        This can be used directly by BaseGraph serialization.
        
        Returns:
            Dictionary containing edge state
        """
        return self._edge.to_dict()
    
    def restore_after_load(self) -> bool:
        """
        Restore edge state after graph load.
        
        Called after both nodes have been loaded and the edge has been
        instantiated. Rebuilds the adapter chain based on current port
        types.
        
        Returns:
            True if restoration succeeded, False otherwise
        """
        logger.debug(
            f"Restoring edge {self._connection_uuid} after load"
        )
        
        # Build adapter chain (will auto-detect types from ports)
        self.build()
        
        return self._state.is_valid()
    
    
    def cleanup(self):
        """Clean up edge resources"""
        # Unsubscribe from adapter factory
        self._adapter_factory.unregister_edge_callback(
            self._connection_uuid
        )
        
        # Clear references
        self._first_adapter = None
        self._source_wrapper = None
        self._sink_wrapper = None
        self._outlet_port = None
        self._inlet_port = None
        self._edge = None
        
        # Clear subscribers
        self._lifecycle_subscribers.clear()
    
        
    def __repr__(self) -> str:
        status = "valid" if self._state.is_valid() else "invalid"
        
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
            f"EdgeWrapper({self._connection_uuid}, "
            f"type={self._edge_type.value if self._edge_type else 'unknown'}, "
            f"status={status}, chain={chain_desc})"
        )
