"""
Display widgets for read-only data visualization
"""

from typing import Any
from nicegui import ui

from haywire.ui.widget.base import BaseWidget
from haywire.ui.widget.decorator import widget
from ..types.specs import BOOL, FLOAT, INT, STRING

@widget(
        description="Read-only label widget for displaying data",
        compatible_types=[FLOAT, INT, STRING, BOOL]
    )
class LabelWidget(BaseWidget):
    """
    Read-only label widget that displays the port value as text.

    Config options (via ``LabelWidget.config(properties={...})``):

    - ``classes`` (str): Tailwind CSS classes applied to the label (default: ``'text-sm'``).

    Example::

        LabelWidget.config(properties={'classes': 'text-lg font-bold'})
    """

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else ' '   

    def create_element(self) -> Any:
        """Create a label element"""
        text = str(self._get_typed_value()) if self._get_typed_value() is not None else ''
        
        # Apply styling from props
        classes = self.config.get('properties', {}).get('classes', 'text-sm')
        
        return ui.label(text).classes(f'w-full {classes}').bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )

@widget(
        description="Progress bar widget for numeric data",
        compatible_types=[FLOAT, INT]
    )
class ProgressWidget(BaseWidget):
    """
    Horizontal progress bar widget for numeric ports.

    Config options (via ``ProgressWidget.config(properties={...})``):

    - ``min`` (int | float): Minimum value of the range (default: ``0``).
    - ``max`` (int | float): Maximum value of the range (default: ``100``).

    The value is automatically normalized to the 0–1 range for display.

    Example::

        ProgressWidget.config(properties={'min': 0, 'max': 1000})
    """

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else 0    

    def create_element(self) -> Any:
        """Create a progress bar element"""
        value = self._get_typed_value() or 0
        
        # Get min/max from props
        props = self.config.get('properties', {})
        min_val = props.get('min', 0)
        max_val = props.get('max', 100)
        
        # Normalize value to 0-1 range
        normalized_value = (value - min_val) / (max_val - min_val) if max_val != min_val else 0
        normalized_value = max(0, min(1, normalized_value))
        
        return ui.linear_progress(value=normalized_value).classes('w-full').bind_value_from(
            self.data_field, 'value', 
            backward=lambda x: (
                max(0, min(1, (x - min_val) / (max_val - min_val))) 
                if x is not None 
                else 0
            )
        )

@widget(
    description="Badge widget for displaying status or short text",
    compatible_types=[STRING]
    )
class BadgeWidget(BaseWidget):
    """
    Badge widget that displays a colored pill label for status or short text.

    Config options (via ``BadgeWidget.config(properties={...})``):

    - ``color`` (str): Quasar color name for the badge background (default: ``'primary'``).
      Examples: ``'positive'``, ``'negative'``, ``'warning'``, ``'info'``, ``'red'``, ``'green'``.

    Example::

        BadgeWidget.config(properties={'color': 'positive'})
    """

    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        unwrapped = self._get_typed_value()
        self.ui_element.value = unwrapped if unwrapped is not None else ''    

    def create_element(self) -> Any:
        """Create a badge element"""
        text = str(self._get_typed_value()) if self._get_typed_value() is not None else ''
        color = self.config.get('properties', {}).get('color', 'primary')
        
        return ui.badge(text, color=color).bind_text_from(
            self.data_field, 'value', backward=lambda x: str(x) if x is not None else ''
        )
