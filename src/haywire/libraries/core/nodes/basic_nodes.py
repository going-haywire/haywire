"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.node import BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, DataCategory, FlowType
from haywire.core.data.fields import SingleField

class TestNodeOne(BaseNode):
    """Node that outputs a constant value"""
    
    # Required metadata for node discovery
    node_name = 'TestNodeOne'
    node_label = 'Test Node One'
    node_search_tags = ['constant', 'value', 'output', 'basic']
    node_menu = 'core/basic'
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # This would normally be set up with proper inlet/outlet definitions
        # For now, just demonstrate the structure
        self.is_data_node = True
        self.is_control_node = False

        # Add configs with different widget types
        _ = self.add_inlet(Inlet(
                id='execute',  # id as first positional parameter
                label='Execute',
                flow_type=FlowType.CTRL,
                is_pooled=False
            )
        )
        _ = self.add_inlet(Inlet(
                id='temperature',  # id as first positional parameter
                label='Temperature',
                flow_type=FlowType.NONE,
                data=SingleField('temp_val', DataType.FLOAT, DataCategory.SCALAR, 25.0, False),
                widget='example:temperature.widget',
                ui={'properties': {'unit': 'celsius'}}
            )
        )    
        # Add inlets with different widget types
        _ = self.add_inlet(Inlet(
            id='float_slider',  # id as first positional parameter
            label='Float',
            flow_type=FlowType.DATA,
            is_pooled=False,
            data=SingleField('float_val', DataType.STRING, DataCategory.SCALAR, "Option 1", False),
            widget='core.select',
            ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}}
            )
        )
        _ = self.add_inlet(Inlet(
                'float_slider',  # element_id as first positional parameter
                label='Float Slider',
                flow_type=FlowType.DATA,
                data=SingleField('float_val', DataType.FLOAT, DataCategory.SCALAR, 50.0, False),
                widget='haywire.core:slider.widget',
                ui={'properties': {'min': 0, 'max': 100, 'step': 1}}
            )
        )
        _ = self.add_inlet(Inlet(
                'bool_switch',  # element_id as first positional parameter
                label='Boolean Switch',
                flow_type=FlowType.DATA,
                data=SingleField('bool_val', DataType.BOOL, DataCategory.SCALAR, True, False),
                widget='haywire.core:switch.widget',
                ui={'properties': {'text': 'Enable Feature'}}
            )
        )
        _ = self.add_inlet(Inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                flow_type=FlowType.DATA,
                data=SingleField('str_val', DataType.STRING, DataCategory.SCALAR, 'Hello', False),
                widget='haywire.core:text.input.widget',
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
        _ = self.add_inlet(Inlet(
                'callback',  # element_id as first positional parameter
                label='Callback Widget',
                flow_type=FlowType.CALLBACK,
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

