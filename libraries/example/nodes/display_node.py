
from haywire.core.node.node import BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, FlowType
from haywire.core.data.fields import SingleField

class DisplayNode(BaseNode):
    """Node that displays input values"""
    
    # Required metadata for node discovery
    node_name = 'Display'
    node_label = 'Display'
    node_description = 'Displays input values for debugging'
    node_search_tags = ['display', 'debug', 'output', 'basic']
    node_menu = 'example/basic'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        self.is_data_node = True
        self.is_control_node = False
        self.renderer = 'example.renderer'

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
    

    def execute(self, input_value=None):
        """Execute the node - display the input value"""
        if input_value is not None:
            print(f"Display Node [{self.node_id}]: {input_value}")
        return
