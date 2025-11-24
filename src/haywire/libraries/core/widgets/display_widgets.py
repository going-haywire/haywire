"""
Display widgets for read-only data visualization
"""

from typing import Any, Dict
from nicegui import ui

from haywire.core.ui.widget.base import BaseWidget
from haywire.core.ui.widget.decorator import widget
from haywire.libraries.core.types.specs import BOOL, FLOAT, INT, STRING

@widget(
        description="Read-only label widget for displaying data",
        compatible_types=[FLOAT, INT, STRING, BOOL]
    )
class LabelWidget(BaseWidget):
    """Read-only label widget for displaying data"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else ' '   

    def create_element(self) -> Any:
        """Create a label element"""
        text = str(self._get_typed_value()) if self._get_typed_value() is not None else ''
        
        # Apply styling from props
        classes = self.ui_properties.get('classes', 'text-sm')
        
        return ui.label(text).classes(f'w-full {classes}').bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )

@widget(
        description="Progress bar widget for numeric data",
        compatible_types=[FLOAT, INT]
    )
class ProgressWidget(BaseWidget):
    """Progress bar widget for numeric data"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else 0    

    def create_element(self) -> Any:
        """Create a progress bar element"""
        value = self._get_typed_value() or 0
        
        # Get min/max from props
        min_val = self.ui_properties.get('min', 0)
        max_val = self.ui_properties.get('max', 100)
        
        # Normalize value to 0-1 range
        normalized_value = (value - min_val) / (max_val - min_val) if max_val != min_val else 0
        normalized_value = max(0, min(1, normalized_value))
        
        return ui.linear_progress(value=normalized_value).classes('w-full').bind_value_from(
            self.data_field, 'value', 
            backward=lambda x: max(0, min(1, (x - min_val) / (max_val - min_val))) if x is not None else 0
        )

@widget(
    description="Badge widget for displaying status or short text",
    compatible_types=[STRING]
    )
class BadgeWidget(BaseWidget):
    """Badge widget for displaying status or short text"""

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else ''    

    def create_element(self) -> Any:
        """Create a badge element"""
        text = str(self._get_typed_value()) if self._get_typed_value() is not None else ''
        color = self.ui_properties.get('color', 'primary')
        
        return ui.badge(text, color=color).bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )
