from haywire.core.node.dataclasses import NodeErrorInfo


from nicegui import element, ui


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