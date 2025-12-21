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

from ..errors import HaywireException
from ..registry.lifecycle_event import (
    LifeCycleEvent,
    LifeCycleEventType,
    LiveCycleBatchCallback,
    LiveCycleEventCallback
)

if TYPE_CHECKING:
    from .base import BaseNode
    from ..graph.base import BaseGraph
    from .factory import NodeFactory

@dataclass
class NodeWrapperState:
    """Lifecycle state of wrapper and its node instance"""
    is_instantiated: bool = False
    """The node instance has been created"""
    is_valid: bool = True
    """The node instance is safe to use"""
    is_executing: bool = False
    last_hot_reload: float = 0.0
    history: List[LifeCycleEvent] = field(default_factory=list)
    error: Optional['HaywireException'] = None
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
        """The node ID of the node instance. DO NOT CHANGE AFTER INITIALIZATION"""
        self.registry_key = registry_key
        """The registry key of the node class. DO NOT CHANGE AFTER INITIALIZATION"""
        self._node_factory = node_factory
        self._node_factory.add_event_subscriber(self.registry_key, self._listen_on_livecycle_event)
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Lifecycle state
        self.state: NodeWrapperState = NodeWrapperState(creation_time=time.time())
        self._node_instance: Optional['BaseNode'] = None
        
        # Change notification callbacks
        self._livecycle_subscribers: List[LiveCycleEventCallback] = []

        # Middleware support
        self._middleware: List[NodeMiddleware] = []
               
        # Store initial position for later initialization
        self._initial_position = position
        
        self.graph: Optional['BaseGraph' | None] = None

    def initialize(self, graph: 'BaseGraph') -> Optional['NodeWrapper']:
        """
        Initialize the wrapper by creating the node instance.
        
        This is separate from __init__ to allow for deferred instantiation
        and better error handling during creation. Does NOT add wrapper to
        graph - that's the caller's responsibility.
        
        Args:
            graph: The graph this wrapper belongs to
            
        Returns:
            Self if initialization succeeded, None if failed
        """
        with self._lock:
            if self.state.is_instantiated:
                return self if self.state.is_valid else None
            
            self.graph = graph

            self.node_id = graph.generate_unique_node_id()

            _instance, _event = self._create_node_instance()

            if _instance:
                self._node_instance = _instance
                self._node_instance.ui_state.posX = self._initial_position[0]
                self._node_instance.ui_state.posY = self._initial_position[1]
                self.state.is_valid = True
                self.state.history.append(_event)
                self.state.error = _event.error
                self.state.is_instantiated = True
                self._notify_change(_event)
                return self
            else:
                return None

    def cleanup(self) -> None:
        """Full cleanup when wrapper is being destroyed"""
        with self._lock:
            # Remove event subscription
            self._node_factory.remove_event_subscriber(
                self.registry_key, self._listen_on_livecycle_event
            )
                        
            self._livecycle_subscribers.clear()
            self._middleware.clear()
            self.state.is_valid = False
            self.state.is_instantiated = False
            self.graph = None
            self._node_factory = None
            self._node_instance = None

    def _listen_on_livecycle_event(self, lc_event: LifeCycleEvent) -> None:
        """
        Handle event notification from factory.
        
        Args:
            event: The live cycle event with complete context
        """
        # Only process if initialized
        if self.state.is_instantiated:
            # Filter: Only care about events matching our registry key
            if not lc_event.matches_registry_key(self.registry_key):
                logging.warning(
                    f"NodeWrapper {self.node_id}: Received unrelated live "
                    f"cycle event for {lc_event.registry_key}"
                )
                return
                
            with self._lock:
                logging.info(
                    f"NodeWrapper {self.node_id}: Detected live cycle event - "
                    f"{lc_event.event_type.value}"
                )
                
                if lc_event.is_successful_event():
                    # Successful reload - mark for migration
                    _instance, event = self._generate_node_instance(lc_event)

                    if _instance is not None:
                        # get current position
                        position = (
                            self._node_instance.ui_state.posX,
                            self._node_instance.ui_state.posY
                        )
                        self._node_instance = _instance
                        # restore position
                        self._node_instance.ui_state.posX = position[0]
                        self._node_instance.ui_state.posY = position[1]
                        
                        self.state.is_instantiated = True
                        self.state.is_valid = True
                        self.state.last_hot_reload = time.time()
                        self.state.hot_reload_count += 1
                    else:
                        self.state.is_valid = False

                    self.state.error = event.error
                    self.state.history.append(event)                      
                    # Forward the event to UI components
                    self._notify_change(event)
                
                else:
                    self.state.is_valid = False
                    if lc_event.is_removal():
                        # The registry doesn't flag this as an error, but we 
                        # cannot use the node anymore. Therefore generate our 
                        # own error state and enhance the event
                        error = HaywireException(
                            operation="Node Removed",
                            message=(
                                f"Node '{self.registry_key}' has been removed "
                                f"from the registry and can no longer be used."
                            ),
                        ).enrich(
                            node_id=self.node_id,
                            registry_key=self.registry_key,
                            module_name=lc_event.module_name,
                            library_identity=lc_event.library_identity,                            
                            suggestions=[
                                    "Re-add the node class to the registry",
                                ],
                            )
                        lc_event = lc_event.clone()
                        lc_event.error = error

                    self.state.error = lc_event.error
                    self.state.history.append(lc_event)                      
                    # Forward the event to UI components
                    self._notify_change(lc_event)

    def _create_node_instance(self) -> tuple['BaseNode', LifeCycleEvent]:
        """
        Utility internal method to create a node instance.
        
        This method works a wrapper method for the _generate_node_instance method.
        It is used during initial registration to create the node instance.
                    
        Returns:
            A tuple of (created node instance, lifecycle event)
        """

        lc_event: LifeCycleEvent = self._node_factory.get_node_event(self.registry_key)
        
        return self._generate_node_instance(lc_event)

    def _generate_node_instance(
        self, lc_event: LifeCycleEvent, _is_error: bool = False
    ) -> tuple['BaseNode', LifeCycleEvent]:
        """
        Generate a node instance based on the lifecycle event.

        Args:
            event: The lifecycle event with class information
        Returns:
            A tuple of (created node instance, lifecycle event)
        """

        event = lc_event

        node_cls = lc_event.affected_class

        node_instance: 'BaseNode' | None = None

        # Create the node instance 
        try:
            if not lc_event.has_class_available():
                node_cls = self._node_factory.get_error_node()

            node_instance = node_cls(self.node_id, self)
        
        except Exception as e:
            # Create detailed error with context about the node instantiation
            error = HaywireException.from_exception(
                exception=e,
                operation="Instantiate Node",
                message=f"Failed to instantiate node '{self.registry_key}'"
            ).enrich(
                module_name=event.module_name,
                registry_key=self.registry_key,
                class_name=node_cls.__name__,
                library_identity=event.library_identity
            ).log()
            node_cls = self._node_factory.get_error_node()
            event = lc_event.create_derived_event(
                error=error,
                affected_class=node_cls,
                event_type=LifeCycleEventType.CLASS_INSTANTIATION_FAILED
                )
            
            if _is_error:
                # Prevent infinite recursion. If there is something wrong with the error node,
                # we cannot recover from this.
                return None, event
            
            if self.state.is_instantiated:
                # If we already had an instance, we dont need to proceed further
                return None, event
            
            # Create error node instance
            return self._generate_node_instance(event, _is_error=True)

        return node_instance, event
 
    
    @property  
    def node(self) -> 'BaseNode':
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
                issues.append("Node instance is not safe to use")
                            
            if self.state.error:
                issues.append(f"Error state: {self.state.error}")
            
            if not self.state.is_instantiated:
                issues.append("Wrapper node is not instantiated")
            
            # Additional validation can be added here
            # e.g., pin compatibility, data types, etc.
            
            return issues
    
    def add_livecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """Add subscriber for wrapper state changes (hot reload events)"""
        with self._lock:
            if callback not in self._livecycle_subscribers:
                self._livecycle_subscribers.append(callback)
    
    def remove_livecycle_subscriber(self, callback: LiveCycleBatchCallback) -> None:
        """Remove subscriber for wrapper state changes (hot reload events)"""
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
                
    def _notify_change(self, event: LifeCycleEvent) -> None:
        """
        Notifies all subscribers of wrapper state change.
        
        Args:
            event: The live cycle event to propagate to observers
        """
        # Copy to avoid modification during iteration
        for callback in self._livecycle_subscribers[:]:
            callback(event)
    
    def recall_change(self, callback: LiveCycleBatchCallback) -> None:
        """
        Recall all past lifecycle events to a new subscriber.
        
        Args:
            callback: The callback to notify of past events
        """
        with self._lock:
            callback(self.state.history[-1])

    def _execute_with_middleware(self, method_name: str, *args) -> Any:
        """Execute a method with middleware hooks"""
        # Before hooks
        for middleware in self._middleware:
            try:
                middleware.before_method(self, method_name, *args)
            except Exception as e:
                HaywireException.from_exception(
                    exception=e,
                    message=f"Error in before middleware for {self.node_id}.{method_name}"
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
                    message=f"Error in after middleware for {self.node_id}.{method_name}"
                ).log()
        
        return result
    
    def __repr__(self) -> str:
        return (
            f"NodeWrapper(id={self.node_id}, "
            f"registry_key={self.registry_key}, valid={self.state.is_valid})"
        )