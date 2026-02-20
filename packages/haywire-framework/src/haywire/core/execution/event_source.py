"""
Event source type system for Haywire event nodes.

Defines the types of events that can trigger flow execution.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class SystemEventType(Enum):
    """Predefined system lifecycle events"""
    BEGIN_PLAY = "begin_play"
    TICK = "tick"
    SHUTDOWN = "shutdown"
    PAUSE = "pause"
    RESUME = "resume"


@dataclass(frozen=True)
class EventSource:
    """
    Base class for event sources.
    
    All event sources are immutable (frozen) to ensure they can be used
    as dictionary keys and compared reliably.
    """
    
    def get_subscription_key(self) -> str:
        """
        Get unique key for event subscription registration.
        
        Returns:
            String key that uniquely identifies this event source
        """
        raise NotImplementedError("Subclasses must implement get_subscription_key()")
    
    def matches(self, trigger_key: str) -> bool:
        """
        Check if this event source matches a trigger key.
        
        Args:
            trigger_key: Key from incoming trigger
            
        Returns:
            True if this event source should respond to the trigger
        """
        return self.get_subscription_key() == trigger_key


@dataclass(frozen=True)
class SystemEvent(EventSource):
    """
    Predefined system lifecycle events.
    
    These are standard events provided by the Haywire runtime:
    - BEGIN_PLAY: Fired once when execution starts
    - TICK: Fired periodically (frame updates)
    - SHUTDOWN: Fired when system is shutting down
    - PAUSE/RESUME: Fired when execution is paused/resumed
    """
    type: SystemEventType
    
    def get_subscription_key(self) -> str:
        return f"system:{self.type.value}"
    
    def __str__(self) -> str:
        return f"SystemEvent({self.type.value})"


@dataclass(frozen=True)
class ExternalEvent(EventSource):
    """
    Events from external systems (input, network, etc).
    
    These events come from outside Haywire and are forwarded by
    the host application:
    - Input events (keyboard, mouse, gamepad)
    - Network events (messages, connections)
    - File system events
    - Custom application events
    
    Args:
        category: Event category (e.g., 'input', 'network')
        name: Specific event name (e.g., 'key_pressed:Space')
    """
    category: str
    name: str
    
    def get_subscription_key(self) -> str:
        return f"external:{self.category}:{self.name}"
    
    def __str__(self) -> str:
        return f"ExternalEvent({self.category}:{self.name})"


@dataclass(frozen=True)
class CallbackEvent(EventSource):
    """
    Events from other flows via callback mechanism.
    
    These enable inter-flow communication within the same graph.
    A control node can emit a callback that triggers event nodes
    in other flows.
    
    Args:
        event_name: Name of the callback event
    """
    event_name: str
    
    def get_subscription_key(self) -> str:
        return f"callback:{self.event_name}"
    
    def __str__(self) -> str:
        return f"CallbackEvent({self.event_name})"


@dataclass
class Trigger:
    """
    Runtime trigger that activates a flow.
    
    Created when an event occurs and contains all data needed
    to execute the flow.
    
    Args:
        source_key: Subscription key that identifies event source
        payload: Optional data associated with the event
        timestamp: When the trigger was created
    """
    source_key: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0
    
    def matches_subscription(self, event_source: EventSource) -> bool:
        """Check if this trigger matches an event source subscription"""
        return event_source.matches(self.source_key)