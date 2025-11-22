"""
Base widget classes for the Haywire widget system
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.ui.base_widget import BaseWidget
from haywire.core.ui.base_widget import widget
from haywire.ui.render_error_details import render_error_details

@widget(
    _is_error=True, 
    description="Widget displayed when no appropriate widget is found")
class ErrorWidget(BaseWidget):
    """Widget displayed when no appropriate widget is found"""
    
    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        pass

    def create_element(self) -> Any:
        """Create an error display widget with lazy-loaded details"""
        
        # Use the error attribute from BaseWidget
        error = self.error
        
        if not error or not isinstance(error, HaywireException):
            # Create a default error if none provided
            error = HaywireException.create(
                message="An error occurred but no detailed information is available",
                category="Unknown Error"
            )
        
        with ui.column().classes('w-full') as container:
            # Compact error summary card
            with ui.card().classes('w-full bg-red-50 border-l-4 border-red-500 shadow-sm'):
                with ui.row().classes('items-start gap-3 w-full'):
                    # Icon
                    ui.icon(error.get_severity_icon(), color=error.get_severity_color()).classes('text-2xl')
                    
                    # Error message and button
                    with ui.column().classes('flex-grow gap-1'):
                        ui.label(f"{error.category}").classes('text-red-700 font-bold text-sm')
                        ui.label(error.message).classes('text-gray-800 text-sm')
                        
                        with ui.row().classes('gap-2 mt-2'):
                            detail_button = ui.button('Show Details', icon='expand_more').classes('bg-red-600 text-white')
            
            # Create dialog with lazy content rendering
            dialog = ui.dialog()
            
            def show_details():
                """Render error details on-demand when dialog is opened"""
                # Clear any existing content
                dialog.clear()
                
                # Create the dialog content NOW (lazy rendering)
                with dialog, ui.card().classes('w-full max-w-4xl bg-gray-50'):
                    with ui.column().classes('w-full gap-4 p-4'):
                        # Render error details using the reusable function
                        detail_container = ui.column().classes('w-full gap-4')
                        render_error_details(error, detail_container)
                        
                        # Footer with close button
                        with ui.row().classes('justify-end w-full pt-3 border-t'):
                            ui.button('Close', icon='close', on_click=dialog.close).classes('bg-gray-600 text-white')
                
                # Open the dialog
                dialog.open()
            
            # Connect button to lazy rendering function
            detail_button.on_click(show_details)
                                   
        return container