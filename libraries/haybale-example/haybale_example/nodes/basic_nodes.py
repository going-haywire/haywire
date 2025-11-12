"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.base_node import node
from haywire.core.node.base_node import BaseNode
from haywire.core.node.ports import PortInlet, PortOutlet
from haywire.core.data.enums import ContainerType, FlowType
from haywire.core.data.fields import SingleField
from haywire.libraries.core.types.specs import STRING

from ..types.mesh_data import MeshData
from ..types.specs import TEMPERATURE

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
                cls_type=None,
                label='Execute',
                flow_type=FlowType.CTRL,
                is_pooled=False
            )
        )

        _ = self.add_inlet(TEMPERATURE.as_inlet(id='temp_config',default=40.0)) 

        # Add inlets with different widget types
        _ = self.add_inlet(PortInlet(
                id='float_select',  # id as first positional parameter
                label='Select',
                cls_type=str,
                flow_type=FlowType.DATA,
                is_pooled=False,
                data=SingleField(str, "Option 1", False),
                widget='core:select.widget',
                ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'float_slider',  # element_id as first positional parameter
                label='Float Slider',
                cls_type=float,
                flow_type=FlowType.DATA,
                data=SingleField(float, 50.0, False),
                widget='core:slider.widget',
                ui={'properties': {'min': 0, 'max': 100, 'step': 1}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'bool_switch',  # element_id as first positional parameter
                label='Boolean Switch',
                cls_type=bool,
                flow_type=FlowType.DATA,
                data=SingleField(bool, True, False),
                widget='core:switch.widget',
                ui={'properties': {'text': 'Enable Feature'}}
            )
        )
        _ = self.add_inlet(STRING.as_inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                flow_type=FlowType.DATA,
                default='Hello, Haywire!',
                widget='core:text.input.widget',
                ui={'properties': {'placeholder': 'Enter text...'}}
            )   
        )

        _ = self.add_inlet(MeshData.specs().as_inlet(id='mesh_data_inlet', label='Mesh Data Inlet'))

 
        _ = self.add_inlet(PortInlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                cls_type=int,
                flow_type=FlowType.DATA,
                data=SingleField(int, 42, False),
                widget='core:number.widget',
                ui={'properties': {}}
            )
        )
        _ = self.add_inlet(PortInlet(
                'callback',  # element_id as first positional parameter
                label='Callback Widget',
                cls_type=None,
                flow_type=FlowType.CALLBACK,
            )
        )

        _ = self.add_outlet(PortOutlet(
                'execute',  # element_id as first positional parameter
                label='Execute',
                cls_type=None,
                flow_type=FlowType.CTRL
            )
        )
        _ = self.add_outlet(PortOutlet(
                'nonexistent',  # element_id as first positional parameter
                label='Missing Widget',
                cls_type=int,
                flow_type=FlowType.DATA,
                data=SingleField(int, 42, False),
            )
        )

    
    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        return None

