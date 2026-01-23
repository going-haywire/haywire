"""
Base class for all event nodes.

Event nodes are entry points for flow execution and must declare
what event they listen for.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from haywire.core.node.base import BaseNode
from haywire.core.execution.event_source import EventSource

if TYPE_CHECKING:
    from haywire.core.node.node_wrapper import NodeWrapper


class EventNode(BaseNode):
    """
    Base class for all event nodes.
    
    Event nodes are special control nodes that:
    - Start flow execution (entry points)
    - Have no control inlets (nothing triggers them except events)
    - Declare what event they listen for via EVENT_SOURCE
    - Can have data outlets to pass event payload
    
    Subclasses MUST either:
    1. Override EVENT_SOURCE at class level (for static events)
    2. Set self.event_subscription in initialize() (for dynamic events)
    
    Example (static):
        class BeginPlayNode(EventNode):
            EVENT_SOURCE = SystemEvent(SystemEventType.BEGIN_PLAY)
            
            def initialize(self):
                super().initialize()
                self.add(EXEC.as_outlet('exec'))
                self.add(FLOAT.as_outlet('timestamp'))
    
    Example (callback listener):
        class DataReadyNode(EventNode):
            EVENT_SOURCE = CallbackEvent(event_name='data_ready')
            
            def initialize(self):
                super().initialize()
                
                # Declare interest in callback
                self.add(CALLBACK.as_outlet(
                    'listen_callback',
                    event_filter='data_ready'
                ))
                
                # Control flow when triggered
                self.add(EXEC.as_outlet('triggered'))
                
                # Pass event data
                self.add(ANY.as_outlet('payload'))
            
            def worker(self, context):
                # Extract payload from trigger
                payload = context['trigger'].payload
                self.out('payload', payload)
                return {'next_outlet': 'triggered'}
    """
    
    # Class-level declaration (can be overridden)
    EVENT_SOURCE: EventSource = None
    
    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        super().__init__(node_id, wrapper)
        
        # Initialize subscription from class-level EVENT_SOURCE
        if self.__class__.EVENT_SOURCE is not None:
            self.event_subscription = self.__class__.EVENT_SOURCE

        self.behavior.is_event_node = True
