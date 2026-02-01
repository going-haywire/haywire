"""
NodeWrapper - Complete lifecycle management for Haywire nodes.

This wrapper manages the complete lifecycle of a HaywireNode instance,
including creation, hot reload, serialization, and cleanup.
"""
import time
import threading
import logging
from typing import List, Optional, Tuple, Any, Dict, TYPE_CHECKING
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from ..graph.types import ChangeReason
from ..library.utils import get_registry_id_from_key
from ..errors import HaywireException
from ..registry.lifecycle_event import LifeCycleEvent
from ..validation.interface import IStructuralValidator

if TYPE_CHECKING:
    from .base import BaseNode
    from ..graph.base import BaseGraph
    from .factory import NodeFactory
    from ..execution.execution_context import ExecutionContext

logger = logging.getLogger(__name__)

@dataclass
class NodeWrapperState:
    """Lifecycle state of wrapper and its node instance"""
    is_registered: bool = False
    """The node has been registered with the graph"""
    is_imported: bool = False
    """The node class has been imported"""
    is_instantiated: bool = False
    """The node instance has been created"""
    is_initialized: bool = False
    """The node is initialized"""
    is_structural: bool = False 
    """The node has passed structural validation"""
    has_test_passed: bool = False
    """The node has been successfully tested"""
    is_executing: bool = False
    error: Optional['HaywireException'] = None
    error_import: Optional[HaywireException] = None
    """node import error"""
    error_instantiate: Optional[HaywireException] = None
    """node instantiate error"""
    error_initialize: Optional[HaywireException] = None
    """node initialize error"""
    error_structural: Optional[HaywireException] = None
    """node structural validation error"""
    error_custom: Optional[HaywireException] = None
    """node custom error """
    error_test: Optional[HaywireException] = None
    """node test error"""
    error_runtime: List[HaywireException] = field(default_factory=list)
    """node runtime errors (startup, execution, shutdown)"""
    test_execution_time_ns: float = 0.0
    """Last transform() execution time"""

    def is_valid(self) -> bool:
        """Check if node is in valid state (initialized and tested)"""
        return (self.is_registered and 
            self.is_imported and
            self.is_instantiated and
            self.is_initialized and
            self.is_structural and
            self.has_test_passed)

    def has_error(self) -> bool:
        """
        Check if any error exists in the wrapper state
        Having an error does not necessarily mean the node is invalid.
        """
        return self.get_error() is not None

    def get_error(self) -> Optional[HaywireException]:
        """Get error. Having an error does not necessarily mean the node is invalid."""
        if self.error_import:
            return self.error_import
        elif self.error_instantiate:
            return self.error_instantiate
        elif self.error_initialize:
            return self.error_initialize
        elif self.error_structural:
            return self.error_structural
        elif self.error_test:
            return self.error_test
        elif self.error_custom:
            return self.error_custom
        elif self.error_runtime:
            return self.error_runtime[-1]  # Return most recent
        else:
            return None
        
    def _clear_errors(self) -> None:
        """Clear all error states"""
        # self.error_import = None -> we dont clear import errors here, 
        # this error can only be cleared on hot reload
        self.error_instantiate = None
        self.error_initialize = None
        self.error_structural = None
        self.error_test = None
        self.error_custom = None

class NodeMiddleware(ABC):
    """Abstract base for wrapper middleware/plugins"""
    
    @abstractmethod
    def before_method(self, wrapper: 'NodeWrapper', method_name: str, *args) -> None:
        """Called before a wrapper method executes"""
        pass
    
    @abstractmethod
    def after_method(self, wrapper: 'NodeWrapper', method_name: str, result: Any) -> None:
        """Called after a wrapper method executes"""
        pass


class NodeWrapper:
    """
    Manages the complete lifecycle of a HaywireNode instance.
    
    Responsibilities:
    - Node instance management and lifecycle
    - Hot reload detection and migration  
    - Execution preparation and cleanup
    - State validation and error handling
    - Change notifications
    - Serialization/deserialization
    - Resource management
    """
    
    def __init__(self, 
                 registry_key: str,
                 node_id: str,
                 graph: 'BaseGraph',
                 position: Tuple[float, float] = (100, 100)):
        """
        Initialize a new NodeWrapper.
        
        Args:
            registry_key: Registry key for the node class
            node_id: Unique identifier for the node instance
            graph: Parent graph instance
            position: Initial (x, y) position
        """
        self.registry_key = registry_key
        """The registry key of the node class. DO NOT CHANGE AFTER INITIALIZATION"""
        self._node_id = node_id
        """The node ID of the node instance. DO NOT CHANGE AFTER INITIALIZATION"""
        self._graph = graph
        """Parent graph instance"""

        # Get factory from global DI service locator
        from haywire.core.di.config import get_library_system
        self._node_factory = get_library_system().get_node_factory()
        
        self._node_factory.add_event_subscriber(self.registry_key, self._on_node_lifecycle_event)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Lifecycle state
        self._state: NodeWrapperState = NodeWrapperState()

        self._node_cls: type['BaseNode'] | None = None
        self._node_instance: 'BaseNode' | None = None
        
        # Middleware support
        self._middleware: List[NodeMiddleware] = []
               
        # Store initial position for later initialization
        self._initial_position = position

        # Reference to structural validator from graph
        self._structural_validator: Optional['IStructuralValidator'] = (
            self._graph._structural
        )

        self._alternate_registry_keys: List[str] = []
        """Alternate registry keys for this node if the specific version is not available"""

        self._is_dirty_structural: bool = False
        self._is_dirty_data: bool = False

        self._import_node_cls()        

    @property  
    def node(self) -> 'BaseNode':
        """
        Get the current node instance with validation and migration.        
        Returns:
            BaseNode: The current node instance
        """
        with self._lock:                
            return self._node_instance

    def is_valid(self) -> bool:
        """Check if edge is valid"""
        return self._state.is_valid()

    @property
    def state(self) -> Optional[NodeWrapperState]:
        """Get the Edge state"""
        return self._state

    @property
    def node_id(self) -> Optional[NodeWrapperState]:
        """Get the node id"""
        return self._node_id


    def set_as_registered(self, is_registered: bool) -> None:
        """
        Set the node as registered with the graph.
        
        Args:
            is_registered: True if the node is registered
        """
        with self._lock:
            self._state.is_registered = is_registered

    # ========================================================================= 
    # House Keeping & Validation
    # =========================================================================
    
    def _import_node_cls(self):
        """
        gets the node class and import error, if any
        """
        self._node_cls, self._state.error_import = self._node_factory.get_node(self.registry_key)
        if self._state.error_import:
            self._state.is_imported = False
            self._alternate_registry_keys = self._node_factory.get_alternate_node_registry_keys(
                self.registry_key)
        else:
            self._state.is_imported = True
    
    def _rebuild(self, registry_key: str) -> None:
        """
        Rebuild the node wrapper for a new registry key."""
        with self._lock:
            self.registry_key = registry_key
            self._import_node_cls()
            node_info = self._node_instance._to_dict()
            self.build(node_info)
            # Tell graph about need for hot reload
            if self._graph:
                self._graph._validation.mark_node_dirty(
                    self._node_id,
                    ChangeReason.NODE_HOT_RELOADED
                )

    def build(self, node_info: Optional[Dict[str, Any]] = None):
        """
        Build node from class.
        This includes instantiation, initialization, and testing of the node.
        Args:
            node_info: Optional serialized node data for deserialization
        """
        logger.debug(
            f"Start node building: {self._node_id} ... "
        )

        self._state._clear_errors()

        if self._instantiate():
            if self._initialize(node_info):
                if self._structural_validation():
                    if self._test():
                        logger.debug(
                            f"Node building succeeded: {self._node_id}"
                        )
                        return
        
        logger.debug(
            f".. building failed with errors."
        )

    def _instantiate(self) -> bool:
        """
        Instantiate the node instance from the node class.        
        Returns:
            True if instantiation succeeded, False otherwise
        """
        try:
            if self._node_instance:
                self._node_instance._cleanup()
                self._node_instance = None

            self._node_instance = self._node_cls(self._node_id, self)
            self._node_instance.ui.state.set_position(self._initial_position)
            self._state.is_instantiated = True
            self._state.error_instantiate = None

            return True
        
        except Exception as e:
            # Create detailed error with context about the node instantiation
            self._state.error_instantiate = HaywireException.from_exception(
                exception=e,
                operation="Instantiate Node",
                message=f"Failed to instantiate node '{self.registry_key}'"
            ).enrich(
                module_name=self._node_cls.__module__,
                registry_key=self.registry_key,
                class_name=self._node_cls.__name__,
                library_identity=self._node_cls.class_library
            )
            self._state.error_instantiate.log()
            self._state.is_instantiated = False

        return False

    def _initialize(self, node_info: Optional[Dict[str, Any]] = None) -> bool:
        """
        Initializes the node after instantiation to its default setup
        by either calling the nodes initialize() method or using the 
        serialized node_info to restore its state.
        Args:
            node_info: Optional serialized node data for deserialization
        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            if node_info:
                self._node_instance._initialize_from_dict(node_info)
            else:   
                self._node_instance.init()
            self._node_instance.on_init()
            self._state.is_initialized = True
            self._state.error_initialize = None
            return True
        except Exception as e:
            self._state.error_initialize = HaywireException.from_exception(
                exception=e,
                operation="Initialize Node",
                message=f"Failed to initialize node '{self.registry_key}'"
            ).enrich(
                _node_id=self._node_id,
                registry_key=self.registry_key,
                module_name=self._node_cls.__module__,
                library_identity=self._node_cls.class_library
            )
            self._state.error_initialize.log()
            self._state.is_initialized = False

        return False

    def _structural_validation(self) -> bool:
        """
        Validate structural constraints for this node.
        
        Uses the graph's structural validator to check domain-specific rules
        such as event node constraints, control flow topology, etc.
        
        Returns:
            True if validation passed, False otherwise
        """
        try:
            # Call structural validator
            (
                is_valid,
                error_message,
                suggestions
            ) = self._structural_validator.validate_node(self)
            
            # Update state
            self._state.is_structural = is_valid
            
            # Create exception from error message if validation failed
            if not is_valid and error_message:
                self._state.error_structural = HaywireException.create(
                    message=error_message
                ).enrich(
                    node_id=self._node_id,
                    registry_key=self.registry_key,
                    module_name=self._node_cls.__module__,
                    library_identity=self._node_cls.class_library,
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
                node_id=self._node_id,
                registry_key=self.registry_key,
                module_name=self._node_cls.__module__,
                library_identity=self._node_cls.class_library,
                operation="Structural Validation",
                category="Structural Validation Error",
                suggestions=[
                    "Check node type and event node constraints",
                    "Verify control flow requirements if applicable"
                ]
            )
            self._state.error_structural.log()
            self._state.is_structural = False
            return False

    def _test(self) -> bool:
        """
        test the node after initialization                
        Returns:
            True if test was run without errors, False otherwise
        """

        try:
            # Execute adapter chain with performance tracking

            if self._node_instance:
                start_time = time.perf_counter()
                success, error =self._node_instance.on_testrun()
            
                # Update metrics
                execution_time = (time.perf_counter() - start_time) * 1000000.0
                self._state.test_execution_time_ns = execution_time

                self._state.has_test_passed = success
                if not success and error:
                    self._state.error_test = HaywireException.create(
                        message=f"Node test execution failed: {error}"
                    ).enrich(
                        module_name=self._node_cls.__module__,
                        registry_key=self.registry_key,
                        operation="Node Test Execution",
                        category="Node Execution Error",
                        suggestions=[
                            "Check the test() method implementation",
                            "Ensure all required ports exist"
                        ]
                    )                
                else:
                    self._state.error_test = None
                
                return success
            
        except Exception as e:

            self._state.error_test = HaywireException.from_exception(
                exception=e,
                message=f"Node test execution failed: {e}"
            ).enrich(
                operation="Node Test Execution",
                category="Node Execution Error"
            )
            self._state.error_test.log()
            self._state.has_test_passed = False
            
        return False

    def _on_node_lifecycle_event(self, lc_event: LifeCycleEvent) -> None:
        """
        Handle event notification from factory.
        
        Args:
            event: The life cycle event with complete context
        """
        with self._lock:
            logging.info(
                f"NodeWrapper {self._node_id}: Detected life cycle event - "
                f"{lc_event.event_type.value}"
            )
            
            if lc_event.is_warning_event():
                if lc_event.is_removal():
                    # The registry doesn't flag this as an error, but we 
                    # cannot use the node anymore. Therefore generate our 
                    # own error state and enhance the event
                    self._state.error_import = HaywireException(
                        operation="Node Removed",
                        message=(
                            f"Node '{self.registry_key}' has been removed "
                            f"from the registry and can no longer be used."
                        ),
                    ).enrich(
                        _node_id=self._node_id,
                        registry_key=self.registry_key,
                        module_name=lc_event.module_name,
                        library_identity=lc_event.library_identity,                            
                        suggestions=[
                                "Re-add the node class to the registry",
                            ],
                        )
                else:
                    self._state.error_import = lc_event.error

                if self._state.error_import:
                    self._state.error_import.log()

                # Tell graph about error 
                if self._graph:
                    self._graph._validation.mark_node_dirty(
                        self._node_id,
                        ChangeReason.NODE_HOT_RELOAD_ERROR
                    )
                return  # abort further processing
            
            # Successful reload - mark for migration
            self._node_cls = lc_event.affected_class
            self._state.error_import = None
            self._state.is_imported = True
            
            # Tell graph about need for hot reload
            if self._graph:
                self._graph._validation.mark_node_dirty(
                    self._node_id,
                    ChangeReason.NODE_HOT_RELOADED
                )

    def cleanup(self) -> None:
        """Full cleanup when wrapper is being destroyed"""
        with self._lock:
            # Remove event subscription
            self._node_factory.remove_event_subscriber(
                self.registry_key, self._on_node_lifecycle_event
            )
                        
            self._middleware.clear()
            self._state = None
            self._node_cls = None
            self._node_factory = None
            if self._node_instance:
                self._node_instance._cleanup()
                self._node_instance = None
            self._graph = None

    def validate(self) -> List[str]:
        """
        Validate node and return list of issues.
        
        Returns:
            List of validation issue descriptions
        """
        with self._lock:
            issues = []
            
            if not self._state.is_valid():
                issues.append("Node instance is not safe to use")
                            
            if self._state.error:
                issues.append(f"Error state: {self._state.error}")
            
            if not self._state.is_instantiated:
                issues.append("Wrapper node is not instantiated")
            
            # Additional validation can be added here
            # e.g., pin compatibility, data types, etc.
            
            return issues

    # =========================================================================
    # RUNTIME OPERATIONS
    # =========================================================================
 
    def move(self, new_x: float, new_y: float):
        """
        Move internal node instance and set the default position

        Args:
            new_x: New X position
            new_y: New Y position
        """
        self._initial_position = (new_x, new_y)
        if self._node_instance:
            self._node_instance.ui.state.set_position(self._initial_position)

    def add_middleware(self, middleware: NodeMiddleware) -> None:
        """Add middleware to the wrapper"""
        with self._lock:
            self._middleware.append(middleware)
    
    def remove_middleware(self, middleware: NodeMiddleware) -> None:
        """Remove middleware from the wrapper"""
        with self._lock:
            if middleware in self._middleware:
                self._middleware.remove(middleware)
    
    def _add_runtime_error(self, error: HaywireException) -> None:
        """Add a runtime error to the list and trigger redraw"""
        with self._lock:
            self._state.error_runtime.append(error)
            if len(self._state.error_runtime) == 1:
                # First error - trigger redraw
                self.redraw()

    def _get_all_runtime_errors(self) -> List[HaywireException]:
        """Get all runtime errors"""
        with self._lock:
            return list(self._state.error_runtime)

    def _clear_runtime_errors(self) -> None:
        """Clear all runtime errors and trigger redraw if any existed"""
        with self._lock:
            if self._state.error_runtime:
                # Errors cleared - trigger redraw
                self.redraw()
            self._state.error_runtime.clear()
    
    def _startup(self, exec_ctx: 'ExecutionContext') -> None:
        """
        wrapper startup logic before execution

        this method catches any exceptions during startup
        """
        self._clear_runtime_errors()

        try:
            self._node_instance.on_startup(exec_ctx)
        except Exception as e:
            error = HaywireException.from_exception(
                exception=e,
                operation="Node Startup",
                message=f"Error during startup of node '{self.node.identity.label}'"
            ).enrich(
                _node_id=self._node_id,
                registry_key=self.registry_key,
                module_name=self._node_cls.__module__,
                library_identity=self._node_cls.class_library
            )
            error.log()
            self._add_runtime_error(error)

    def _shutdown(self, exec_ctx: 'ExecutionContext') -> None:
        """
        wrapper shutdown logic before execution

        This method catches any exceptions during shutdown
        """
        try:
            self._node_instance.on_shutdown(exec_ctx)
        except Exception as e:
            error = HaywireException.from_exception(
                exception=e,
                operation="Node Shutdown",
                message=f"Error during shutdown of node '{self.node.identity.label}'"
            ).enrich(
                _node_id=self._node_id,
                registry_key=self.registry_key,
                module_name=self._node_cls.__module__,
                library_identity=self._node_cls.class_library
            )
            error.log()
            self._add_runtime_error(error)

    def _execute(self, exec_ctx: 'ExecutionContext') -> str | None:
        """
        Execute the node's transform method within the given execution context.
        
        Args:
            exec_ctx: The execution context for this run
            
        Returns:
            Outlet ID to follow, or None
        """
        try:
            if self._node_instance.behavior.is_data_node:
                if not self._is_dirty_data:
                    logger.debug(f"Skipping {self._node_id} (not dirty)")
                    return None  # No execution needed
                self._is_dirty_data = False  # Reset dirty flag

            self._node_instance.on_validate(exec_ctx)

            return self._node_instance._execute(exec_ctx)
        
        except Exception as e:
            error = HaywireException.from_exception(
                exception=e,
                operation="Node Execution",
                message=f"Error executing node '{self.node.identity.label}'"
            ).enrich(
                _node_id=self._node_id,
                registry_key=self.registry_key,
                module_name=self._node_cls.__module__,
                library_identity=self._node_cls.class_library
            )
            error.log()
            self._add_runtime_error(error)
            return None
 
        #return self._execute_with_middleware('transform', exec_ctx)

    def _execute_with_middleware(self, method_name: str, *args) -> Any:
        """Execute a method with middleware hooks"""
        # Before hooks
        for middleware in self._middleware:
            try:
                middleware.before_method(self, method_name, *args)
            except Exception as e:
                HaywireException.from_exception(
                    exception=e,
                    message=f"Error in before middleware for {self._node_id}.{method_name}"
                ).log()
        
        # Execute method (placeholder - actual implementation would call real methods)
        result = None
        
        # After hooks  
        for middleware in reversed(self._middleware):
            try:
                middleware.after_method(self, method_name, result)
            except Exception as e:
                HaywireException.from_exception(
                    exception=e,
                    message=f"Error in after middleware for {self._node_id}.{method_name}"
                ).log()
        
        return result

    def mark_as_data_dirty(self) -> None:
        """
        Called by ports when their value changes to indicate 
        the requirement for executing the worker method
        """
        self._is_dirty_data = True

    def mark_as_structuraly_dirty(self) -> None:
        """
        Mark the node as structurally dirty, requiring re-validation.

        This is required to be called when the node 
        changes its inlets or outlets.
        """
        # Notify graph of redraw request
        if self._graph and not self._is_dirty_structural:
            self._graph._validation.mark_node_dirty(
                self._node_id,
                ChangeReason.NODE_VALIDATION_REQUESTED
            )
            self._is_dirty_structural = True

    def _housekeeping(self) -> None:
        """
        Perform housekeeping of the node and its ports.
        Should only be called by the graph validation or 
        after deserialization, but not from inside a node.

        This includes the rebuild of the port pipelines
        """
        with self._lock:
            if self._node_instance:
                if self._is_dirty_structural:
                    self._node_instance._housekeeping()
                    self._is_dirty_structural = False


    def redraw(self) -> None:
        """
        Request a redraw of the node in the UI.
        """
        # Notify graph of redraw request
        if self._graph:
            self._graph._validation.mark_node_dirty(
                self._node_id,
                ChangeReason.NODE_REDRAW_REQUESTED
            )

    def request_graph_reassembly(self) -> None:
        """
        Request a reassembly of the flow from the graph.
        This will notify the flow assembler to regenerate the flow structure.
        It will not trigger any rebuild or redraw of the graph. 

        This is needed when a setting inside the node was changed and the flow
        assembler needs this information to build the flow.

        if the node has changed its inlet or outlet structure, use 
        mark_as_structuraly_dirty() instead.
        """
        # Notify graph of reassembly request
        if self._graph:
            self._graph._validation.mark_graph_dirty(
                ChangeReason.GRAPH_REQUIRE_REASSEMBLY
            )


    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize wrapper state for graph save.
        
        Returns:
            Dictionary containing wrapper and node state
        """
        with self._lock:
            if self._node_instance:
                self._node_instance.on_saved()

            result = {
                'node_id': self._node_id,
                'registry_key': self.registry_key,
                'position': list(self._initial_position),
            }
            
            # Serialize node instance if available
            if self._node_instance:
                result['node_data'] = self._node_instance._to_dict()
            
            return result
    
    def __repr__(self) -> str:
        return (
            f"NodeWrapper(id={self._node_id}, "
            f"registry_key={self.registry_key}, valid={self._state.is_valid()})"
        )