from haywire.core.node.base_node import node
from haywire.core.node.base_node import BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, FlowType
from haywire.core.data.fields import SingleField

@node(
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
        self.ui_config.node_renderer = 'example:example.node.rendere'

        # Math node
        _ = self.add_inlet(
            Inlet(
                id='a', 
                label='Value A', 
                flow_type=FlowType.DATA,
                data=SingleField(DataType.FLOAT, 'single', 10.0), 
                widget='core.number')
        )
        _ = self.add_inlet(
            Inlet(
                id='b', 
                label='Value B', 
                flow_type=FlowType.DATA,
                data=SingleField(DataType.FLOAT, 'single', 5.0), 
                widget='core.number')
            )
        _ = self.add_outlet(
            Outlet(
                id='result', 
                flow_type=FlowType.DATA, 
                label='Result', 
                data=SingleField(DataType.FLOAT, 'single', None)),
        )
        _ = self.add_inlet (
            Inlet(
                id='operation', 
                label='Operation', 
                flow_type=FlowType.DATA,
                data=SingleField(DataType.STRING, 'single', 'add'), 
                widget='core.select')
        )   
    

    def worker(self, context: dict) -> dict | None:
        """Execute the node - display the input value"""
        input_value = context.get('input_value')
        if input_value is not None:
            print(f"Display Node [{self.node_id}]: {input_value}")
        return None
