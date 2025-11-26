from nicegui import element, ui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo

from haywire.ui.errors.haywire_exception import render_error_details
from haywire.ui.editor.popup import Popup

def error_render_detail(error: HaywireException) -> ui.element:
    """
    Renders a compact error summary with a button to show detailed error information in a popup.
    
    Uses the custom Popup class with proper lifecycle management to ensure only one instance
    exists at a time and cleanup is handled correctly.
    
    Args:
        error: The HaywireException to render

    Returns:
        ui.element: The NiceGUI element containing the error summary and popup
    """
    if not error or not isinstance(error, HaywireException):
        # Create a default error if none provided
        error = HaywireException.create(
            message="An error occurred but no detailed information is available",
            category="Unknown Error"
        )

    # Track the current popup instance for this error detail renderer
    current_popup = None
    
    def close_popup():
        """Close and cleanup the current popup."""
        nonlocal current_popup
        popup = current_popup
        current_popup = None  # Prevent re-entrancy/race conditions
        if popup:
            popup.close()
            popup.delete()

    def show_details():
        """Show error details in a popup with lazy content rendering."""
        nonlocal current_popup
        
        # Close any existing popup first (ensures only one instance)
        close_popup()
        
        # Create new popup as a centered modal with adaptive width
        popup = Popup(
            width="fit-content",  # Adapts to content width
            height="auto",
            backdrop_click_close=True,
            escape_close=True,
            backdrop_color="rgba(0,0,0,0.5)"
        )
        
        # Render error details inside the popup
        with popup:
            # Container with min/max constraints for adaptive sizing
            with ui.column().classes('w-full gap-4 overflow-y-auto').style(
                'min-width: 600px; max-width: min(1200px, 90vw); max-height: 80vh;'
            ):
                # Render error details using the reusable function
                detail_container = ui.column().classes('w-full gap-4')
                render_error_details(error, detail_container)
                
                # Footer with close button
                with ui.row().classes('justify-end w-full pt-3 border-t mt-4'):
                    ui.button('Close', icon='close', on_click=close_popup).classes('bg-gray-600 text-white')
        
        # Register cleanup callback when popup is closed via other means
        # (backdrop click, escape key, etc.)
        popup.on_close(lambda: close_popup())
        
        # Open the popup and track it
        popup.open()
        current_popup = popup

    # Build the compact error summary UI
    with ui.column().classes('w-full') as container:
        # Compact error summary card
        with ui.card().classes('w-full bg-red-50 border-l-4 border-red-500 shadow-sm'):
            with ui.row().classes('items-start gap-3 w-full'):
                # Icon
                detail_button = ui.button(icon='bug_report').classes('w-full bg-red-600 text-white')
        
        # Connect button to show details
        detail_button.on_click(show_details)

    return container


def render_error_info(error_info: NodeErrorInfo) -> element:
    """
    Render error information for a node.

    Args:
        error_info: The NodeErrorInfo with error information

    Returns:
        ui.element: The rendered error info element
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