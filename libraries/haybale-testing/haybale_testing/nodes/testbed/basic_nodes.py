"""
Basic core node implementations
"""

# Import the node system base class
from haybale_test_a.types.maps_string_type import MapsStringType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node import node, BaseNode, NodeType

@node(
    label='Test Node Four',
    search_tags=['constant', 'value', 'output', 'basic'],
    menu='testing/testbed',
    node_type=NodeType.CONTROL
)
class TestNodeOne(BaseNode):
    """Node that outputs a constant value"""
    
    def init(self):
        from haybale_core.types.array_type import ArrayType
        from haybale_core.types.pooled_type import PooledType
        from haybale_core.types.specs import (
            BOOL,
            CALLBACK,
            EXEC,
            FLOAT,
            GROUP,
            INT,
            STRING,
        )
        from haybale_core.widgets.basic_widgets import (
            NumberWidget,
            SelectWidget,
            SliderWidget,
            SwitchWidget,
            TextWidget,
        )
        from haybale_testing.types.temperature import Temperature

        self.push()

        # Add control inlet (no type, just execution flow)
        self.add(EXEC.as_inlet(id='execute_in'))

        with self.group(GROUP.as_inlet(
                id='advanced_settings',
                label='Advanced Settings',
                default=False,
                on_change='redraw'
                )):
            self.add(PooledType[STRING].as_inlet(
                    id='pooled_string_inlet',
                    label='Pooled STRING Inlet'
                ))
       
            with self.group(GROUP.as_inlet(
                    id='temperature_config_group',
                    label='Temperature Configuration',
                    default=False,
                    on_change='redraw'
                    )):
                self.add(PooledType[ArrayType[STRING]].as_inlet(
                        id='pooled_array_string_inlet',
                        label='Pooled ARRAY[STRING]'
                    ))

        # Add inlets with different widget types
        self.add(STRING.as_inlet(
                id='string_selector',
                label='Selector',
                widget=SelectWidget.config(properties={'options': ['Option 1', 'Option 2', 'Option 3']}),
                default='Option 1'
            ))
        
        self.add(FLOAT.as_inlet(
                id='float_slider',
                label='Float Sliderio',
                widget=SliderWidget.config(properties={'min': 0.0, 'max': 60.0, 'step': 1}),
                default=50.0
            ))

        self.add(BOOL.as_inlet(
                id='bool_switch_in',
                label='Boolean Switch',
                widget=SwitchWidget.config(properties={'text': 'Enable Feature'}),
                default=True
            ))

        self.add(STRING.as_inlet(
                'string_input',  # element_id as first positional parameter
                label='Text Input',
                default='Hello, Haywire!',
                widget=TextWidget.config(properties={'placeholder': 'Enter text...'})
            ))

        self.add(INT.as_inlet(
                id='int_input',
                label='Missing Widget',
                widget=NumberWidget.config(),
                default=42
            ))

        self.add(CALLBACK.as_inlet(id='callback'))

        # Temperature inlet (derived from FLOAT — tests type hierarchy)
        self.add(Temperature.as_inlet(
                id='temperature_in',
                label='Temperature',
                default=20.0
            ))

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

        with self.group(GROUP.as_outlet(
                id='out_group',
                label='Advanced Settings',
                default=False,
                on_change='redraw'
                )):
            self.add(ArrayType[BOOL].as_outlet(
                    id='array_bool_outlet',
                    label='ARRAY[BOOL]'
                ))

            self.add(MapsStringType[BOOL].as_outlet(
                    id='mapsString_bool_outlet',
                    label='MAPSSTRING[BOOL]'
                ))

        # Temperature outlet (derived from FLOAT — tests type hierarchy)
        self.add(Temperature.as_outlet(
                id='temperature_out',
                label='Temperature'
            ))

        self.pop()

    def redraw(self, *args, **kwargs) -> None:
        """Request a redraw of the node in the UI."""
        self.wrapper.redraw()

    def worker(self, context: ExecutionContext) -> dict | None:
        """Execute the node - return the constant value"""
        wert = self.value('float_slider')

        self.out('float', wert)
    

