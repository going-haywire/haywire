"""
Display widgets for read-only data visualization
"""

from typing import Any, Dict
from nicegui import ui

from haywire.ui.widget.base import BaseWidget

class LabelWidget(BaseWidget):
    """Read-only label widget for displaying data"""
    
    def create_element(self) -> Any:
        """Create a label element"""
        text = str(self.get_value()) if self.get_value() is not None else ''
        
        # Apply styling from props
        classes = self.ui_props.get('classes', 'text-sm')
        
        return ui.label(text).classes(f'w-full {classes}').bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )


class ProgressWidget(BaseWidget):
    """Progress bar widget for numeric data"""
    
    def create_element(self) -> Any:
        """Create a progress bar element"""
        value = self.get_value() or 0
        
        # Get min/max from props
        min_val = self.ui_props.get('min', 0)
        max_val = self.ui_props.get('max', 100)
        
        # Normalize value to 0-1 range
        normalized_value = (value - min_val) / (max_val - min_val) if max_val != min_val else 0
        normalized_value = max(0, min(1, normalized_value))
        
        return ui.linear_progress(value=normalized_value).classes('w-full').bind_value_from(
            self.data_field, 'value', 
            backward=lambda x: max(0, min(1, (x - min_val) / (max_val - min_val))) if x is not None else 0
        )


class BadgeWidget(BaseWidget):
    """Badge widget for displaying status or short text"""
    
    def create_element(self) -> Any:
        """Create a badge element"""
        text = str(self.get_value()) if self.get_value() is not None else ''
        color = self.ui_props.get('color', 'primary')
        
        return ui.badge(text, color=color).bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )
