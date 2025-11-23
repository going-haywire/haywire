from nicegui import element, ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo

from haywire.ui.errors.haywire_exception import render_error_details

def error_render_detail(error: HaywireException) -> None:
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


def render_error_info(error_info: NodeErrorInfo) -> element:
    """
    Render error information for a node.

    Args:
        node: The HaywireNode with error information

    Returns:
        bool: True if error info was rendered, False if no error info
    """
    with ui.column().classes('items-left p-2 border border-red-500 bg-red-50') as error_column:
        with ui.row():
            ui.icon('error', color='red').classes('text-lg')
            ui.label(error_info.error).classes('text-lg text-red-600')
        ui.label(error_info.error_message).classes('text-sm text-red-600')
        if error_info.note:
            for value in error_info.note:
                ui.label(value).classes('text-sm text-red-600')
        ui.label(error_info.timestamp).classes('text-sm text-red-600')
    return error_column