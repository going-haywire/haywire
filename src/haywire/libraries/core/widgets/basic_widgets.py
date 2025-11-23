"""
Basic widget implementations for common data types
"""

from typing import Any, Dict
from nicegui import ui

from haywire.core.ui.widget.base import BaseWidget
from haywire.core.ui.widget.decorator import widget

@widget(
    description="Text input widget for string data"
    )
class TextInputWidget(BaseWidget):
    """Text input widget for string data"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else 'empty'    

    def create_element(self) -> Any:
        """Create a text input element"""
        input_kwargs = {
            'value': self.get_value() or ''
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'password', 'password_toggle_button', 'autocomplete']:
            if prop in self.ui_properties:
                input_kwargs[prop] = self.ui_properties[prop]

        return ui.input(**input_kwargs).classes('w-full')

@widget(
    description="Number input widget for numeric data"
    )
class NumberWidget(BaseWidget):
    """Number input widget for numeric data"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else 0    
     
    def create_element(self) -> Any:
        """Create a number input element"""
        number_kwargs = {
            'value': self.get_value() or 0
        }
        
        # Apply direct property mapping
        for prop in ['label', 'placeholder', 'min', 'max', 'precision', 'step', 'prefix', 'suffix', 'format']:
            if prop in self.ui_properties:
                number_kwargs[prop] = self.ui_properties[prop]
        
		# Create the UI element  
        return ui.number(**number_kwargs).classes('w-full')

@widget(
    description="Checkbox widget for boolean data"
    )
class CheckboxWidget(BaseWidget):
    """Checkbox widget for boolean data"""
    
    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else False    

    def create_element(self) -> Any:
        """Create a checkbox element"""
        checkbox_kwargs = {
            'value': bool(self.get_value())
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in self.ui_properties:
                checkbox_kwargs[prop] = self.ui_properties[prop]

        return ui.checkbox(**checkbox_kwargs).classes('w-full')

@widget(
    description="Switch widget for boolean data")
class SwitchWidget(BaseWidget):
    """Switch widget for boolean data"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else False    

    def create_element(self) -> Any:
        """Create a switch element"""
        switch_kwargs = {
            'value': bool(self.get_value())
        }
        
        # Apply direct property mapping
        for prop in ['text']:
            if prop in self.ui_properties:
                switch_kwargs[prop] = self.ui_properties[prop]

        return ui.switch(**switch_kwargs).classes('w-full')

@widget(
    description="Dropdown select widget for choice-based data")
class SelectWidget(BaseWidget):
    """Dropdown select widget for choice-based data"""
    
    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else 0    

    def create_element(self) -> Any:
        """Create a dropdown select element"""
        select_kwargs = {
            'options': self.ui_properties.get('options', []),
            'value': self.get_value()
        }
        
        # Apply direct property mapping
        for prop in ['options', 'clearable', 'multiple', 'with_input']:
            if prop in self.ui_properties:
                select_kwargs[prop] = self.ui_properties[prop]
        
        def update_value(e):
            self.update_value(e.value)

        return ui.select(**select_kwargs, on_change=update_value).classes('w-full')

@widget(
    description="Slider widget for numeric data with range")
class SliderWidget(BaseWidget):
    """Slider widget for numeric data with range"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else 0    

    def create_element(self) -> Any:
        """Create a slider element"""
        slider_kwargs = {
            'value': self.get_value() or 0
        }
        
        # Apply direct property mapping
        for prop in ['min', 'max', 'step']:
            if prop in self.ui_properties:
                slider_kwargs[prop] = self.ui_properties[prop]
        
        # Set defaults if not specified
        if 'min' not in slider_kwargs:
            slider_kwargs['min'] = 0
        if 'max' not in slider_kwargs:
            slider_kwargs['max'] = 100
        
        def update_value(e):
            self.update_value(e.value)

        return ui.slider(**slider_kwargs, on_change=update_value).classes('w-full').props('label-always')

@widget(
    description="Knob widget for numeric data with rotary control")
class KnobWidget(BaseWidget):
    """Knob widget for numeric data with rotary control"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        self.ui_element.value = value if value is not None else 0    

    def create_element(self) -> Any:
        """Create a knob element"""
        knob_kwargs = {
            'value': self.get_value() or 0,
            'show_value': True
        }
        
        # Apply direct property mapping
        for prop in ['min', 'max', 'step', 'color', 'center_color', 'track_color', 'size', 'show_value']:
            if prop in self.ui_properties:
                knob_kwargs[prop] = self.ui_properties[prop]

        with ui.row().classes('w-full justify-center'):
            knob = ui.knob(**knob_kwargs)

        return knob.classes('w-32 h-32')

