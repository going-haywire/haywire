"""
Base widget classes for the Haywire widget system
"""

import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from nicegui import ui

from haywire.core.data.fields import DataField
from haywire.core.errors.haywire_exception import HaywireException
from haywire.core.ui.base_widget import BaseWidget
from haywire.core.types.ports import DataPort
from haywire.core.ui.base_widget import widget

@widget(
    _is_error=True, 
    description="Widget displayed when no appropriate widget is found")
class ErrorWidget(BaseWidget):
    """Widget displayed when no appropriate widget is found"""
    
    def on_value_change(self, value: float):  
        """Update the number input's value"""  
        pass


    def create_element(self) -> Any:
        """Create an error display widget"""
        
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
                    ui.icon('error', color='red').classes('text-2xl')
                    
                    # Error message and button
                    with ui.column().classes('flex-grow gap-1'):
                        ui.label(f"{error.category}").classes('text-red-700 font-bold text-sm')
                        ui.label(error.message).classes('text-gray-800 text-sm')
                        
                        with ui.row().classes('gap-2 mt-2'):
                            detail_button = ui.button('Show Details', icon='expand_more').classes('bg-red-600 text-white')
                            
            # Detailed error dialog - hidden by default
            with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl bg-gray-50'):
                with ui.column().classes('w-full gap-4 p-4'):
                    # Header
                    with ui.row().classes('items-center justify-between w-full border-b pb-3'):
                        with ui.row().classes('items-center gap-2'):
                            ui.icon('error', color='red').classes('text-3xl')
                            ui.label(f"{error.category}: {error.message}").classes('text-xl font-bold text-gray-800')
                        ui.button(icon='close', on_click=dialog.close).props('flat round')
                    
                    # Main error info
                    with ui.card().classes('w-full bg-white'):
                        with ui.column().classes('gap-2'):
                            if error.operation:
                                self._create_detail_row('Operation', error.operation, 'build')
                                                        
                            if error.suggestions:
                                with ui.column().classes('gap-1 pl-8 pt-2'):
                                    ui.label('Suggestions:').classes('font-bold text-sm text-blue-700')
                                    for suggestion in error.suggestions:
                                        with ui.row().classes('items-start gap-2'):
                                            ui.icon('lightbulb', color='orange').classes('text-sm')
                                            ui.label(suggestion).classes('text-sm')
                    
                    # Library and context info
                    if error.library_identity or error.module_name:
                        with ui.card().classes('w-full bg-white'):
                            with ui.column().classes('gap-2'):
                                ui.label('Context Information').classes('font-bold text-gray-700')
                                
                                if error.library_identity:
                                    self._create_detail_row('Library', error.library_identity.label, 'folder')
                                    if error.library_identity.folder_path:
                                        self._create_detail_row('Path', error.library_identity.folder_path, 'folder_open', monospace=True)
                                
                                if error.registry_key:
                                    self._create_detail_row('Registry', error.registry_key, 'key')
                                                                
                                if error.module_name:
                                    self._create_detail_row('Module', error.module_name, 'article')
                    
                    # Source code section
                    if error.filename:
                        with ui.card().classes('w-full bg-white'):
                            with ui.column().classes('gap-2'):
                                ui.label('Source Location').classes('font-bold text-gray-700')
                                
                                # File path
                                file_display = error.filename
                                if error.library_identity and error.library_identity.folder_path:
                                    rel_path = error.filename[len(error.library_identity.folder_path):]
                                    if rel_path:
                                        file_display = f"...{rel_path}"
                                
                                self._create_detail_row('File', file_display, 'description', monospace=True)
                                
                                # Source code with context
                                if error.source_context:
                                    with ui.column().classes('w-full mt-2'):
                                        ui.label('Source Code:').classes('font-bold text-sm text-gray-600')
                                        
                                        # Use context_info if available, otherwise fall back
                                        context_to_use = error.source_context
                                        
                                        with ui.column().classes('w-full bg-gray-900 rounded p-3 font-mono text-sm overflow-x-auto'):
                                            for line_num, line_content in context_to_use:
                                                is_error_line = (line_num == error.line_number)
                                                
                                                with ui.row().classes('gap-2 items-start w-full ' + 
                                                    ('bg-red-900 -mx-3 px-3 py-1' if is_error_line else '')):
                                                    # Line number
                                                    ui.label(f"{line_num:3d}").classes(
                                                        'text-gray-500 select-none ' + 
                                                        ('text-red-300 font-bold' if is_error_line else '')
                                                    )
                                                    # Line content with error marker
                                                    if is_error_line:
                                                        ui.label('»').classes('text-red-400 font-bold')
                                                    ui.label(line_content).classes(
                                                        'text-gray-300 flex-grow whitespace-pre ' +
                                                        ('text-red-200 font-bold' if is_error_line else '')
                                                    )
                    
                    # Traceback section
                    if error.traceback_frames:
                        with ui.card().classes('w-full bg-white'):
                            with ui.column().classes('gap-2'):
                                ui.label('Traceback').classes('font-bold text-gray-700')
                                
                                with ui.column().classes('w-full gap-3 pl-4'):
                                    for frame in error.traceback_frames:
                                        filename = frame['file']
                                        line_number = frame['line']
                                        function_name = frame['function']
                                        source_line = frame['code']
                                        
                                        base_filename = os.path.basename(filename)
                                        
                                        with ui.column().classes('gap-1 border-l-2 border-blue-300 pl-3'):
                                            # Location
                                            with ui.row().classes('items-center gap-2'):
                                                ui.icon('arrow_right', color='blue').classes('text-sm')
                                                ui.label(f"{base_filename}").classes('font-bold text-sm')
                                                ui.label(f"in {function_name}").classes('text-sm text-gray-600')
                                            
                                            # File path
                                            ui.label(f'File "{filename}"').classes('text-xs text-gray-500 font-mono')
                                            
                                            # Source line
                                            with ui.row().classes('items-start gap-2 mt-1 bg-gray-100 rounded p-2'):
                                                ui.label(f"line {line_number}:").classes('text-xs text-blue-600 font-mono')
                                                ui.label(source_line.strip()).classes('text-xs font-mono')
                    
                    # Footer with close button
                    with ui.row().classes('justify-end w-full pt-3 border-t'):
                        ui.button('Close', icon='close', on_click=dialog.close).classes('bg-gray-600 text-white')
            
            # Connect button to dialog
            detail_button.on_click(dialog.open)
                                   
        return container
    
    def _create_detail_row(self, label: str, value: str, icon: str, multiline: bool = False, monospace: bool = False):
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