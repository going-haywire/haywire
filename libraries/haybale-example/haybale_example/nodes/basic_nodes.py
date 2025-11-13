"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.base_node import node
from haywire.core.node.base_node import BaseNode
from haywire.core.data.enums import ContainerType, FlowType
from haywire.libraries.core.types.specs import BOOL, CALLBACK, EXEC, FLOAT, INT, STRING

from ..types.mesh_data import MeshData
from ..types.specs import Temperature

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

        # Add control inlet (no type, just execution flow)
        _ = self.add_inlet(EXEC.as_inlet(id='execute'))

        _ = self.add_inlet(Temperature.as_inlet(
                id='temp_config',
                default=40.0
            )) 

        # Add inlets with different widget types
        _ = self.add_inlet(STRING.as_inlet(
                id='string_input',
                label='Select',
                widget='core:select.widget',
                ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}},
                default='Option 3'
            ))
        
        _ = self.add_inlet(FLOAT.as_inlet(
                id='float_slider',
                label='Float Slider',
                widget='core:slider.widget',
                ui={'properties': {'min': 0.0, 'max': 100.0, 'step': 1}},
                default=50.0
            ))

        _ = self.add_inlet(BOOL.as_inlet(
                id='bool_switch',
                label='Boolean Switch',
                widget='core:switch.widget',
                ui={'properties': {'text': 'Enable Feature'}},
                default=True
            ))
        
        _ = self.add_inlet(STRING.as_inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                default='Hello, Haywire!',
                widget='core:text.input.widget',
                ui={'properties': {'placeholder': 'Enter text...'}}
            ))

        _ = self.add_inlet(MeshData.as_inlet(
                id='mesh_data_inlet', 
                label='Mesh Data Inlet'
            ))

        _ = self.add_inlet(INT.as_inlet(
                id='int_input',
                label='Missing Widget',
                widget='core:number.widget',
                ui={'properties': {}},
                default=42
            ))

        _ = self.add_inlet(CALLBACK.as_inlet(id='callback'))

        # Add outlets
        _ = self.add_outlet(EXEC.as_outlet(id='execute'))

        _ = self.add_outlet(FLOAT.as_outlet(
                id='float',
                label='Float Output'
            ))

        _ = self.add_outlet(BOOL.as_outlet(
                id='bool_switch',
                label='Boolean Output'
            ))
        
        _ = self.add_outlet(STRING.as_outlet(
                id='string_output',
                label='Text Output'
            ))

    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        return None

