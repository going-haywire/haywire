"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.node import HaywireNode
from haywire.core.node.elements import Config, Inlet, Outlet
from haywire.core.data.enums import CouplingType, DataType, DataCategory, FlowType
from haywire.core.data.fields import SingleField

class TestNodeOne(HaywireNode):
    """Node that outputs a constant value"""
    
    # Required metadata for node discovery
    node_display_name = 'TestNode One'
    node_description = 'Outputs a constant value'
    node_name = 'TestNodeOne'
    node_package = 'org.haywire.core.basic'
    node_library_name = 'Haywire Core'
    node_library_url = 'https://haywire.io/docs/core-nodes'
    node_search_tags = ['constant', 'value', 'output', 'basic']
    node_menu = 'core/basic'
    node_version = '1.0.0'
    node_author = 'Haywire System'
    node_author_url = 'https://haywire.io'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        # For now, just demonstrate the structure
        self.is_data_node = True
        self.is_control_node = False
        
        # Add configs with different widget types
        _ = self.add_config(Config(
            element_id='float_slider',  # element_id as first positional parameter
            label='Float Slider',
            data=SingleField('float_val', DataType.STRING, DataCategory.SCALAR, "Option 1", False),
            widget='select',
            ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}}
            )
        )
        _ = self.add_config(
            Config(
                element_id='temperature',  # element_id as first positional parameter
                label='Temperature',
                data=SingleField('temp_val', DataType.FLOAT, DataCategory.SCALAR, 25.0, False),
                widget='example.temperature',
                ui={'properties': {'unit': 'celsius'}}
            )
        )    
        # Add configs with different widget types
        _ = self.add_inlet(Inlet(
                'float_slider',  # element_id as first positional parameter
                label='Float Slider',
                flow_type=FlowType.DATA,
                data=SingleField('float_val', DataType.FLOAT, DataCategory.SCALAR, 50.0, False),
                widget='slider',
                ui={'properties': {'min': 0, 'max': 100, 'step': 1}}
            )
        )
        _ = self.add_inlet(Inlet(
                'temperature',  # element_id as first positional parameter
                label='Temperature',
                flow_type=FlowType.DATA,
                data=SingleField('temp_val', DataType.FLOAT, DataCategory.SCALAR, 25.0, False),
                widget='example.temperature',
                ui={'properties': {'unit': 'celsius'}}
            )
        )
        _ = self.add_inlet(Inlet(
                'bool_switch',  # element_id as first positional parameter
                label='Boolean Switch',
                flow_type=FlowType.DATA,
                data=SingleField('bool_val', DataType.BOOL, DataCategory.SCALAR, True, False),
                widget='switch',
                ui={'properties': {'text': 'Enable Feature'}}
            )
        )
        _ = self.add_inlet(Inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                flow_type=FlowType.DATA,
                data=SingleField('str_val', DataType.STRING, DataCategory.SCALAR, 'Hello', False),
                widget='input',
                ui={'properties': {'placeholder': 'Enter text...'}}
            )   
        )
        _ = self.add_inlet(Inlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                flow_type=FlowType.DATA,
                data=SingleField('missing_val', DataType.INT, DataCategory.SCALAR, 42, False),
                widget='nonexistent_widget_type',
                ui={'properties': {}}
            )
        )

        _ = self.add_outlet(Outlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                flow_type=FlowType.DATA,
                data=SingleField('missing_val', DataType.INT, DataCategory.SCALAR, 42, False),
                widget='nonexistent_widget_type',
                ui={'properties': {}}
            )
        )

    
    def execute(self):
        """Execute the node - return the constant value"""
        return None

