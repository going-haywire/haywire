from haywire.core.execution.event_source import CallbackEvent, SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.node_wrapper import NodeWrapper

from .event_node import EventNode


@node(
    label='Merge Callback',
    description='Listens for a specified number of callbacks from other flows',
    menu='events/callback',
    search_tags=['callback', 'listen', 'event', 'custom'],
)
class MergeCallbackNode(EventNode):
    """
    Listens for a specified number of callbacks from other flows.
    
    Config:
        callback_name: Name of the callback to listen for
    
    Outputs:
        triggered: Control flow when callback received
        payload: Data from callback
    """
        
    def initialize(self):
        pass

    def setup(self):
        # Set initial subscription
        self.event_subscription = CallbackEvent(event_name=self.node_id)
        self.store: dict[str, float] = {}
        self.reconfigure(number_of_callbacks=1)

    def rebuild(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        number_of_callbacks = self.value('custom_callback_count')
        if number_of_callbacks and number_of_callbacks > 0:
            number_of_callbacks = int(number_of_callbacks)
            self.reconfigure(number_of_callbacks=number_of_callbacks)
            self.wrapper.redraw()

    def reconfigure(self, number_of_callbacks: int = 1):
        """Reconfigure the node based on current settings."""
        from ..types.specs import GROUP, EXEC, CALLBACK, STRING, FLOAT, INT, BOOL
        from haybale_core.widgets.basic_widgets import SwitchWidget, TextWidget, NumberWidget, SelectWidget

        self.store = {}

        self.push()

        # Config for callback name
        self.add(INT.as_config(
            'custom_callback_count',
            default=number_of_callbacks,
            label='Callback Count',
            widget=NumberWidget.config(),
            on_change='rebuild'
        ))        

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
        self.store[context.trigger.source_key] = context.trigger.payload

        return 'triggered'