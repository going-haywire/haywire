"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.base_node import node
from haywire.core.node.base_node import BaseNode
from haywire.core.node.ports import PortInlet, PortOutlet
from haywire.core.data.enums import DataType, DataContainerType, FlowType
from haywire.core.data.fields import SingleField

@node(
    label='Test Node One',
    search_tags=['constant', 'value', 'output', 'basic'],
    menu='core/basic'
)
class TestNodeOne(BaseNode):
    """Node that outputs a constant value"""
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False

        # Add configs with different widget types
        _ = self.add_inlet(PortInlet(
                id='execute',  # id as first positional parameter
                label='Execute',
                flow_type=FlowType.CTRL,
                is_pooled=False
            )
        )
        _ = self.add_inlet(PortInlet(
                id='temperature',  # id as first positional parameter
                label='Temperature',
                flow_type=FlowType.NONE,
                data=SingleField(DataType.FLOAT, 25.0, False),
                widget='example:temperature.widget',
                ui={'properties': {'unit': 'celsius'}}
            )
        )    
        # Add inlets with different widget types
        _ = self.add_inlet(PortInlet(
                id='float_select',  # id as first positional parameter
                label='Select',
                flow_type=FlowType.DATA,
                is_pooled=False,
                data=SingleField(DataType.STRING, "Option 1", False),
                widget='core:select.widget',
                ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'float_slider',  # element_id as first positional parameter
                label='Float Slider',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.FLOAT, 50.0, False),
                widget='core:slider.widget',
                ui={'properties': {'min': 0, 'max': 100, 'step': 1}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'bool_switch',  # element_id as first positional parameter
                label='Boolean Switch',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.BOOL, True, False),
                widget='core:switch.widget',
                ui={'properties': {'text': 'Enable Feature'}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.STRING, 'Hello', False),
                widget='core:text.input.widget',
                ui={'properties': {'placeholder': 'Enter text...'}}
            )   
        )
        _ = self.add_inlet(PortInlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.INT, 42, False),
                widget='core:number.widget',
                ui={'properties': {}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'callback',  # element_id as first positional parameter
                label='Callback Widget',
                flow_type=FlowType.CALLBACK,
            )
        )

        _ = self.add_outlet(PortOutlet(
                'execute',  # element_id as first positional parameter
                label='Execute',
                flow_type=FlowType.CTRL
            )
        )
        _ = self.add_outlet(PortOutlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                flow_type=FlowType.DATA,
                data=SingleField(DataType.INT, 42, False),
            )
        )

    
    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        return None

