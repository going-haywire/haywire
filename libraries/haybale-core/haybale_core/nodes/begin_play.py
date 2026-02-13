from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType

from ..types.specs import EXEC, FLOAT

@node(
    registry_id='begin_play',
    label='Begin Play',
    description='Triggered once when execution starts',
    menu='event/runtime',
    search_tags=['start', 'init', 'begin', 'event'],
    node_type=NodeType.EVENT,
)
class BeginPlayNode(BaseNode):
    """
    Triggered once when execution starts.
    
    Outputs:
        exec: Control flow
        timestamp: Time when execution began
    """
        
    def init(self):
        # Control output
        self.add(EXEC.as_outlet('exec', label='Execute'))
        
        # Data output
        self.add(FLOAT.as_outlet('timestamp', label='Start Time'))
    
    def post_init(self):
        self.event_subscription = SystemEvent(SystemEventType.BEGIN_PLAY)
    
    def worker(self, context: ExecutionContext) -> str | None:
        import time
        
        self.out('timestamp', time.time())
        # Continue execution
        return 'exec'