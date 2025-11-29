"""
Basic widget implementations for common data types
"""

from typing import Any, Dict
from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget

from haywire.libraries.core.types.specs import BOOL, FLOAT, INT, STRING
from haywire.ui.widget.simple import SimpleWidget

@widget(
    description="Fast number input widget",
    compatible_types=[FLOAT, INT]
)
class NumberWidget(SimpleWidget):
    """number widget for performance-critical scenarios"""
    
    def create_element(self) -> Any:
        kwargs = {'value': 0}
        
        # Apply UI properties
        for prop in ['label', 'min', 'max', 'step', 'precision', 'prefix', 'suffix']:
            if prop in self.ui_properties:
                kwargs[prop] = self.ui_properties[prop]
        
        return ui.number(**kwargs).classes('w-full')
    
    def get_default_value(self) -> float:
        return 0.0


@widget(
    description="Fast text input widget",
    compatible_types=[STRING]
)
class TextWidget(SimpleWidget):
    """text input for simple string binding"""
    
    def create_element(self) -> Any:
        kwargs = {'value': ''}
        
        for prop in ['label', 'placeholder', 'password']:
            if prop in self.ui_properties:
                kwargs[prop] = self.ui_properties[prop]
        
        return ui.input(**kwargs).classes('w-full')
    
    def get_default_value(self) -> str:
        return ''


@widget(
    description="checkbox widget",
    compatible_types=[BOOL]
)
class CheckboxWidget(SimpleWidget):
    """checkbox for boolean binding"""
    
    def create_element(self) -> Any:
        kwargs = {'value': False}
        
        if 'text' in self.ui_properties:
            kwargs['text'] = self.ui_properties['text']
        
        return ui.checkbox(**kwargs).classes('w-full')
    
    def get_default_value(self) -> bool:
        return False


@widget(
    description="switch widget",
    compatible_types=[BOOL]
)
class SwitchWidget(SimpleWidget):
    """switch for boolean binding"""
    
    def create_element(self) -> Any:
        kwargs = {'value': False}
        
        if 'text' in self.ui_properties:
            kwargs['text'] = self.ui_properties['text']
        
        return ui.switch(**kwargs).classes('w-full')
    
    def get_default_value(self) -> bool:
        return False


@widget(
    description="slider widget",
    compatible_types=[FLOAT, INT]
)
class SliderWidget(SimpleWidget):
    """slider for numeric ranges"""
    
    def create_element(self) -> Any:
        kwargs = {
            'value': 0,
            'min': self.ui_properties.get('min', 0),
            'max': self.ui_properties.get('max', 100),
            'step': self.ui_properties.get('step', 1)
        }
        
        return ui.slider(**kwargs).classes('w-full').props('label-always')
    
    def get_default_value(self) -> float:
        return float(self.ui_properties.get('min', 0))


@widget(
    description="select widget",
    compatible_types=[INT, STRING]
)
class SelectWidget(SimpleWidget):
    """dropdown select"""
    
    def create_element(self) -> Any:
        kwargs = {
            'options': self.ui_properties.get('options', []),
            'value': None
        }
        
        for prop in ['clearable', 'multiple']:
            if prop in self.ui_properties:
                kwargs[prop] = self.ui_properties[prop]
        
        return ui.select(**kwargs).classes('w-full')


@widget(
    description="knob widget",
    compatible_types=[FLOAT, INT]
)
class KnobWidget(SimpleWidget):
    """knob for numeric input"""
    
    def create_element(self) -> Any:
        kwargs = {
            'value': 0,
            'show_value': True
        }
        
        for prop in ['min', 'max', 'step', 'color', 'size']:
            if prop in self.ui_properties:
                kwargs[prop] = self.ui_properties[prop]
        
        with ui.row().classes('w-full justify-center'):
            knob = ui.knob(**kwargs)
        
        return knob.classes('w-32 h-32')
    
    def get_default_value(self) -> float:
        return 0.0


# Read-only widget example
@widget(
    description="Simple label for display only",
    compatible_types=[STRING, FLOAT, INT]
)
class SimpleLabelWidget(SimpleWidget):
    """Read-only label widget"""
    
    # Override class attributes
    UI_PROPERTY = 'text'
    IS_READONLY = True
    
    def create_element(self) -> Any:
        return ui.label('').classes('text-base')
    
    def get_default_value(self) -> str:
        return ''
