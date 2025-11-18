"""
NodeWrapper - Complete lifecycle management for Haywire nodes.

This wrapper manages the complete lifecycle of a HaywireNode instance,
including creation, hot reload, serialization, and cleanup.
"""
import time
import uuid
import threading
import logging
from typing import Dict, List, Optional, Tuple, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from copy import deepcopy

from haywire.core.errors.haywire_error import HaywireError
from haywire.core.errors.utils import generate_haywire_error

from .base_node import BaseNode
from ..errors import log_detailed_error
from ..library.hot_reload_event import LifeCycleEvent, LifeCycleEventType, LiveCycleBatchCallback, LiveCycleEventCallback

if TYPE_CHECKING:
    from ..graph.graph import HaywireGraph
    from .node_factory import NodeFactory


@dataclass
class NodeWrapperState:
    """Tracks the lifecycle state of a wrapped node"""
    is_valid: bool = True
    needs_migration: bool = False
    is_executing: bool = False
    last_hot_reload: float = 0.0
    history: List[LifeCycleEvent] = field(default_factory=list)
    error: Optional[HaywireError | None] = None
    creation_time: float = 0.0
    execution_count: int = 0
    hot_reload_count: int = 0


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
        self.node_id = "unregistered"
        self.registry_key = registry_key
        self.node_factory = node_factory
        self.node_factory.add_event_subscriber(self.registry_key, self._listen_on_livecycle_event)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Lifecycle state
        self.state: NodeWrapperState = NodeWrapperState(creation_time=time.time())
        self._node_instance: Optional[BaseNode] = None
        
        # Change notification callbacks
        self._livecycle_subscribers: List[LiveCycleEventCallback] = []

        # Middleware support
        self._middleware: List[NodeMiddleware] = []
        
        # Resource management
        self._allocated_resources: List[Any] = []
        
        # Store initial position for later initialization
        self._initial_position = position
        
        # Flag to track if we've been initialized
        self._initialized = False

        self.graph: Optional['HaywireGraph' | None] = None

    def register(self, graph: 'HaywireGraph') -> bool:
        """
        Initialize the wrapper by creating the node instance.
        
        This is separate from __init__ to allow for deferred instantiation
        and better error handling during creation.
        
        Returns:
            bool: True if initialization succeeded, False if no node was created
        """
        with self._lock:
            if self._initialized:
                return self.state.is_valid
            
            self.graph = graph

            self.node_id = graph.generate_unique_node_id()

            _instance, _event = self.get_instance()

            if _instance is not None:
                self._node_instance = _instance
                self._node_instance.ui_state.posX = self._initial_position[0]
                self._node_instance.ui_state.posY = self._initial_position[1]
                self.state.is_valid = True
                self.state.needs_migration = False
                self.state.history.append(_event)
                self.state.error = _event.error
                self._initialized = True
                self.graph.add_node_wrapper(self)
                self._notify_change(_event)
                return True
            else:               
                return False

    def cleanup(self) -> None:
        """Full cleanup when wrapper is being destroyed"""
        with self._lock:
            # Remove event subscription
            self.node_factory.remove_event_subscriber(self.registry_key, self._listen_on_livecycle_event)
            
            # Clean up resources
            for resource in self._allocated_resources:
                try:
                    if hasattr(resource, 'cleanup'):
                        resource.cleanup()
                    elif hasattr(resource, 'close'):
                        resource.close()
                except Exception as e:
                    log_detailed_error(f"Failed to cleanup resource in {self.node_id}", e)
            
            self._allocated_resources.clear()
            self._livecycle_subscribers.clear()
            self._middleware.clear()
            self._node_instance = None
            self.state.is_valid = False
            self.graph = None
            self._node_instance = None
            self._initialized = False
            self.node_factory = None

    def _listen_on_livecycle_event(self, lc_event: LifeCycleEvent) -> None:
        """
        Handle event notification from factory.
        
        Args:
            event: The live cycle event with complete context
        """
        # Only process if initialized
        if self._initialized:
            # Filter: Only care about events matching our registry key
            if not lc_event.matches_registry_key(self.registry_key):
                logging.warning(
                    f"NodeWrapper {self.node_id}: Received unrelated live cycle event for {event.registry_key}"
                )
                return
                
            with self._lock:
                logging.info(
                    f"NodeWrapper {self.node_id}: Detected live cycle event - {lc_event.event_type.value}"
                )
                
                event = lc_event

                if lc_event.is_successful_event():
                    # Successful reload - mark for migration
                    _instance, event = self._generate_node_instance(lc_event)

                    if _instance is not None:
                        self._node_instance = _instance
                        self.state.is_valid = True
                        self.state.needs_migration = True
                        self.state.last_hot_reload = time.time()
                        self.state.hot_reload_count += 1
                
                else:
                    self.state.needs_migration = False
                    self.state.is_valid = False

                self.state.error = event.error
                self.state.history.append(event)                      
                # Forward the event to UI components
                self._notify_change(event)


    def get_instance(self) -> tuple[BaseNode | None, LifeCycleEvent]:
        """
        Pure utility method to create a node instance.
        
        This method only creates the node instance and tracks it for hot reload.
        It does not add the node to any graph or interact with undo systems.
                    
        Returns:
            A tuple of (created node instance, lifecycle event)
        """

        lc_event: LifeCycleEvent = self.node_factory.get_node_event(self.registry_key)
        
        return self._generate_node_instance(lc_event)

    def _generate_node_instance(self, lc_event: LifeCycleEvent) -> tuple[BaseNode | None, LifeCycleEvent]:
        """
        Generate a node instance based on the lifecycle event.

        Args:
            event: The lifecycle event with class information
        Returns:
            A tuple of (created node instance, lifecycle event)
        """

        event = lc_event

        node_cls = lc_event.affected_class

        node_instance: BaseNode | None = None

        if not lc_event.has_class_available():
            node_cls = self.node_factory.get_error_node()

        # Create the node instance 
        try:
            node_instance = node_cls(self.node_id, self)
        
        except Exception as e:
            # Create detailed error with context about the node instantiation
            error = log_detailed_error(
                exception=e,
                operation="Instantiate Node",
                module_name=event.module_name,
                registry_key=self.registry_key,
                class_name=node_cls.__name__,
                library_identity=event.class_library,
                message=f"Failed to instantiate node '{self.registry_key}'"
            )
            event = lc_event.create_derived_event(
                error=error,
                error_info=str(e),
                affected_class=node_cls,
                event_type=LifeCycleEventType.CLASS_INSTANTIATION_FAILED
                )

        return node_instance, event
 
    
    @property  
    def node(self) -> BaseNode:
        """
        Get the current node instance with validation and migration.
        
        Returns:
            BaseNode: The current node instance

        """
        with self._lock:                
            return self._node_instance
    
   
    def validate(self) -> List[str]:
        """
        Validate node and return list of issues.
        
        Returns:
            List of validation issue descriptions
        """
        with self._lock:
            issues = []
            
            if not self.state.is_valid:
                issues.append("Node instance is invalid")
            
            if self.state.needs_migration:
                issues.append("Node needs hot reload migration")
                
            if self.state.error:
                issues.append(f"Error state: {self.state.error}")
            
            if not self._initialized:
                issues.append("Wrapper not initialized")
            
            # Additional validation can be added here
            # e.g., pin compatibility, data types, etc.
            
            return issues
    
    def add_livecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """Add callback for wrapper state changes (hot reload events)"""
        with self._lock:
            if callback not in self._livecycle_subscribers:
                self._livecycle_subscribers.append(callback)
    
    def remove_livecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """Remove change callback"""
        with self._lock:
            if callback in self._livecycle_subscribers:
                self._livecycle_subscribers.remove(callback)
    
    def add_middleware(self, middleware: NodeMiddleware) -> None:
        """Add middleware to the wrapper"""
        with self._lock:
            self._middleware.append(middleware)
    
    def remove_middleware(self, middleware: NodeMiddleware) -> None:
        """Remove middleware from the wrapper"""
        with self._lock:
            if middleware in self._middleware:
                self._middleware.remove(middleware)
    
    def register_resource(self, resource: Any) -> None:
        """Register a resource for cleanup"""
        with self._lock:
            self._allocated_resources.append(resource)
            
    def _notify_change(self, event: LifeCycleEvent) -> None:
        """
        Notify subscribers of wrapper state change.
        
        Args:
            event: The live cycle event to propagate to observers
        """
        for callback in self._livecycle_subscribers[:]:  # Copy to avoid modification during iteration
            callback(event)
    
    def _execute_with_middleware(self, method_name: str, *args) -> Any:
        """Execute a method with middleware hooks"""
        # Before hooks
        for middleware in self._middleware:
            try:
                middleware.before_method(self, method_name, *args)
            except Exception as e:
                log_detailed_error(f"Error in before middleware for {self.node_id}.{method_name}", e)
        
        # Execute method (placeholder - actual implementation would call real methods)
        result = None
        
        # After hooks  
        for middleware in reversed(self._middleware):
            try:
                middleware.after_method(self, method_name, result)
            except Exception as e:
                log_detailed_error(f"Error in after middleware for {self.node_id}.{method_name}", e)
        
        return result
    
    def __repr__(self) -> str:
        return f"NodeWrapper(id={self.node_id}, registry_key={self.registry_key}, valid={self.state.is_valid})"