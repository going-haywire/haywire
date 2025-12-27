"""
Basic core node implementations
"""

# Import the node system base class
from haywire.core.node.base import node
from haywire.core.node.base import BaseNode
from haywire.libraries.core.types.pooled_type import PooledType
from haywire.libraries.core.types.specs import BOOL, CALLBACK, EXEC, FLOAT, INT, STRING

from ..types.mesh_data import MeshData
from ..types.specs import Temperature

@node(
    label='Test Node Four',
    search_tags=['constant', 'value', 'output', 'basic'],
    menu='core/basic'
)
class TestNodeOne(BaseNode):
    """Node that outputs a constant value"""
    
    def __init__(self, node_id, wrapper):
        super().__init__(node_id, wrapper)
        
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False

        # Add control inlet (no type, just execution flow)
        self.add(EXEC.as_inlet(id='execute'))

        self.add(Temperature.as_inlet(
                id='temp_config',
                default=40.0
            )) 

        self.add(PooledType[STRING].as_inlet(
                id='pooled_data_inlet',
                label='Pooled Data Inlet'
            ))

        # Add inlets with different widget types
        self.add(STRING.as_inlet(
                id='string_selector',
                label='Selector',
                widget='core:widget:select.widget',
                ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}},
                default='Option 3'
            ))
        
        self.add(FLOAT.as_inlet(
                id='float_slider',
                label='Float Sliderio',
                widget='core:widget:slider.widget',
                ui={'properties': {'min': 0.0, 'max': 60.0, 'step': 1}},
                default=50.0
            ))

        self.add(BOOL.as_inlet(
                id='bool_switch',
                label='Boolean Switch',
                widget='core:widget:switch.widget',
                ui={'properties': {'text': 'Enable Feature'}},
                default=True
            ))

        self.add(STRING.as_inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                default='Hello, Haywire!',
                widget='core:widget:text.widget',
                ui={'properties': {'placeholder': 'Enter text...'}}
            ))

        self.add(MeshData.as_inlet(
                id='mesh_data_inlet', 
                label='Mesh Data Inlet'
            ))

        self.add(INT.as_inlet(
                id='int_input',
                label='Missing Widget',
                widget='core:widget:number.widget',
                ui={'properties': {}},
                default=42
            ))

        self.add(CALLBACK.as_inlet(id='callback'))

        # Add outlets
        self.add(EXEC.as_outlet(id='execute'))

        self.add(FLOAT.as_outlet(
                id='float',
                label='Float Output'
            ))

        self.add(BOOL.as_outlet(
                id='bool_switch',
                label='Boolean Output'
            ))
        
        self.add(STRING.as_outlet(
                id='string_output',
                label='Text Output'
            ))

    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        # wert = self.inlets['float_slider'].data.value.value
        # wert = self.inlets['float_slider'].value.value
        # get_inlet_value("float_slider").value

        return None
    

