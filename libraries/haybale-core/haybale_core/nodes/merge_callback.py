from haywire.core.execution.event_source import CallbackEvent, SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType

@node(
    label='Merge Callback',
    description='Listens for a specified number of callbacks from other flows',
    menu='event/callback',
    search_tags=['callback', 'listen', 'event', 'custom'],
    node_type=NodeType.EVENT,
)
class MergeCallbackNode(BaseNode):
    """
    Listens for a specified number of callbacks from other flows.
    
    Config:
        callback_name: Name of the callback to listen for
    
    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """

    def init(self):
        # Config for callback name
        from ..types.specs import  INT
        from haybale_core.widgets.basic_widgets import  NumberWidget

        self.add(INT.as_config(
            'custom_callback_count',
            default=1,
            label='Callback Count',
            widget=NumberWidget.config(properties={'min': 1, 'step': 1}),
            on_change='hb_rebuild'
        ))     
        
        self.hb_reconfigure(number_of_callbacks=1)

    def on_init(self):
        # Set initial subscription
        self.cache.store = {}
        self.event_subscription = CallbackEvent(event_name=self.node_id)

    def hb_rebuild(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        number_of_callbacks = self.value('custom_callback_count')
        if number_of_callbacks and number_of_callbacks > 0:
            self.hb_reconfigure(number_of_callbacks=number_of_callbacks)
            self.wrapper.redraw()

    def hb_reconfigure(self, number_of_callbacks: int = 1):
        """Reconfigure the node based on current settings."""
        from ..types.specs import GROUP, EXEC, CALLBACK, STRING, FLOAT, INT, BOOL
        from haybale_core.widgets.basic_widgets import SwitchWidget, TextWidget, NumberWidget, SelectWidget

        self.cache.store = {}

        self.push(exclude=['custom_callback_count'])

        for i in range(number_of_callbacks):
            # Declare callback interest
            self.add(CALLBACK.as_outlet(
                f'listen_callback_{i+1}',
                label='Listener '+str(i+1),
                default=self.node_id+str(i+1),
            ))

        if number_of_callbacks > 0:
            # Control output
            self.add(EXEC.as_outlet('triggered', label='Triggered'))

        for i in range(number_of_callbacks):
            # Data output
            self.add(FLOAT.as_outlet(f'payload_{i+1}', label='Payload '+str(i+1)))
    
        self.pop()

    def worker(self, context: ExecutionContext) -> str | None:
        # Extract payload from trigger
        self.cache.store[context.trigger.source_key] = context.trigger.payload

        return 'triggered'