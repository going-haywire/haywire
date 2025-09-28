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
    
    def __init__(self, node_id, graph, registry_key):
        super().__init__(node_id, graph, registry_key)
        
        # Configure identity
        self.identity.label = 'Test Node One'
        self.identity.search_tags = ['constant', 'value', 'output', 'basic']
        self.identity.menu = 'core/basic'
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False

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
                id='float_select',  # id as first positional parameter
                label='Select',
                flow_type=FlowType.DATA,
                is_pooled=False,
                data=SingleField('string_val', DataType.STRING, DataCategory.SCALAR, "Option 1", False),
                widget='haywire.core:select.widget',
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
                widget='haywire.core:number.widget',
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
                'execute',  # element_id as first positional parameter
                label='Execute',
                flow_type=FlowType.CTRL
            )
        )
        _ = self.add_outlet(Outlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                flow_type=FlowType.DATA,
                data=SingleField('missing_val', DataType.INT, DataCategory.SCALAR, 42, False),
            )
        )

    
    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        return None

