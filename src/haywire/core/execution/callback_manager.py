"""
Callback Manager - Manages inter-flow communication via callbacks.

The CallbackManager enables control nodes to emit callbacks that
trigger event nodes in other flows within the same graph.
"""
from __future__ import annotations
from typing import Dict, List, Optional, TYPE_CHECKING
import time
import logging

if TYPE_CHECKING:
    from haywire.core.execution.flow import Flow

from haywire.core.execution.event_source import Trigger

logger = logging.getLogger(__name__)

class CallbackManager:
    """
    Manages callback-based inter-flow communication.
    
    Responsibilities:
    - Register flows that listen for callbacks
    - Dispatch callbacks to listening flows
    - Track callback statistics
    """
    
    def __init__(self):
        """Initialize callback manager"""
        self.callbacks: Dict[str, List[Flow]] = {}
        """Maps callback event names to listening flows"""
        
        self.callback_stats: Dict[str, int] = {}
        """Tracks number of times each callback was emitted"""
        
        logger.debug("CallbackManager initialized")
    
    def register_callback_listener(
        self,
        event_name: str,
        flow: Flow
    ):
        """
        Register a flow as listener for a callback event.
        
        Args:
            event_name: Name of callback event to listen for
            flow: Flow that should be triggered
        """
        if event_name not in self.callbacks:
            self.callbacks[event_name] = []
        
        if flow not in self.callbacks[event_name]:
            self.callbacks[event_name].append(flow)
            logger.debug(
                f"Flow {flow.flow_id} registered for callback '{event_name}'"
            )
    
    def unregister_callback_listener(
        self,
        event_name: str,
        flow: Flow
    ):
        """
        Unregister a flow from callback event.
        
        Args:
            event_name: Callback event name
            flow: Flow to unregister
        """
        if event_name in self.callbacks:
            if flow in self.callbacks[event_name]:
                self.callbacks[event_name].remove(flow)
                logger.debug(
                    f"Flow {flow.flow_id} unregistered from callback '{event_name}'"
                )
    
    def emit_callback(
        self,
        event_name: str,
        payload: Optional[Dict] = None
    ):
        """
        Emit a callback event to trigger listening flows.
        
        This is called by control nodes during execution to trigger
        event nodes in other flows.
        
        Args:
            event_name: Name of callback event
            payload: Optional data to pass to triggered flows
        """
        # Track statistics
        if event_name not in self.callback_stats:
            self.callback_stats[event_name] = 0
        self.callback_stats[event_name] += 1
        
        # Get listening flows
        flows = self.callbacks.get(event_name, [])
        
        if not flows:
            logger.debug(
                f"Callback '{event_name}' emitted but no flows listening"
            )
            return
        
        logger.debug(
            f"Emitting callback '{event_name}' to {len(flows)} flows"
        )
        
        # Create trigger
        trigger = Trigger(
            source_key=f"callback:{event_name}",
            payload=payload,
            timestamp=time.time()
        )
        
        # Enqueue trigger in each flow's scheduler
        for flow in flows:
            if flow.scheduler:
                flow.scheduler.enqueue_trigger(trigger)
            else:
                logger.warning(
                    f"Flow {flow.flow_id} has no scheduler, "
                    f"cannot trigger callback"
                )
    
    def get_listeners(self, event_name: str) -> List[Flow]:
        """
        Get all flows listening for a callback event.
        
        Args:
            event_name: Callback event name
            
        Returns:
            List of flows listening for this callback
        """
        return self.callbacks.get(event_name, []).copy()
    
    def clear_callbacks(self):
        """Clear all callback registrations"""
        self.callbacks.clear()
        logger.debug("All callback registrations cleared")
    
    def get_statistics(self) -> Dict:
        """
        Get callback statistics.
        
        Returns:
            Dictionary with callback stats
        """
        return {
            'total_callbacks': len(self.callbacks),
            'callbacks': [
                {
                    'event_name': event_name,
                    'listener_count': len(flows),
                    'emit_count': self.callback_stats.get(event_name, 0)
                }
                for event_name, flows in self.callbacks.items()
            ]
        }
