"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from nicegui import ui

from haywire.core.data.fields import DataField
from haywire.core.ui.base_widget import BaseWidget
from haywire.core.node.ports import DataPort
from haywire.core.ui.base_widget import widget

@widget(
    is_error_widget=True, 
    description="Widget displayed when no appropriate widget is found")
class ErrorWidget(BaseWidget):
    """Widget displayed when no appropriate widget is found"""
    
    def on_model_change(self, value: float):  
        """Update the number input's value"""  
        pass

    def create_element(self) -> Any:
        """Create an error display widget"""
        error_msg = f"'{self.element.widget}'" if self.element.widget else "No default widget defined"
        
        with ui.column().classes('w-full h-full p-2 border border-red-500 bg-red-50') as label:
            with ui.row().classes('items-center gap-2 mb-1'):
                ui.icon('error', color='red').classes('text-lg')
                ui.label(f"Widget not found").classes('text-red-700 text-sm font-bold')
            # Show current value as read-only
            ui.label(f"'{error_msg}'").classes('text-red-600 text-xs font-bold')
            ui.label(f"Element ID: {self.element_id}").classes('text-red-600 text-xs')
            ui.label(f"Value: {self.get_value()}").classes('text-red-600 text-xs')
            ui.label(f"Data type: {self.data_field.type}").classes('text-red-600 text-xs')
                    
        return label
