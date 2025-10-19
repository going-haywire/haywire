"""
NodeWrapper - Complete lifecycle management for Haywire nodes.

This wrapper manages the complete lifecycle of a HaywireNode instance,
including creation, hot reload, serialization, and cleanup.
"""
import time
import uuid
import threading
from typing import Dict, List, Optional, Tuple, Callable, Any, TYPE_CHECKING
from dataclasses import dataclass
from abc import ABC, abstractmethod
from copy import deepcopy

from .base_node import BaseNode
from ..errors import log_detailed_error, DetailedError

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
    error_state: Optional[str] = None
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
                 node_id: str,
                 registry_key: str,
                 node_factory: 'NodeFactory',
                 initial_position: Optional[Tuple[float, float]] = None):
        """
        Initialize a new NodeWrapper.
        
        Args:
            node_id: Unique identifier for this node instance
            registry_key: Registry key for the node class
            node_factory: Factory for creating node instances  
            initial_position: Optional initial position (x, y)
        """
        self.node_id = node_id
        self.registry_key = registry_key
        self.node_factory = node_factory
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Lifecycle state
        self.state = NodeWrapperState(creation_time=time.time())
        self._node_instance: Optional[BaseNode] = None
        
        # Change notification callbacks  
        self._change_callbacks: List[Callable[['NodeWrapper', str], None]] = []
        
        # Middleware support
        self._middleware: List[NodeMiddleware] = []
        
        # Resource management
        self._allocated_resources: List[Any] = []
        
        # Store initial position for later initialization
        self._initial_position = initial_position
        
        # Flag to track if we've been initialized
        self._initialized = False

    def initialize(self, position: Optional[Tuple[float, float]] = None) -> bool:
        """
        Initialize the wrapper by creating the node instance.
        
        This is separate from __init__ to allow for deferred instantiation
        and better error handling during creation.
        
        Returns:
            bool: True if initialization succeeded, False if error node was created
        """
        with self._lock:
            if self._initialized:
                return self.state.is_valid
                
            try:
                self._create_node_instance()
                self._setup_hot_reload_monitoring()

                self.node.ui_state.posX = position[0] if position else 0.0
                self.node.ui_state.posY = position[1] if position else 0.0
                self._initialized = True
                
                self._notify_change("initialized")
                return True
                
            except Exception as e:
                log_detailed_error(
                    operation="NodeWrapper Initialization",
                    logger=None,
                    message = f"Failed to initialize node wrapper {self.node_id}", 
                    exception = e)
                self.state.is_valid = False
                self.state.error_state = str(e)
                
                # Try to create error node as fallback
                try:
                    self._create_error_node()
                    self._initialized = True  
                    self._notify_change("initialized_with_error")
                    return False
                except Exception as e2:
                    log_detailed_error(f"Failed to create error node for {self.node_id}", e2)
                    self.state.error_state = f"Initialization failed: {e}, Error node failed: {e2}"
                    return False
    
    @property  
    def node(self) -> BaseNode:
        """
        Get the current node instance with validation and migration.
        
        Returns:
            BaseNode: The current node instance

        """
        with self._lock:                
            return self._node_instance
    
    def copy(self) -> 'NodeWrapper':
        """
        Create a copy of this wrapper with a new node instance.
        
        Returns:
            NodeWrapper: New wrapper with copied node data
        """
        with self._lock:
            # Generate new node ID
            new_node_id = f"node_{uuid.uuid4().hex[:8]}"
            
            # Create new wrapper (uninitialized)
            new_wrapper = NodeWrapper(
                node_id=new_node_id,
                registry_key=self.registry_key,
                node_factory=self.node_factory,
                initial_position=self._initial_position
            )
            
            # Initialize the new wrapper
            if new_wrapper.initialize():
                # Copy node state from current instance
                if self._node_instance:
                    try:
                        # Serialize current state and apply to new instance
                        current_state = self._node_instance.to_dict()
                        current_state['node_id'] = new_node_id  # Update ID
                        
                        new_wrapper._node_instance.load_state(current_state)
                        
                        # Copy middleware
                        new_wrapper._middleware = self._middleware.copy()
                        
                    except Exception as e:
                        log_detailed_error(f"Failed to copy node state to {new_node_id}", e)
            
            return new_wrapper
    
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the wrapper and its node to a dictionary.
        
        Returns:
            Dict containing all wrapper and node data
        """
        with self._lock:
            wrapper_data = {
                'node_id': self.node_id,
                'registry_key': self.registry_key,
                'state': {
                    'creation_time': self.state.creation_time,
                    'execution_count': self.state.execution_count,
                    'hot_reload_count': self.state.hot_reload_count,
                },
                'position': self._initial_position,
                'node_data': None
            }
            
            # Serialize node instance if it exists
            if self._node_instance:
                try:
                    wrapper_data['node_data'] = self._node_instance.to_dict()
                except Exception as e:
                    log_detailed_error(f"Failed to serialize node {self.node_id}", e)
                    wrapper_data['serialization_error'] = str(e)
            
            return wrapper_data
    
    def deserialize(self, data: Dict[str, Any]) -> bool:
        """
        Deserialize wrapper and node data from a dictionary.
        
        Args:
            data: Dictionary containing wrapper and node data
            
        Returns:
            bool: True if deserialization succeeded
        """
        with self._lock:
            try:
                # Restore wrapper metadata
                if 'state' in data:
                    state_data = data['state']
                    self.state.creation_time = state_data.get('creation_time', time.time())
                    self.state.execution_count = state_data.get('execution_count', 0)
                    self.state.hot_reload_count = state_data.get('hot_reload_count', 0)
                
                # Store position for initialization
                self._initial_position = data.get('position')
                
                # Initialize if not already done
                if not self._initialized:
                    if not self.initialize():
                        return False
                
                # Restore node state
                if 'node_data' in data and data['node_data'] and self._node_instance:
                    self._node_instance.load_state(data['node_data'])
                
                self._notify_change("deserialized")
                return True
                
            except Exception as e:
                log_detailed_error(f"Failed to deserialize node wrapper {self.node_id}", e)
                self.state.error_state = f"Deserialization failed: {e}"
                return False
    
    def prepare_for_execution(self, context: Dict[str, Any]) -> None:
        """
        Prepare node for execution in a flow.
        
        Args:
            context: Execution context data
        """
        with self._lock:
            if not self.state.is_valid:
                raise ValueError(f"Cannot execute invalid node {self.node_id}")
                
            self.state.is_executing = True
            self.state.execution_count += 1
            
            self._execute_with_middleware('prepare_for_execution', context)
            self._notify_change("execution_started")
    
    def cleanup_after_execution(self) -> None:
        """Cleanup after execution completes"""
        with self._lock:
            self.state.is_executing = False
            
            self._execute_with_middleware('cleanup_after_execution')
            self._notify_change("execution_ended")
    
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
                
            if self.state.error_state:
                issues.append(f"Error state: {self.state.error_state}")
            
            if not self._initialized:
                issues.append("Wrapper not initialized")
            
            # Additional validation can be added here
            # e.g., pin compatibility, data types, etc.
            
            return issues
    
    def add_change_callback(self, callback: Callable[['NodeWrapper', str], None]) -> None:
        """Add callback for wrapper state changes"""
        with self._lock:
            if callback not in self._change_callbacks:
                self._change_callbacks.append(callback)
    
    def remove_change_callback(self, callback: Callable[['NodeWrapper', str], None]) -> None:
        """Remove change callback"""
        with self._lock:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
    
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
    
    def cleanup(self) -> None:
        """Full cleanup when wrapper is being destroyed"""
        with self._lock:
            # Remove hot reload listener
            if hasattr(self, 'node_factory'):
                try:
                    self.node_factory.remove_hot_reload_listener(self._on_hot_reload)
                except:
                    pass  # May have already been removed
            
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
            self._change_callbacks.clear()
            self._middleware.clear()
            self._node_instance = None
            self.state.is_valid = False
    
    # Private helper methods
    
    def _create_node_instance(self) -> None:
        """Create a new node instance"""
        self._node_instance = self.node_factory.create_instance(
            self.registry_key,
            graph=None,  # Will be set by graph when wrapper is added
            node_id=self.node_id,
            position=self._initial_position
        )
        
        self.state.is_valid = True
        self.state.needs_migration = False
        self.state.error_state = None
    
    def _create_error_node(self) -> None:
        """Create an error node as fallback"""
        error_node_class = self.node_factory.node_registry.get_error_node()
        if error_node_class:
            self._node_instance = error_node_class(
                node_id=self.node_id,
                graph=None
            )
            
            # Set error information
            if hasattr(self._node_instance, 'set_error_info'):
                self._node_instance.set_error_info(
                    original_registry_key=self.registry_key,
                    error_message=self.state.error_state or "Unknown error"
                )
    
    def _setup_hot_reload_monitoring(self) -> None:
        """Setup hot reload monitoring for this wrapper"""
        self.node_factory.add_hot_reload_listener(self._on_hot_reload)
    
    def _on_hot_reload(self, reloaded_registry_key: str, affected_node_ids: List[str]) -> None:
        """Handle hot reload notification from factory"""
        if reloaded_registry_key == self.registry_key:
            with self._lock:
                self.state.needs_migration = True
                self.state.last_hot_reload = time.time()
                self.state.hot_reload_count += 1
                
                self._notify_change("hot_reload_detected")
    
    def _perform_migration(self) -> None:
        """Perform hot reload migration"""
        if not self.state.needs_migration:
            return
            
        print(f"🔄 Migrating node {self.node_id} to new class version")
        
        try:
            # Preserve current state
            old_state = None
            old_position = None
            
            if self._node_instance:
                old_state = self._node_instance.to_dict()
                old_position = (self._node_instance.ui_state.posX, self._node_instance.ui_state.posY)
            
            # Create new instance
            self._create_node_instance()
            
            # Restore state if we had it
            if old_state and self._node_instance:
                try:
                    self._node_instance.load_state(old_state)
                except Exception as e:
                    log_detailed_error(f"Failed to restore state during migration of {self.node_id}", e)
            
            # Restore position
            if old_position and self._node_instance:
                self._node_instance.ui_state.posX = old_position[0]
                self._node_instance.ui_state.posY = old_position[1]
            
            self.state.needs_migration = False
            print(f"✅ Successfully migrated node {self.node_id}")
            
            self._notify_change("migration_completed")
            
        except Exception as e:
            print(f"❌ Failed to migrate node {self.node_id}: {e}")
            self.state.error_state = f"Migration failed: {e}"
            self.state.is_valid = False
            
            # Try to create error node
            try:
                self._create_error_node()
                self._notify_change("migration_failed_error_node_created")
            except Exception as e2:
                log_detailed_error(f"Failed to create error node during failed migration of {self.node_id}", e2)
                self._notify_change("migration_failed_no_fallback")
    
    def _notify_change(self, change_type: str) -> None:
        """Notify callbacks of wrapper state change"""
        for callback in self._change_callbacks[:]:  # Copy to avoid modification during iteration
            try:
                callback(self, change_type)
            except Exception as e:
                log_detailed_error(f"Error in wrapper change callback for {self.node_id}", e)
    
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