from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node

from .event_node import EventNode
from ..types.specs import EXEC, FLOAT


@node(
    registry_id='tick',
    label='Tick',
    description='Triggered periodically (every frame/interval)',
    menu='events/system',
    search_tags=['frame', 'update', 'loop', 'event'],
)
class TickNode(EventNode):
    """
    Triggered periodically (every frame/interval).
    
    Config:
        interval: Target time between ticks (seconds)
    
    Outputs:
        exec: Control flow
        delta_time: Time since last tick
    """
    
    EVENT_SOURCE = SystemEvent(SystemEventType.TICK)
    
    def initialize(self):
        super().initialize()
        
        # Config
        self.add(FLOAT.as_config(
            'interval',
            default=0.016,  # ~60fps
            label='Interval (s)'
        ))
        
        # Control output
        self.add(EXEC.as_outlet('exec', label='Execute'))
        
        # Data output
        self.add(FLOAT.as_outlet('delta_time', label='Delta Time'))
    
    def worker(self, context: ExecutionContext):
        # Extract delta time from trigger
        delta = context.trigger.payload.get('delta_time', 0.016)
                
        return 'exec', (('delta_time', delta),)