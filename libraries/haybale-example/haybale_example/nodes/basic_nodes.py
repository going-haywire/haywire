"""
Basic core node implementations
"""

# Import the node system base class
from haybale_test_a.types.maps_string_type import MapsStringType
from haywire.core.node.base import node
from haywire.core.node.base import BaseNode
from haywire.libraries.core.types.array_type import ArrayType
from haywire.libraries.core.types.pooled_type import PooledType
from haywire.libraries.core.types.specs import BOOL, CALLBACK, EXEC, FLOAT, GROUP, INT, STRING

from ..types.mesh_data import MeshData
from ..types.specs import Temperature

@node(
    label='Test Node Four',
    search_tags=['constant', 'value', 'output', 'basic'],
    menu='core/basic'
)
class TestNodeOne(BaseNode):
    """Node that outputs a constant value"""
    
    def initialize(self):
        # Configure behavior
        self.behavior.is_data_node = True
        self.behavior.is_control_node = False

        # Add control inlet (no type, just execution flow)
        self.add(EXEC.as_inlet(id='execute_in'))

        with self.group(GROUP.as_inlet(
                id='advanced_settings',
                label='Advanced Settings',
                default=False,
                on_change='wrapper:redraw'
                )):
            
            with self.section('idle_inlets'):
                self.add(Temperature.as_inlet(
                        id='temp_config',
                        default=40.0
                    )) 

            self.add(PooledType[STRING].as_inlet(
                    id='pooled_string_inlet',
                    label='Pooled STRING Inlet'
                ))

            self.add(PooledType[ArrayType[STRING]].as_inlet(
                    id='pooled_array_string_inlet',
                    label='Pooled ARRAY[STRING]'
                ))

        # Add inlets with different widget types
        self.add(STRING.as_inlet(
                id='string_selector',
                label='Selector',
                widget='core:widget:select.widget',
                ui={'properties': {'options': ['Option 1', 'Option 2', 'Option 3']}},
                default='Option 1'
            ))
        
        self.add(FLOAT.as_inlet(
                id='float_slider',
                label='Float Sliderio',
                widget='core:widget:slider.widget',
                ui={'properties': {'min': 0.0, 'max': 60.0, 'step': 1}},
                default=50.0
            ))

        self.add(BOOL.as_inlet(
                id='bool_switch_in',
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
                default=42
            ))

        self.add(CALLBACK.as_inlet(id='callback'))

        # Add outlets
        self.add(EXEC.as_outlet(id='execute_out'))

        self.add(FLOAT.as_outlet(
                id='float',
                label='Float Output'
            ))

        self.add(BOOL.as_outlet(
                id='bool_switch_out',
                label='Boolean Output'
            ))
        
        self.add(STRING.as_outlet(
                id='string_output',
                label='Text Output'
            ))

        self.add(ArrayType[STRING].as_outlet(
                id='array_string_outlet',
                label='ARRAY[STRING]'
            ))

        self.add(ArrayType[INT].as_outlet(
                id='array_int_outlet',
                label='ARRAY[INT]'
            ))

        self.add(ArrayType[BOOL].as_outlet(
                id='array_bool_outlet',
                label='ARRAY[BOOL]'
            ))

        self.add(MapsStringType[BOOL].as_outlet(
                id='mapsString_bool_outlet',
                label='MAPSSTRING[BOOL]'
            ))


    def worker(self, context: dict) -> dict | None:
        """Execute the node - return the constant value"""
        # wert = self.inlets['float_slider'].data.value.value
        # wert = self.inlets['float_slider'].value.value
        # get_inlet_value("float_slider").value

        return None
    

