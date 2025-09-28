
from haywire.core.node.node import BaseNode, node_identity
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, FlowType
from haywire.core.data.fields import SingleField

@node_identity(
    label='Display',
    description='Displays input values for debugging',
    search_tags=['display', 'debug', 'output', 'basic'],
    menu='example/basic'
)
class DisplayNode(BaseNode):
    """Node that displays input values"""
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False
        
        # Configure UI
        self.ui_config.node_renderer = 'example.renderer'

        # Math node
        _ = self.add_inlet(
            Inlet(
                id='a', 
                label='Value A', 
                flow_type=FlowType.DATA,
                data=SingleField('a', DataType.FLOAT, 'scalar', 10.0, False), 
                widget='core.number')
        )
        _ = self.add_inlet(
            Inlet(
                id='b', 
                label='Value B', 
                flow_type=FlowType.DATA,
                data=SingleField('b', DataType.FLOAT, 'scalar', 5.0, False), 
                widget='core.number')
            )
        _ = self.add_outlet(
            Outlet(
                id='result', 
                flow_type=FlowType.DATA, 
                label='Result', 
                data=SingleField('result', DataType.FLOAT, 'scalar', None, False))
        )
        _ = self.add_inlet (
            Inlet(
                id='operation', 
                label='Operation', 
                flow_type=FlowType.DATA,
                data=SingleField('operation', DataType.STRING, 'scalar', 'add', False), 
                widget='core.select')
        )   
    

    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        input_value = context.get('input_value')
        if input_value is not None:
            print(f"Display Node [{self.node_id}]: {input_value}")
        return None
