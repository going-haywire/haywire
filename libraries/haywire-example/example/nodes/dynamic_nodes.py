"""
Basic core node implementations
"""

from example.nodes.util import simple_function

# Import the node system base class
from haywire.core.node.base_node import node
from haywire.core.node.base_node import BaseNode
from haywire.core.node.elements import Inlet, Outlet
from haywire.core.data.enums import DataType, DataContainerType, FlowType
from haywire.core.data.fields import SingleField
from haywire.core.node.elements import PinBuilder
from haywire.libraries.core.adapters import FLOAT, INT, STRING

@node(
    label='Configurable Math Node',
    search_tags=['math', 'operation', 'configurable'],
    menu='math/basic'
)
class ConfigurableMathNode(BaseNode):
    """Node demonstrating configs and properties"""
    
    # Control flow
    execute_in = PinBuilder.ctrl_inlet('Execute')
    execute_out = PinBuilder.ctrl_outlet('Execute')
    
    # Config - has callback, no pin, reconfigures node structure
    operation_config = PinBuilder.config(
        STRING(value='add'),
        label='Operation Mode',
        widget='haywire.core:select.widget',
        ui={'properties': {'options': ['add', 'multiply', 'power']}},
        callback=lambda self: self._on_operation_changed()
    )

    precision_config = PinBuilder.config(
        INT(value=2),
        label='Decimal Precision',
        widget='haywire.core:number.widget'
    )
    
    # Property - no callback, no pin, just user-editable value
    author_property = PinBuilder.property(
        STRING(value=''),
        label='Author',
        widget='haywire.core:text.input.widget'
    )
    
    description_property = PinBuilder.property(
        STRING(value=''),
        label='Description',
        widget='haywire.core:text.area.widget'
    )
    
    # Regular data inlets
    value_a = PinBuilder.inlet(FLOAT(value=0.0), 'Value A')
    value_b = PinBuilder.inlet(FLOAT(value=0.0), 'Value B')
    
    # Data outlet
    result = PinBuilder.outlet(FLOAT(value=0.0), 'Result')
    
    def __init__(self, node_id, graph):
        super().__init__(node_id, graph)
        
        # Initial configuration based on config values
        self._configure_for_operation()
    
    def _on_operation_changed(self):
        """Callback when operation config changes"""
        # Notify graph that structure may have changed
        self.graph.mark_dirty(self.node_id)
        
        # Reconfigure node based on new operation
        self._configure_for_operation()
        
        # Trigger re-assembly if needed
        self.graph.request_reassembly(self.node_id)
    
    def _configure_for_operation(self):
        """Dynamically add inlets based on operation config"""
        operation = self.operation_config.data.get_value()
        
        # Remove old dynamic inlets
        if 'exponent' in self.inlets:
            del self.inlets['exponent']
            delattr(self, 'exponent')
        
        # Add operation-specific inlets
        if operation == 'power':
            self.add_inlet(
                Inlet(
                    id='exponent',  # id as first positional parameter
                    data=SingleField('exponent', DataType.FLOAT, 25.0, False),
                )
            )

    def worker(self, context: dict) -> dict | None:
        """Execute the node"""
        #test_value = simple_function(self.node_id)

        # Access config values (read-only in worker)
        operation = self.operation_config.data.get_value()
        precision = self.precision_config.data.get_value()
        
        # Access property values (read-only in worker)
        author = self.author_property.data.get_value()
        
        # Access data inlets
        a = self.value_a.data.get_value()
        b = self.value_b.data.get_value()
        
        # Perform operation
        if operation == 'add':
            result = a + b
        elif operation == 'multiply':
            result = a * b
        elif operation == 'power':
            exponent = self.exponent.data.get_value()
            result = a ** exponent
        
        # Apply precision from config
        result = round(result, precision)
        
        # Set output
        self.result.data.set_value(result)
        
        return {'outlet': 'execute_out'}