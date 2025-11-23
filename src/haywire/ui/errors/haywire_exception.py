"""
Render detailed error information for HaywireException in a NiceGUI UI.

usage:

    # Create dialog with lazy content rendering
    dialog = ui.dialog()
    
    def show_details():
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

"""

import os
from typing import Any
from nicegui import ui

from haywire.core.errors.haywire_exception import HaywireException

def _create_detail_row(label: str, value: str, icon: str, multiline: bool = False, monospace: bool = False):
    """Helper to create a consistent detail row"""
    classes = 'text-sm ' + ('font-mono' if monospace else '')
    
    with ui.row().classes('items-start gap-2 w-full'):
        ui.icon(icon, color='gray').classes('text-sm mt-0.5')
        ui.label(f"{label}:").classes('font-bold text-sm text-gray-600 min-w-20')
        if multiline and '\n' in value:
            with ui.column().classes('flex-grow'):
                lines = value.split('\n')
                ui.label(lines[0]).classes(classes)
                for line in lines[1:]:
                    ui.label(line).classes(classes + ' pl-4')
        else:
            ui.label(value).classes(classes + ' flex-grow')

def render_error_details(error: HaywireException, parent_container=None) -> Any:
    """
    Render detailed error information for a HaywireException.

    This is a reusable function that can be called from ErrorWidget or any other UI component.
    Can be used to render error details on-demand (lazy rendering).

    Args:
        error: The HaywireException to render
        parent_container: Optional parent container to render into. If None, creates a new column.

    Returns:
        The container with rendered error details
    """
    if parent_container is None:
        parent_container = ui.column().classes('w-full gap-4 p-4')

    with parent_container:
        # Header
        with ui.row().classes('items-center gap-2 w-full pb-3 border-b'):
            ui.icon(error.get_severity_icon(), color=error.get_severity_color()).classes('text-3xl')
            ui.label(f"{error.category}: {error.message}").classes('text-xl font-bold text-gray-800')

        # Main error info card
        with ui.card().classes('w-full bg-white'):
            with ui.column().classes('gap-2'):
                if error.operation:
                    _create_detail_row('Operation', error.operation, 'build')

                if error.severity:
                    _create_detail_row('Severity', error.severity.value.upper(), error.get_severity_icon())

                if error.context_type:
                    _create_detail_row('Context', error.context_type, 'code')

                if error.highlighted_item:
                    _create_detail_row('Item', error.highlighted_item, 'label')

                # Suggestions section
                if error.has_suggestions():
                    with ui.column().classes('gap-1 pt-2 mt-2 border-t'):
                        ui.label('💡 Suggestions:').classes('font-bold text-sm text-blue-700')
                        for suggestion in error.suggestions:
                            with ui.row().classes('items-start gap-2'):
                                ui.icon('lightbulb', color='orange').classes('text-sm')
                                ui.label(suggestion).classes('text-sm')

        # Library and context info
        if error.library_identity or error.module_name or error.registry_key:
            with ui.card().classes('w-full bg-white'):
                with ui.column().classes('gap-2'):
                    ui.label('📦 Context Information').classes('font-bold text-gray-700')

                    if error.library_identity:
                        _create_detail_row('Library', error.library_identity.label, 'folder')
                        if error.library_identity.folder_path:
                            _create_detail_row('Path', error.library_identity.folder_path, 'folder_open', monospace=True)

                    if error.registry_key:
                        _create_detail_row('Registry', error.registry_key, 'key')

                    if error.module_name:
                        _create_detail_row('Module', error.module_name, 'article')

        # Source code section
        if error.has_source_location():
            with ui.card().classes('w-full bg-white'):
                with ui.column().classes('gap-2'):
                    ui.label('📝 Source Location').classes('font-bold text-gray-700')

                    # File path
                    file_display = error.filename
                    if error.library_identity and error.library_identity.folder_path:
                        try:
                            rel_path = os.path.relpath(error.filename, error.library_identity.folder_path)
                            if not rel_path.startswith(".."):
                                file_display = f"./{rel_path}"
                        except ValueError:
                            pass

                    _create_detail_row('File', file_display, 'description', monospace=True)

                    if error.line_number:
                        _create_detail_row('Line', str(error.line_number), 'tag')

                    # Source code with context
                    if error.source_context:
                        with ui.column().classes('w-full mt-2'):
                            ui.label('Source Code:').classes('font-bold text-sm text-gray-600 mb-1')

                            with ui.column().classes('w-full bg-gray-900 rounded p-3 font-mono text-sm overflow-x-auto'):
                                for line_num, line_content in error.source_context:
                                    is_error_line = (line_num == error.line_number)

                                    with ui.row().classes('gap-2 items-start w-full ' +
                                        ('bg-red-900 -mx-3 px-3 py-1' if is_error_line else '')).style(
                                            'min-height: 1.5rem'
                                        ):
                                        # Line number
                                        ui.label(f"{line_num:3d}").classes(
                                            'text-gray-500 select-none ' +
                                            ('text-red-300 font-bold' if is_error_line else '')
                                        )
                                        # Line content with error marker
                                        if is_error_line:
                                            ui.label('»').classes('text-red-400 font-bold')
                                        ui.label(line_content or ' ').classes(
                                            'text-gray-300 flex-grow whitespace-pre ' +
                                            ('text-red-200 font-bold' if is_error_line else '')
                                        )

        # Traceback section (filter interesting frames)
        if error.traceback_frames:
            interesting_frames = [f for f in error.traceback_frames if error.is_interesting_frame(f)]

            if interesting_frames:
                with ui.card().classes('w-full bg-white'):
                    with ui.column().classes('gap-2'):
                        ui.label('🔍 Traceback').classes('font-bold text-gray-700')

                        with ui.column().classes('w-full gap-3 pl-4'):
                            for frame in interesting_frames:
                                filename = frame['file']
                                line_number = frame['line']
                                function_name = frame['function']
                                source_line = frame['code']

                                base_filename = os.path.basename(filename)

                                with ui.column().classes('gap-1 border-l-2 border-blue-300 pl-3 py-1'):
                                    # Location
                                    with ui.row().classes('items-center gap-2'):
                                        ui.icon('arrow_right', color='blue').classes('text-sm')
                                        ui.label(f"{base_filename}").classes('font-bold text-sm')
                                        ui.label(f"in {function_name}").classes('text-sm text-gray-600')

                                    # File path (truncated if too long)
                                    display_path = filename
                                    if len(display_path) > 60:
                                        display_path = '...' + display_path[-57:]
                                    ui.label(f'File "{display_path}"').classes('text-xs text-gray-500 font-mono')

                                    # Source line
                                    if source_line.strip():
                                        with ui.row().classes('items-start gap-2 mt-1 bg-gray-100 rounded p-2'):
                                            ui.label(f"line {line_number}:").classes('text-xs text-blue-600 font-mono')
                                            ui.label(source_line.strip()).classes('text-xs font-mono')

    return parent_container