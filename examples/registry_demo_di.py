"""
DI-based Registry Demo - Demonstrating dependency injection with the node rendering architecture

This example shows how to use dependency injection for clean instance management:
1. DI container setup with automatic service registration
2. Clean separation of configuration and business logic  
3. Flexible registry access through DI services
4. Testable architecture with easy mocking

Key improvements over manual setup:
- No manual registry creation and wiring
- Automatic singleton management
- Easy configuration and testing
- Clean service boundaries
"""

import logging
import sys
import os
from pathlib import Path

from nicegui import ui

# Add project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Import DI system
from haywire.core.di.config import create_library_system_service

# Import UI components
from haywire.ui.ui_node import UINode


class RegistryDemoApp:
    """
    Main demo application using dependency injection.
    
    This class demonstrates how to use the DI-based architecture for
    clean service access and instance management.
    """
    
    def __init__(self):
        """Initialize the demo app with DI."""
        # Create and initialize the library system service
        self.library_service = create_library_system_service(
            project_root=project_root,
            enable_file_watching=True
        )
        
        # Print registry status
        self.library_service.print_registry_status()
        
        # Store UINode instances
        self.ui_nodes = {}
    
    def create_ui(self):
        """Create the main UI."""
        @ui.page('/')
        def index_page():
            self._create_index_page()
        
        # Run the application
        ui.run(port=8080, show=True, title="DI-based Renderer Registry Demo", reload=False)
    
    def _create_index_page(self):
        """Create the main page content."""
        ui.label('DI-based Renderer Registry Demo').classes('text-h4 mb-4')
        
        ui.label('This demo shows the DI-based registry system:').classes('text-lg mb-2')
        ui.html('''
        <ul class="list-disc ml-6 mb-4">
            <li><strong>Dependency Injection</strong> - Clean service management with automatic wiring</li>
            <li><strong>LibrarySystemService</strong> - High-level service for registry access</li>
            <li><strong>Singleton Management</strong> - Automatic instance lifecycle management</li>
            <li><strong>Configuration Separation</strong> - Clean separation of setup and business logic</li>
        </ul>
        ''')

        with ui.row().classes('w-full gap-4'):
            # Column 1: Standard Node (Default Renderer)
            with ui.column().classes('flex-1') as col1:
                self._create_standard_node_demo(col1)

            # Column 2: Math Node (Custom Renderer)
            with ui.column().classes('flex-1') as col2:
                self._create_math_node_demo(col2)

        # System Information
        self._create_system_info()
    
    def _create_standard_node_demo(self, container):
        """Create the standard node demo section."""
        ui.label('Standard Node (Default Renderer)').classes('text-h6 mb-2')
        
        try:
            # Get services through DI
            node_registry = self.library_service.get_node_registry()
            node_render_factory = self.library_service.get_node_render_factory()
            
            # Create node instance
            error, node_class = node_registry.get_node_class("example:Display2")
            node_instance = node_class('unique_id', None, "example:Display2")
            
            # Set library metadata from class default
            if hasattr(node_class, '_default_library_metadata'):
                node_instance.library = node_class._default_library_metadata
            if error:
                node_instance.error_info = error
            if error:
                node_instance.error_info = error

            if node_instance is not None:
                # Create UINode with container-slot approach
                self.ui_nodes['standard'] = UINode(node_instance, node_render_factory, container)
                self.ui_nodes['standard'].render()  # Uses default renderer
            
                # Controls
                self._create_standard_controls()
        
        except Exception as e:
            ui.notify(f'Error creating standard node: {str(e)}', type='negative')
    
    def _create_standard_controls(self):
        """Create controls for the standard node."""
        with ui.card().classes('mt-4 p-4'):
            ui.label('Controls').classes('font-bold mb-2')
            
            async def rerender_standard():
                self.ui_nodes['standard'].rerender()
                ui.notify('Standard node re-rendered')
            
            async def update_standard():
                success = self.ui_nodes['standard'].update_element_value('input', 15.0)
                ui.notify(f'Update: {"Success" if success else "Failed"}')
            
            async def print_registry():
                self.library_service.print_registry_status()

            ui.button('Re-render', on_click=rerender_standard)
            ui.button('Set Input to 15.0', on_click=update_standard)
            ui.button('Print Registry Status', on_click=print_registry)
    
    def _create_math_node_demo(self, container):
        """Create the math node demo section."""
        ui.label('Math Node (Custom Renderer)').classes('text-h6 mb-2')

        try:
            # Get services through DI
            node_registry = self.library_service.get_node_registry()
            node_render_factory = self.library_service.get_node_render_factory()
            
            # Create node instance
            error, node_class = node_registry.get_node_class("haywire.core:test.node.one")
            node_instance = node_class('unique_id', None, "haywire.core:test.node.one")
            
            # Set library metadata from class default
            if hasattr(node_class, '_default_library_metadata'):
                node_instance.library = node_class._default_library_metadata
            if error:
                node_instance.error_info = error
            if error:
                node_instance.error_info = error

            if node_instance is not None:
                # Create UINode with custom renderer
                self.ui_nodes['math'] = UINode(node_instance, node_render_factory, container)
                self.ui_nodes['math'].render()  # Uses custom math renderer
            
                # Controls
                self._create_math_controls()
        
        except Exception as e:
            ui.notify(f'Error creating math node: {str(e)}', type='negative')
    
    def _create_math_controls(self):
        """Create controls for the math node."""
        with ui.card().classes('mt-4 p-4'):
            ui.label('Controls').classes('font-bold mb-2')
            
            async def rerender_nodes_default():
                self.ui_nodes['math'].rerender()
                ui.notify('Math node re-rendered with its custom renderer')
            
            async def rerender_custom():
                self.ui_nodes['math'].rerender('example:example.node.renderer')
                ui.notify('Math node re-rendered with example:example.node.renderer')

            async def rerender_default():
                self.ui_nodes['math'].rerender('haywire.core:default.node.renderer')
                ui.notify('Math node re-rendered with haywire.core:default.node.renderer')
            
            async def test_error_renderer():
                self.ui_nodes['math'].rerender('nonexistent')
                ui.notify('Math node rendered with error renderer (fallback)')
            
            ui.button('Render nodes own renderer', on_click=rerender_nodes_default)
            ui.button('Render with custom renderer', on_click=rerender_custom)
            ui.button('Render with core default', on_click=rerender_default)
            ui.button('Test Error Fallback', on_click=test_error_renderer)
    
    def _create_system_info(self):
        """Create the system information section."""
        with ui.expansion('System Information', icon='info').classes('w-full mt-6'):
            # Get renderer registry through DI
            renderer_registry = self.library_service.get_renderer_registry()
            
            # Dynamically get all registered renderers
            registered_renderers = renderer_registry.list_names()
            renderer_list_html = ""
            
            # Add special renderers (default and error)
            default_renderer = renderer_registry.get_default_renderer()
            if default_renderer:
                renderer_list_html += f'<li><strong>default</strong>: {default_renderer.__name__}</li>'
            error_renderer = renderer_registry.get_error_renderer()
            if error_renderer:
                renderer_list_html += f'<li><strong>error</strong>: {error_renderer.__name__}</li>'
            
            # Add all explicitly registered renderers
            for renderer_name in registered_renderers:
                renderer_class = renderer_registry.get(renderer_name)
                if renderer_class:
                    renderer_list_html += f'<li><strong>{renderer_name}</strong>: {renderer_class.__name__}</li>'
            
            _ = ui.html(f'''
            <div class="p-4">
                <h3 class="text-lg font-bold mb-2">DI Architecture Benefits:</h3>
                <ul class="list-disc ml-6 mb-4">
                    <li><strong>Clean Separation:</strong> Configuration isolated from business logic</li>
                    <li><strong>Testable:</strong> Easy mocking and dependency substitution</li>
                    <li><strong>Flexible:</strong> Easy to swap implementations and configurations</li>
                    <li><strong>Maintainable:</strong> No manual wiring or singleton management</li>
                </ul>
                
                <h3 class="text-lg font-bold mb-2">Registered Renderers ({len(registered_renderers) + 2}):</h3>
                <ul class="list-disc ml-6 mb-4">
                    {renderer_list_html}
                </ul>
                
                <h3 class="text-lg font-bold mb-2">Fallback Strategy:</h3>
                <ol class="list-decimal ml-6 mb-4">
                    <li>Use default if no renderer name specified</li>
                    <li>Try exact renderer name lookup</li>
                    <li>Return error renderer if exact renderer doesn't exist</li>
                </ol>
                
                <h3 class="text-lg font-bold mb-2">Service Access Pattern:</h3>
                <ul class="list-disc ml-6">
                    <li>LibrarySystemService provides high-level registry access</li>
                    <li>DI injector manages singleton lifecycle automatically</li>
                    <li>Services obtained through typed getter methods</li>
                    <li>No manual registry creation or wiring required</li>
                </ul>
            </div>
            ''')


def main():
    """Main entry point using DI architecture."""
    # Create and run the DI-based demo app
    app = RegistryDemoApp()
    app.create_ui()


if __name__ in {"__main__", "__mp_main__"}:
    main()
