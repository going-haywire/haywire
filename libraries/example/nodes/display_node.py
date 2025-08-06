
from haywire.core.node.node import HaywireNode
from haywire.core.node.elements import Config, Inlet, Outlet
from haywire.core.data.enums import CouplingType, DataType, FlowType
from haywire.core.data.fields import SingleField

class DisplayNode(HaywireNode):
    """Node that displays input values"""
    
    # Required metadata for node discovery
    node_display_name = 'Display'
    node_description = 'Displays input values for debugging'
    node_name = 'Display'
    node_package = 'org.example.basic'
    node_library_name = 'Example Library'
    node_library_url = 'https://example.io/docs/core-nodes'
    node_search_tags = ['display', 'debug', 'output', 'basic']
    node_menu = 'example/basic'
    node_version = '1.0.0'
    node_author = 'Exampler System'
    node_author_url = 'https://example.io'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        self.is_data_node = True
        self.is_control_node = False
        

        # Math node
        _ = self.add_inlet(
            Inlet(
                element_id='a', 
                label='Value A', 
                flow_type=FlowType.DATA,
                coupling_type=CouplingType.ONE, 
                data=SingleField('a', DataType.FLOAT, 'scalar', 10.0, False), 
                widget='number')
        )
        _ = self.add_inlet(
            Inlet(
                element_id='b', 
                label='Value B', 
                flow_type=FlowType.DATA,
                coupling_type=CouplingType.ONE, 
                data=SingleField('b', DataType.FLOAT, 'scalar', 5.0, False), 
                widget='number')
            )
        _ = self.add_outlet(
            Outlet(
                element_id='result', 
                flow_type=FlowType.DATA, 
                label='Result', 
                data=SingleField('result', DataType.FLOAT, 'scalar', None, False))
        )
        _ = self.add_config(
            Config(
                element_id='operation', 
                label='Operation', 
                callback=None,
                data=SingleField('operation', DataType.STRING, 'scalar', 'add', False), 
                widget='select')
        )   
    

    def execute(self, input_value=None):
        """Execute the node - display the input value"""
        if input_value is not None:
            self.display_value = input_value
            print(f"Display Node [{self.node_id}]: {input_value}")
        return self.display_value
