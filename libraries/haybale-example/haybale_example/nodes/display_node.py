from haywire.core.node.base import node
from haywire.core.node.base import BaseNode
from haywire.libraries.core.types.specs import FLOAT, STRING

@node(
    label='Display',
    description='Displays input values for debugging',
    search_tags=['display', 'debug', 'output', 'basic'],
    menu='example/basic'
)
class DisplayNode(BaseNode):
    """Node that displays input values"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False
        
        # Configure UI
        self.ui_config.node_renderer = 'example:renderer:example.node.renderer'

        # Using the new .as_inlet() API
        self.add(
            FLOAT.as_inlet('a', label='Value A', default=10.0, widget='core:widget:number.widget')
        )
        self.add(
            FLOAT.as_inlet('b', label='Value B', default=3.4, widget='core:widget:number.widget')
        )
        self.add(
            STRING.as_inlet(
                'operation', label='Operation', default='add', widget='core:widget:text.widget'
            )
        )   
        self.add(FLOAT.as_outlet('result', label='Result'))
    
    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        input_value = context.get('input_value')
        if input_value is not None:
            print(f"Display Node [{self.node_id}]: {input_value}")
        return None
