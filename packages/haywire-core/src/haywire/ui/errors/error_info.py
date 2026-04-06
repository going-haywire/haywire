from nicegui import element, ui
from haywire.ui import elements as hui

from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.node.dataclasses import NodeErrorInfo

from haywire.ui.errors.haywire_exception import render_error_details
from haywire.ui.graph_canvas.popup import Popup


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
            message="An error occurred but no detailed information is available", category="Unknown Error"
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
            width="400",  # Adapts to content width
            height="auto",
            backdrop_click_close=True,
            escape_close=True,
            backdrop_color="rgba(0,0,0,0.5)",
            clamp_to_viewport=True,
            title="Error Details",
            draggable=True,
            closable=True,
        )

        # Render error details inside the popup
        with popup:
            # Container with min/max constraints for adaptive sizing
            with (
                ui.column()
                .classes("w-full gap-4 overflow-y-auto")
                .style("min-width: 600px; max-width: min(1200px, 90vw); max-height: 80vh;")
            ):
                # Render error details using the reusable function
                detail_container = ui.column().classes("w-full gap-4")
                render_error_details(error, detail_container)

                # Footer with close button
                with (
                    ui.row()
                    .classes("justify-end w-full pt-3 mt-4")
                    .style("border-top: 1px solid var(--hw-border);")
                ):
                    ui.button("Close", icon=hui.icon.close, on_click=close_popup).props("flat")

        # Register cleanup callback when popup is closed via other means
        # (backdrop click, escape key, etc.)
        popup.on_close(lambda: close_popup())

        # Open the popup and track it
        popup.open()
        current_popup = popup

    # Build the compact error summary UI
    with ui.column().classes("w-full") as container:
        # Compact error summary
        with (
            ui.column()
            .classes("w-full p-2")
            .style("border-left: 4px solid var(--hw-danger); background: var(--hw-danger-bg);")
        ):
            with ui.row().classes("items-start gap-3 w-full"):
                detail_button = (
                    ui.button(icon=hui.icon.debug)
                    .props("flat dense")
                    .style("background: var(--hw-danger); color: var(--hw-text-on-accent);")
                )

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
    with (
        ui.column()
        .classes("items-left p-2")
        .style("border: 1px solid var(--hw-danger); background: var(--hw-danger-bg);") as error_column
    ):
        with ui.row():
            ui.icon(hui.icon.error).classes("text-sm").style("color: var(--hw-danger);")
            ui.label(error_info.error).classes("text-sm hw-text-danger")
        ui.label(error_info.error_message).classes("text-xs hw-text-danger")
        if error_info.note:
            for value in error_info.note:
                ui.label(value).classes("text-xs hw-text-danger")
        ui.label(error_info.timestamp).classes("text-xs hw-text-danger")
    return error_column
