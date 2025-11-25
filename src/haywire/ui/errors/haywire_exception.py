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
            ui.label(f"{error.category}").classes('text-xl font-bold text-gray-800')

        # Main error info card
        with ui.card().classes('w-full bg-white'):
            with ui.column().classes('gap-2'):
                if error.message:
                    _create_detail_row('Message', error.message, 'build')

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
                            
                            # Show the actual error message right above the code
                            if error.original_exception:
                                exc_type_name = type(error.original_exception).__name__
                                exc_message = str(error.original_exception)
                                with ui.card().classes('w-full bg-red-100 border-l-4 border-red-500 mb-2'):
                                    with ui.row().classes('items-start gap-2 p-2'):
                                        ui.icon('error', color='red').classes('text-lg')
                                        with ui.column().classes('gap-1'):
                                            ui.label(exc_type_name).classes('font-bold text-red-800')
                                            ui.label(exc_message).classes('text-sm text-red-700')


                            # Source code with context using ui.code() in two columns
                            if error.source_context:
                                with ui.column().classes('w-full mt-2'):
                                    ui.label('Source Code:').classes('font-bold text-sm text-gray-600 mb-1')

                                    # Build line numbers and code content
                                    line_numbers = []
                                    code_lines = []
                                    
                                    for line_num, line_content in error.source_context:
                                        is_error_line = (line_num == error.line_number)
                                        
                                        # Add marker for error line
                                        if is_error_line:
                                            line_numbers.append(f"→{line_num:3d}")
                                        else:
                                            line_numbers.append(f" {line_num:3d}")
                                        
                                        # Keep ABSOLUTE indentation - don't strip anything
                                        code_lines.append(line_content)

                                    # Create line numbers string
                                    line_numbers_str = '\n'.join(line_numbers)
                                    
                                    # Create code string with absolute indentation preserved
                                    code_str = '\n'.join(code_lines)

                                    # Two-column layout with ui.code() - force them to stay together
                                    # Add overflow container to prevent escaping the dialog
                                    with ui.row().classes('w-full gap-0 items-stretch flex-nowrap overflow-x-auto').style(
                                        'max-width: 100%;'
                                    ):
                                        # Line numbers column
                                        ui.code(line_numbers_str).classes('flex-shrink-0').style(
                                            'background: #1e293b; '
                                            'color: #94a3b8; '
                                            'padding-right: 0.5rem; '
                                            'padding-left: 0.5rem; '
                                            'border-radius: 0.375rem 0 0 0.375rem; '
                                            'margin: 0; '
                                            'white-space: pre; '
                                            'overflow: visible;'
                                        )
                                        
                                        # Code column with syntax highlighting - absolute indentation preserved
                                        ui.code(code_str).classes('flex-grow').style(
                                            'border-radius: 0 0.375rem 0.375rem 0; '
                                            'margin: 0 0 0 -4px; '
                                            'white-space: pre; '
                                            'padding-left: 0.5rem; '
                                            'overflow-x: visible;'
                                        )
                                    
                                    # Add a visual indicator below showing which line has the error
                                    if error.line_number:
                                        with ui.row().classes('items-center gap-2 mt-2 p-2 bg-red-50 rounded border-l-4 border-red-500'):
                                            ui.icon('error', color='red').classes('text-sm')
                                            ui.label(f'Error on line {error.line_number}').classes('text-sm text-red-700 font-semibold')

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