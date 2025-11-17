"""
Hot Reload Event System - Unified event class for hot reload notifications

This module provides a unified event class that flows through the entire
hot reload notification chain: Registry → Factory → Wrapper → UINode

The event carries complete context about what changed, making it easy to
filter and route at each layer of the system.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Type, Any, Set, Callable

from .library_identity import LibraryIdentity


class HotReloadEventType(Enum):
    """Types of hot reload events"""
    CLASS_ADDED = 'class_added'
    CLASS_RELOADED = 'class_reloaded'
    CLASS_REMOVED = 'class_removed'
    CLASS_RELOAD_FAILED = 'class_reload_failed'


@dataclass
class HotReloadEvent:
    """
    Unified hot reload event carrying complete reload information.
    
    This event is passed through the entire notification chain:
    Registry → Factory → Wrapper → UINode
    
    Each layer can filter based on its needs using the provided methods.
    
    Example Usage:
        # In Registry:
        event = HotReloadEvent(
            registry_key='example:MyNode',
            event_type=HotReloadEventType.CLASS_RELOADED,
            affected_class=NewNodeClass,
            library_identity=lib_id
        )
        self._notify_customer_callbacks(event)
        
        # In Factory:
        def _on_node_reloaded(self, event: HotReloadEvent):
            if event.is_successful_reload():
                # Forward to listeners
                for listener in self._hot_reload_listeners:
                    listener(event)
        
        # In Wrapper:
        def _on_hot_reload(self, event: HotReloadEvent):
            if event.matches_registry_key(self.registry_key):
                self._perform_migration()
    """
    
    # Core identification
    registry_key: str
    """The haywire registry key (e.g., 'example:MyNode')"""
    
    event_type: HotReloadEventType
    """What kind of reload event occurred"""
    
    affected_class: Optional[Type[Any]]
    """The actual class that was affected (None for REMOVED/FAILED events)"""
    
    library_identity: LibraryIdentity
    """The library where the change occurred"""
    
    # Error information (for failed reloads)
    error_info: Optional[str] = None
    """Error message if reload failed"""
    
    exception: Optional[Exception] = None
    """The exception if reload failed"""
    
    # Module tracking
    module_name: Optional[str] = None
    """The Python module name"""
    
    class_name: Optional[str] = None
    """The Python class name (preserved even if class is None)"""
    
    # Propagation tracking
    reloaded_modules: Set[str] = field(default_factory=set)
    """Track modules already reloaded in this event chain"""
    
    def __post_init__(self):
        """Initialize tracking sets and auto-populate class metadata"""
        # Auto-populate class_name and module_name from class if available
        if self.affected_class is not None:
            if self.class_name is None:
                self.class_name = self.affected_class.__name__
            if self.module_name is None:
                self.module_name = self.affected_class.__module__
    
    # ============================================================================
    # Filtering Methods - Easy routing at each layer
    # ============================================================================
    
    def matches_registry_key(self, registry_key: str) -> bool:
        """Check if this event affects a specific registry key"""
        return self.registry_key == registry_key
    
    def matches_class_name(self, class_name: str) -> bool:
        """Check if this event affects a specific class name"""
        return self.class_name == class_name
    
    def matches_module(self, module_name: str) -> bool:
        """Check if this event affects a specific module"""
        return self.module_name == module_name
    
    def is_successful_reload(self) -> bool:
        """Check if this was a successful reload (not removal or failure)"""
        return self.event_type in (
            HotReloadEventType.CLASS_ADDED,
            HotReloadEventType.CLASS_RELOADED
        ) and self.affected_class is not None
    
    def is_error_event(self) -> bool:
        """Check if this event represents an error"""
        return self.event_type == HotReloadEventType.CLASS_RELOAD_FAILED
    
    def is_removal(self) -> bool:
        """Check if this event represents a class removal"""
        return self.event_type == HotReloadEventType.CLASS_REMOVED
    
    def has_class_available(self) -> bool:
        """Check if the affected class is available"""
        return self.affected_class is not None
    
    def get_class(self) -> Type[Any]:
        """
        Get the affected class, raising error if not available.
        
        Use has_class_available() first to check safely.
        """
        if self.affected_class is None:
            raise ValueError(
                f"Class not available for event type {self.event_type.value} "
                f"on {self.registry_key}"
            )
        return self.affected_class
    
    # ============================================================================
    # Routing Helpers
    # ============================================================================
    
    def should_notify_customers(self) -> bool:
        """
        Check if this event should be passed to customer callbacks.
        
        Typically all events are passed down, but layers can filter.
        """
        return True  # By default, notify all
    
    def create_derived_event(self, **overrides) -> 'HotReloadEvent':
        """
        Create a new event with some fields overridden.
        
        Useful when propagating events with additional context.
        """
        data = {
            'registry_key': self.registry_key,
            'event_type': self.event_type,
            'affected_class': self.affected_class,
            'library_identity': self.library_identity,
            'error_info': self.error_info,
            'exception': self.exception,
            'module_name': self.module_name,
            'class_name': self.class_name,
            'reloaded_modules': self.reloaded_modules.copy()
        }
        data.update(overrides)
        return HotReloadEvent(**data)
    
    def __str__(self) -> str:
        """Human-readable representation"""
        status = self.event_type.value
        if self.error_info:
            status += f" (error: {self.error_info})"
        return f"HotReloadEvent({self.registry_key}, {status})"
    
    def __repr__(self) -> str:
        """Detailed representation for debugging"""
        return (
            f"HotReloadEvent("
            f"registry_key='{self.registry_key}', "
            f"event_type={self.event_type.value}, "
            f"class_name='{self.class_name}', "
            f"library='{self.library_identity.label}', "
            f"has_class={self.affected_class is not None}"
            f")"
        )


# Type alias for the new callback signature
HotReloadCallback = Callable[[HotReloadEvent], None]
