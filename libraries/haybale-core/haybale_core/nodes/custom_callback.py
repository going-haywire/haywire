from haywire.core.execution.event_source import CallbackEvent, SystemEvent, SystemEventType
from haywire.core.node.decorator import node
from haywire.core.node.node_wrapper import NodeWrapper

from .event_node import EventNode
from ..types.specs import EXEC, CALLBACK, STRING, FLOAT


@node(
    registry_id='custom_callback',
    label='Custom Callback',
    description='Listens for custom callbacks from other flows',
    menu='events/callback',
    search_tags=['callback', 'listen', 'event', 'custom'],
)
class CustomCallbackNode(EventNode):
    """
    Listens for custom callbacks from other flows.
    
    Config:
        callback_name: Name of the callback to listen for
    
    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """
    
    EVENT_SOURCE = None  # Dynamic, set in initialize()

    def __init__(self, node_id: str, wrapper: 'NodeWrapper'):
        super().__init__(node_id, wrapper)

        self.behavior.is_event_node = True
    
    def initialize(self):
        super().initialize()
        
        # Config for callback name
        self.add(STRING.as_config(
            'callback_name',
            default='my_callback',
            label='Callback Name',
            on_change='_update_subscription'
        ))
        
        # Set initial subscription
        callback_name = self.value('callback_name')
        self.event_subscription = CallbackEvent(event_name=callback_name)
        
        # Declare callback interest
        self.add(CALLBACK.as_outlet(
            'listen_callback',
            event_filter=callback_name,
            label='Listen'
        ))
        
        # Control output
        self.add(EXEC.as_outlet('triggered', label='Triggered'))
        
        # Data output
        self.add(FLOAT.as_outlet('payload', label='Payload'))
    
    def _update_subscription(self, port, new_value):
        """Update event subscription when callback name changes"""
        self.event_subscription = CallbackEvent(event_name=new_value)
        
        # Update callback port event filter
        callback_port = self.ports['listen_callback']
        callback_port.event_filter = new_value
        
        # Trigger flow reassembly via wrapper
        if self.wrapper:
            self.wrapper.redraw()
    
    def worker(self, context):
        # Extract payload from trigger
        payload = context['trigger'].payload
        
        self.out('payload', payload)
        
        return {'next_outlet': 'triggered'}