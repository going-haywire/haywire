from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
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
        from ..types.specs import GROUP, EXEC, CALLBACK, STRING, FLOAT
        from haybale_core.widgets.basic_widgets import SwitchWidget, TextWidget
        
        # Control input
        self.add(EXEC.as_inlet('execute', label='Execute'))

        # Config for callback name
        with self.group(GROUP.as_config(
                'mode_switch',
                default=False,
                label='Use Custom Name',
                on_change='redraw'
            )):

            # Config for callback name
            self.add(STRING.as_config(
                'custom_callback_name',
                default='my_callback',
                label='Callback Name',
                widget=TextWidget.config()
            ))
    
        self.add(FLOAT.as_inlet(
            'payload',
            use_mode='optional',
            label='Payload'
        ))

        self.add(CALLBACK.as_inlet(
            'edge_callback',
            label='Trigger',
            default=None,
            event_filter='*',
            on_change='printout'
        ))

        # Control output
        self.add(EXEC.as_outlet('exec', label='Then'))

    def redraw(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        self.wrapper.redraw()

    def printout(self, port, new_value):
        print(f"Edge Callback changed to: {new_value}")

    def worker(self, 
               context: ExecutionContext, 
               mode_switch: bool, 
               edge_callback: str, 
               custom_callback_name: str, 
               payload: float) -> dict | None:
        
        # Emit callback (VM provides this in context)
        if mode_switch:
            context.emit_callback( 
                event_name=custom_callback_name,
                payload=payload
            )
        else: 
            context.emit_callback( 
                event_name=edge_callback,
                payload=payload
            )
        
        return 'exec'