"""
NodeWrapper - Complete lifecycle management for Haywire nodes.

This wrapper manages the complete lifecycle of a HaywireNode instance,
including creation, hot reload, serialization, and cleanup.
"""
import time
import threading
import logging
from typing import List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

from ..graph.types import ChangeReason
from ..library.utils import get_registry_id_from_key
from ..errors import HaywireException
from ..registry.lifecycle_event import LifeCycleEvent

if TYPE_CHECKING:
    from .base import BaseNode
    from ..graph.base import BaseGraph
    from .factory import NodeFactory

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
    error_custom: Optional[HaywireException] = None
    """node custom error """
    error_test: Optional[HaywireException] = None
    """node test error"""
    test_execution_time_ns: float = 0.0
    """Last transform() execution time"""


    def is_valid(self) -> bool:
        """Check if node is in valid state (initialized and tested)"""
        return (self.is_registered and 
            self.is_imported and
            self.is_instantiated and
            self.is_initialized and
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
        elif self.error_test:
            return self.error_test
        elif self.error_custom:
            return self.error_custom
        else:
            return None
        
    def _clear_errors(self) -> None:
        """Clear all error states"""
        self.error_import = None
        self.error_instantiate = None
        self.error_initialize = None
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
                 node_factory: 'NodeFactory',
                 position: Tuple[float, float] = (100, 100)):
        """
        Initialize a new NodeWrapper.
        
        Args:
            registry_key: Registry key for the node class
            node_factory: Factory for creating node instances  
            initial_position: Optional[Tuple[float, float]] = None):
        """
        self._node_id = "unregistered"
        """The node ID of the node instance. DO NOT CHANGE AFTER INITIALIZATION"""
        self.registry_key = registry_key
        """The registry key of the node class. DO NOT CHANGE AFTER INITIALIZATION"""
        self._node_factory = node_factory
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
        
        self._graph: Optional['BaseGraph' | None] = None

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


    def instantiate(self, graph: 'BaseGraph') -> bool:
        """
        Initialize the wrapper.
        
        This is separate from __init__ to allow for deferred instantiation
        and better error handling during creation. Does NOT add wrapper to
        graph - that's the caller's responsibility.
        
        Args:
            graph: The graph this wrapper belongs to
            
        Returns:
            True if initialization succeeded, False otherwise
        """
        with self._lock:
            if self._state.is_instantiated:
                return True  # already instantiated

            self._import_node_cls()

            self._graph = graph
            self._node_id = graph.generate_unique_node_id(get_registry_id_from_key(self.registry_key))

            return True
        
    def _import_node_cls(self):
        """
        gets the node class and import error, if any
        """
        self.node_cls, self._state.error_import = self._node_factory.get_node(self.registry_key)
        self._state.is_imported = True
        
    def build(self):
        """
        Build node wrapper
        """
        logger.debug(
            f"Start node rebuilding: {self._node_id} ... "
        )

        self._state._clear_errors()

        if self._instantiate():
            if self._initialize():
                if self._test():
                    logger.debug(
                        f"Node rebuilding succeeded: {self._node_id}"
                    )
                    return
        
        logger.debug(
            f".. rebuilding failed with errors."
        )

    def _instantiate(self) -> bool:
        """
        Instantiate the node instance from the node class.        
        Returns:
            True if instantiation succeeded, False otherwise
        """
        try:
            self._node_instance = self.node_cls(self._node_id, self)
            self._node_instance.ui_state.posX = self._initial_position[0]
            self._node_instance.ui_state.posY = self._initial_position[1]
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
                module_name=self.node_cls.__module__,
                registry_key=self.registry_key,
                class_name=self.node_cls.__name__,
                library_identity=self.node_cls.class_library
            )
            self._state.error_instantiate.log()
            self._state.is_instantiated = False

        return False

    def _initialize(self) -> bool:
        """
        Initializes the node after instantiation to its default setup
        by calling the nodes initialize() method.
        Returns:
            True if initialization succeeded, False otherwise
        """
        try:
            self.node.initialize()
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
                module_name=self.node_cls.__module__,
                library_identity=self.node_cls.library_identity
            )
            self._state.error_initialize.log()
            self._state.is_initialized = False

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
                success, error =self._node_instance.test()
            
                # Update metrics
                execution_time = (time.perf_counter() - start_time) * 1000000.0
                self._state.test_execution_time_ns = execution_time

                self._state.has_test_passed = success
                if not success and error:
                    self._state.error_test = HaywireException.create(
                        message=f"Node test execution failed: {error}"
                    ).enrich(
                        module_name=self.node_cls.__module__,
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
            self._node_instance = None
            self._graph = None

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
            self.node_cls = lc_event.affected_class
            self._state.error_import = None

            # Tell graph about error
            if self._graph:
                self._graph._validation.mark_node_dirty(
                    self._node_id,
                    ChangeReason.NODE_HOT_RELOADED
                )

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

    def move(self, new_x: float, new_y: float):
        """
        Move internal node instance and set the default position

        Args:
            new_x: New X position
            new_y: New Y position
        """
        self._initial_position = (new_x, new_y)
        if self._node_instance:
            self._node_instance.ui_state.posX = new_x
            self._node_instance.ui_state.posY = new_y

    def add_middleware(self, middleware: NodeMiddleware) -> None:
        """Add middleware to the wrapper"""
        with self._lock:
            self._middleware.append(middleware)
    
    def remove_middleware(self, middleware: NodeMiddleware) -> None:
        """Remove middleware from the wrapper"""
        with self._lock:
            if middleware in self._middleware:
                self._middleware.remove(middleware)
                
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
    
    def __repr__(self) -> str:
        return (
            f"NodeWrapper(id={self._node_id}, "
            f"registry_key={self.registry_key}, valid={self._state.is_valid()})"
        )