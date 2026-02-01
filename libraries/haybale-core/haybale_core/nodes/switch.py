"""
Shutdown Event Node.

Triggered when the interpreter is shutting down, allowing for cleanup operations.
"""
from haybale_core.widgets.basic_widgets import NumberWidget
from haywire.core.execution.event_source import SystemEvent, SystemEventType
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType

@node(
    label='Control Switch',
    description='Switches control flow based on condition',
    menu='control/switch',
    search_tags=['switch', 'control', 'flow', 'event'],
    node_type=NodeType.CONTROL,
)
class ControlSwitch(BaseNode):
    """
    Triggered when execution is switching control flow based on condition.
    """
        
    def init(self):
        # Control output
        from haybale_core.widgets.basic_widgets import SelectWidget
        from ..types.specs import EXEC, FLOAT, INT, STRING

        self.add(EXEC.as_inlet('exec', label='Execute'))
        
        # Data output - timestamp of shutdown
        self.add(STRING.as_config(
            'DataType', 
            label='Data Type',
            widget=SelectWidget.config(properties={ 'options': ['int', 'float', 'string']}), 
            default='int',
            on_change='hb_change')
        )

        self.add(EXEC.as_outlet('true', label='True'))
        self.add(EXEC.as_outlet('false', label='False'))
    
    def on_init(self):
        self.hb_change()

    def hb_change(self, *args, **kwargs) -> None:
        from haybale_core.widgets.basic_widgets import SelectWidget, NumberWidget
        from ..types.specs import EXEC, FLOAT, INT, STRING

        self.push(exclude=['exec', 'true', 'false', 'DataType'])
        if self.value('DataType') == 'int':
            self.add(INT.as_inlet(
                'compare', 
                label='Compare',
                widget=NumberWidget.config()))
            self.add(STRING.as_config(
                'condition', 
                label='Condition',
                widget=SelectWidget.config(properties={ 'options': ['>', '>=', '==', '<', '<=', '!=' ]}), 
                default='==')
            )
            self.add(INT.as_inlet(
                'with', 
                label='With',
                widget=NumberWidget.config())
            )
        elif self.value('DataType') == 'float':
            self.add(FLOAT.as_inlet(
                'compare', 
                label='Compare',
                widget=NumberWidget.config()))
            self.add(STRING.as_config(
                'condition', 
                label='Condition',
                widget=SelectWidget.config(properties={ 'options': ['>', '>=', '==', '<', '<=', '!=' ]}), 
                default='==')
            )
            self.add(FLOAT.as_inlet(
                'with', 
                label='With',
                widget=NumberWidget.config())
            )
        else:  # string
            self.add(STRING.as_inlet(
                'compare', 
                label='Compare',
                default='')
            )
            self.add(STRING.as_inlet(
                'with', 
                label='With',
                default='')
            )

        self.pop()
    
    def worker(self, context: ExecutionContext) -> str | None:
        if self.value('DataType') == 'int':
            data = self.value('compare')
            condition = self.value('condition')
            target = self.value('with')
            if condition == '>':
                result = data > target
            elif condition == '>=':
                result = data >= target
            elif condition == '==':
                result = data == target
            elif condition == '<':
                result = data < target
            elif condition == '<=':
                result = data <= target
            elif condition == '!=':
                result = data != target
            else:
                result = False
        elif self.value('DataType') == 'float':
            data = self.value('compare')
            condition = self.value('condition')
            target = self.value('with')
            if condition == '>':
                result = data > target
            elif condition == '>=':
                result = data >= target
            elif condition == '==':
                result = data == target
            elif condition == '<':
                result = data < target
            elif condition == '<=':
                result = data <= target
            elif condition == '!=':
                result = data != target
            else:
                result = False
        else:  # string
            data = self.value('compare')
            target = self.value('with')
            result = data == target
        
        if result:
            return 'true'
        else: 
            return 'false'
