from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode

@node(
    registry_id='emit_callback',
    label='Emit Callback',
    description='Emits a callback to trigger event nodes in other flows',
    menu='control/callback',
    search_tags=['callback', 'emit', 'trigger', 'event'],
)
class EmitCallbackNode(BaseNode):
    """
    Emits a callback to trigger event nodes in other flows.
    
    Inputs:
        execute: Control flow in
        callback_name: Name of callback to emit
        payload: Data to send with callback
    
    Outputs:
        exec: Control flow out
    """
    
    def initialize(self):
        from ..types.specs import EXEC, STRING, FLOAT, CALLBACK
        
        # Control input
        self.add(EXEC.as_inlet('execute', label='Execute'))

        self.add(CALLBACK.as_inlet(
            'callback',
            label='Trigger',
            event_filter='*'  # Can trigger any callback event
        ))
    

        # Data inputs
        self.add(STRING.as_inlet(
            'callback_name',
            default='my_callback',
            label='Callback Name'
        ))
        self.add(FLOAT.as_inlet(
            'payload',
            use_mode='optional',
            label='Payload'
        ))
        
        # Control output
        self.add(EXEC.as_outlet('exec', label='Then'))
    
    def worker(self, context):
        callback_name = self.value('callback_name')
        payload = self.value('payload')
        
        # Emit callback (VM provides this in context)
        context['emit_callback'](
            event_name=callback_name,
            payload=payload
        )
        
        return {'next_outlet': 'exec'}