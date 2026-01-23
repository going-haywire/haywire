from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.node.decorator import node

from .event_node import EventNode
from ..types.specs import EXEC, FLOAT

@node(
    registry_id='begin_play',
    label='Begin Play',
    description='Triggered once when execution starts',
    menu='events/system',
    search_tags=['start', 'init', 'begin', 'event'],
)
class BeginPlayNode(EventNode):
    """
    Triggered once when execution starts.
    
    Outputs:
        exec: Control flow
        timestamp: Time when execution began
    """
    
    EVENT_SOURCE = SystemEvent(SystemEventType.BEGIN_PLAY)
    
    def initialize(self):
        super().initialize()
        
        # Control output
        self.add(EXEC.as_outlet('exec', label='Execute'))
        
        # Data output
        self.add(FLOAT.as_outlet('timestamp', label='Start Time'))
    
    def worker(self, context):
        import time
        
        # Set timestamp
        self.out('timestamp', time.time())
        
        # Continue execution
        return {'next_outlet': 'exec'}