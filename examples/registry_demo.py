"""
Renderer Registry Demo - Demonstrating the new node rendering architecture

This example shows how to use the new renderers registry system with:
1. Setting up renderers registry with default and error renderers
2. Creating NodeRenderFactory with both registries
3. Using UINode for reliable rendering and re-rendering
4. Custom renderer registration and usage
"""

import logging
from math import e
from pathlib import Path
import sys
import os

from haywire.core.registry.registry_node import NodeRegistry
from haywire.core.registry.registry_renderer import RendererRegistry
from haywire.core.registry.registry_adapter import AdapterRegistry
from haywire.core.registry.registry_widget import WidgetRegistry

# Add project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from nicegui import ui
from haywire.core.registry.registry_library import LibraryRegistry
from haywire.core.registry.discovery import LibraryDiscovery

# Import the new renderers architecture
from haywire.ui.node_render_factory import NodeRenderFactory
from haywire.ui.ui_node import UINode


def setup_library_system():
    """Set up the complete library system"""
    print("Setting up library system...")
    
    logging.basicConfig(level=logging.INFO)

    # Create registries
    library_registry = LibraryRegistry()
    widget_registry = WidgetRegistry()
    adapter_registry = AdapterRegistry()
    renderer_registry = RendererRegistry()
    node_registry    = NodeRegistry()
    
    # Set up discovery
    discovery = LibraryDiscovery()
    discovery.add_library_path(os.path.join(project_root, 'src', 'haywire', 'libraries'))
    discovery.add_library_path(os.path.join(project_root, 'libraries'))

    discovery.enable_file_watching(debounce_delay=0.5, force=True)  # Enable file watching
    
    # Load libraries
    loaded = discovery.load_libraries(library_registry, widget_registry, adapter_registry, renderer_registry, node_registry)
    
    # 3. Create factory with both registries
    factory = NodeRenderFactory(renderer_registry, widget_registry)

    # Print registered adapters in a beautiful format
    print("\n=== Registered Adapters ===")
    all_adapters = adapter_registry.list_names()
    for adapter_key in all_adapters:
        print(f"🔗 {adapter_key}")

    # Print registered widgets in a beautiful format
    print("\n=== Registered Widgets ===")
    all_widgets = widget_registry.list_names()
    for widget_key in all_widgets:
        print(f"🔧 {widget_key}")

    # Print registered renderers in a beautiful format
    print("\n=== Registered Renderer ===")
    all_renderers = renderer_registry.list_names()
    for renderer_key in all_renderers:
        print(f"🔨 {renderer_key}")        
    
    # Print registered nodes in a beautiful format
    print("\n=== Registered Nodes ===")
    all_nodes = node_registry.list_names()
    for node_key in all_nodes:
        print(f"🛠 {node_key}")
    print(f"Total: {len(all_nodes)} nodes\n")

    return factory, renderer_registry, widget_registry, adapter_registry, node_registry


def main():
    """Main demo application."""

    # Set up the renderers system
    factory, renderers_registry, widget_registry, adapter_registry, node_registry = setup_library_system()

    # Store UINode instances
    ui_nodes = {}
    
    @ui.page('/')
    def index_page():
        ui.label('Renderer Registry Demo - New Node Rendering Architecture').classes('text-h4 mb-4')
        
        ui.label('This demo shows the new renderers registry system:').classes('text-lg mb-2')
        ui.html('''
        <ul class="list-disc ml-6 mb-4">
            <li><strong>Renderer Registry</strong> - Manages NodeRenderer classes with fallback</li>
            <li><strong>NodeRenderFactory</strong> - Caches stateless renderers and creates UINodeCard</li>
            <li><strong>UINode</strong> - Manages UI lifecycle with reliable cleanup</li>
            <li><strong>Container-Slot Approach</strong> - Reliable re-rendering without memory leaks</li>
        </ul>
        ''')

        with ui.row().classes('w-full gap-4'):
            # Column 1: Standard Node (Default Renderer)
            with ui.column().classes('flex-1') as col1:
                ui.label('Standard Node (Default Renderer)').classes('text-h6 mb-2')
                
                try:
                    error, node_class = node_registry.get_node_class("example:Display2")
                    node_instance = node_class('unique_id', None)
                    if error:
                        node_instance.error_info = error

                    if node_instance is not None:
                        # Create UINode with container-slot approach
                        ui_nodes['standard'] = UINode(node_instance, factory, col1)
                        ui_nodes['standard'].render()  # Uses default renderer
                    
                        # Controls
                        with ui.card().classes('mt-4 p-4'):
                            ui.label('Controls').classes('font-bold mb-2')
                            
                            async def rerender_standard():
                                ui_nodes['standard'].rerender()  # Re-render with default
                                ui.notify('Standard node re-rendered')
                            
                            async def update_standard():
                                success = ui_nodes['standard'].update_element_value('input', 15.0)
                                ui.notify(f'Update: {"Success" if success else "Failed"}')
                            
                            async def print_registry():
                                # Print registered adapters in a beautiful format
                                print("\n=== Registered Adapters ===")
                                all_adapters = adapter_registry.list_names()
                                for adapter_key in all_adapters:
                                    print(f"🔗 {adapter_key}")

                                # Print registered widgets in a beautiful format
                                print("\n=== Registered Widgets ===")
                                all_widgets = widget_registry.list_names()
                                for widget_key in all_widgets:
                                    print(f"🔧 {widget_key}")

                                # Print registered renderers in a beautiful format
                                print("\n=== Registered Renderer ===")
                                all_renderers = renderers_registry.list_names()
                                for renderer_key in all_renderers:
                                    print(f"🔨 {renderer_key}")        
                                
                                # Print registered nodes in a beautiful format
                                print("\n=== Registered Nodes ===")
                                all_nodes = node_registry.list_names()
                                for node_key in all_nodes:
                                    print(f"🛠 {node_key}")
                                print(f"Total: {len(all_nodes)} nodes\n")

                            ui.button('Re-render', on_click=rerender_standard)
                            ui.button('Set Input to 15.0', on_click=update_standard)
                            ui.button('Print Registry', on_click=print_registry)

                except Exception as e:
                    ui.notify(f'Error creating node: {str(e)}', type='negative')

            # Column 2: Math Node (Custom Renderer)
            with ui.column().classes('flex-1') as col2:
                ui.label('Math Node (Custom Renderer)').classes('text-h6 mb-2')

                try:
                    error, node_class = node_registry.get_node_class("haywire.core:test.node.one")
                    node_instance = node_class('unique_id', None)
                    if error:
                        node_instance.error_info = error

                    if node_instance is not None:
                        # Create UINode with custom renderer
                        ui_nodes['math'] = UINode(node_instance, factory, col2)
                        ui_nodes['math'].render()  # Uses custom math renderer
                
                    # Controls
                    with ui.card().classes('mt-4 p-4'):
                        ui.label('Controls').classes('font-bold mb-2')
                        
                        async def rerender_nodes_default():
                            ui_nodes['math'].rerender()  # Re-render with default
                            ui.notify('Math node re-rendered with its custom renderer')
                        
                        async def rerender_custom():
                            ui_nodes['math'].rerender('example:example.node.renderer')  # Re-render with custom
                            ui.notify('Math node re-rendered with example:example.node.renderer')

                        async def rerender_default():
                            ui_nodes['math'].rerender('haywire.core:default.node.renderer')  # Re-render with custom
                            ui.notify('Math node re-rendered with haywire.core:default.node.renderer')
                        
                        async def test_error_renderer():
                            ui_nodes['math'].rerender('nonexistent')  # Should use error renderer
                            ui.notify('Math node rendered with error renderer (fallback)')
                        
                        ui.button('Render nodes own renderer', on_click=rerender_nodes_default)
                        ui.button('Render with custom renderer', on_click=rerender_custom)
                        ui.button('Render with core default', on_click=rerender_default)
                        ui.button('Test Error Fallback', on_click=test_error_renderer)
                
                except Exception as e:
                    ui.notify(f'Error: {str(e)}', type='negative')

        # System Information
        with ui.expansion('System Information', icon='info').classes('w-full mt-6'):
            # Dynamically get all registered renderers
            registered_renderers = renderers_registry.list_names()
            renderer_list_html = ""
            
            # Add special renderers (default and error)
            default_renderer = renderers_registry.get_default_renderer()
            if default_renderer:
                renderer_list_html += f'<li><strong>default</strong>: {default_renderer.__name__}</li>'
            error_renderer = renderers_registry.get_error_renderer()
            if error_renderer:
                renderer_list_html += f'<li><strong>error</strong>: {error_renderer.__name__}</li>'
            
            # Add all explicitly registered renderers
            for renderer_name in registered_renderers:
                renderer_class = renderers_registry.get(renderer_name)
                if renderer_class:
                    renderer_list_html += f'<li><strong>{renderer_name}</strong>: {renderer_class.__name__}</li>'
            
            _ = ui.html(f'''
            <div class="p-4">
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
                
                <h3 class="text-lg font-bold mb-2">Architecture Benefits:</h3>
                <ul class="list-disc ml-6">
                    <li>Stateless renderers cached for performance</li>
                    <li>Reliable cleanup via container-slot approach</li>
                    <li>Clean separation: UINode delegates to factory</li>
                    <li>Registry-based extensibility</li>
                </ul>
            </div>
            ''')

    # Run the application
    ui.run(port=8080, show=True, title="Renderer Registry Demo", reload=False)
    # ui.run(port=8080, show=True, title="Renderer Registry Demo", uvicorn_reload_dirs="examples")


if __name__ in {"__main__", "__mp_main__"}:
    main()
