"""
Complete Library System Integration Example

This example demonstrates the full modular library system working together:
1. Library discovery and loading
2. Widget registry with fallbacks
3. Adapter registry for connection validation
4. Updated NiceGUI renderer using the registry system
"""

import logging
import sys
import os
from venv import logger

# Add project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from nicegui import ui
from haywire.core.registry.registry import LibraryRegistry, WidgetRegistry, AdapterRegistry
from haywire.core.registry.discovery import LibraryDiscovery
from haywire.ui.nicegui_renderer import ModularNiceGUINodeRenderer
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.fields import SingleField
from haywire.core.node.node import NodeData, Config, Inlet
from haywire.core.registry.node_system import NodeRegistry


def setup_library_system():
    """Set up the complete library system"""
    print("Setting up library system...")
    
    logger.setLevel(logging.INFO)

    # Create registries
    library_registry = LibraryRegistry()
    widget_registry = WidgetRegistry()
    adapter_registry = AdapterRegistry()
    node_registry = NodeRegistry()
    
    # Set up discovery
    discovery = LibraryDiscovery()
    discovery.add_library_path(os.path.join(project_root, 'src', 'haywire', 'libraries'))
    discovery.add_library_path(os.path.join(project_root, 'libraries'))
    
    # Load libraries
    loaded = discovery.load_libraries(library_registry, widget_registry, adapter_registry, node_registry)
    print(f"Loaded libraries: {loaded}")
    
    return widget_registry, adapter_registry, node_registry


def create_demo_node():
    """Create a demo node with various widget types"""
    node = NodeData()
    node.id = "demo_node"
    node.name = "Demo Node"
    
    # Add configs with different widget types
    node.configs = {
        'float_slider': Config(
            'float_slider',  # element_id as first positional parameter
            label='Float Slider',
            data=SingleField('float_val', DataType.FLOAT, DataCategory.SCALAR, 50.0, False),
            widget='slider',
            ui={'properties': {'min': 0, 'max': 100, 'step': 1}}
        ),
        'temperature': Config(
            'temperature',  # element_id as first positional parameter
            label='Temperature',
            data=SingleField('temp_val', DataType.FLOAT, DataCategory.SCALAR, 25.0, False),
            widget='temperature',
            ui={'properties': {'unit': 'celsius'}}
        ),
        'bool_switch': Config(
            'bool_switch',  # element_id as first positional parameter
            label='Boolean Switch',
            data=SingleField('bool_val', DataType.BOOL, DataCategory.SCALAR, True, False),
            widget='switch',
            ui={'properties': {'text': 'Enable Feature'}}
        ),
        'string_input': Config(
            'string_input',  # element_id as first positional parameter
            label='Text Input',
            data=SingleField('str_val', DataType.STRING, DataCategory.SCALAR, 'Hello', False),
            widget='input',
            ui={'properties': {'placeholder': 'Enter text...'}}
        ),
        'nonexistent_widget': Config(
            'nonexistent',  # element_id as first positional parameter
            label='Missing Widget',
            data=SingleField('missing_val', DataType.INT, DataCategory.SCALAR, 42, False),
            widget='nonexistent_widget_type',
            ui={'properties': {}}
        )
    }
    
    # Add some inlets and outlets for display
    node.inlets = {
        'input1': Inlet('input1', 'Input 1', None, data=SingleField('in1', DataType.FLOAT, DataCategory.SCALAR, 0.0, False))
    }
    node.outlets = {}
    
    return node


def demonstrate_adapter_system(adapter_registry):
    """Demonstrate the adapter system for connection validation"""
    print("\n=== Adapter System Demo ===")
    
    # Test various connection scenarios
    test_connections = [
        (DataType.STRING, DataType.INT, "123"),      # Should work with adapter
        (DataType.FLOAT, DataType.INT, 42.7),       # Should work with adapter
        (DataType.BOOL, DataType.STRING, True),     # Should work with adapter
        (DataType.DICT, DataType.INT, {}),          # Should fail - no adapter
    ]
    
    for source_type, target_type, test_value in test_connections:
        source_field = SingleField('source', source_type, DataCategory.SCALAR, test_value, False)
        target_field = SingleField('target', target_type, DataCategory.SCALAR, None, False)
        
        can_connect = adapter_registry.can_connect(source_field, target_field)
        status = "✓ Allowed" if can_connect else "✗ Blocked"
        print(f"{source_type.value} → {target_type.value}: {status}")
        
        if can_connect and source_type != target_type:
            adapter = adapter_registry.get_adapter(source_type, target_type)
            if adapter:
                try:
                    adapter_instance = adapter()
                    converted = adapter_instance.convert(test_value)
                    print(f"  Conversion: {test_value} → {converted}")
                except Exception as e:
                    print(f"  Conversion failed: {e}")


@ui.page('/')
def main_page():
    """Main page demonstrating the library system"""
    ui.label('Haywire Modular Library System Demo').classes('text-h4 mb-4')
    
    # Set up library system
    widget_registry, adapter_registry, node_registry = setup_library_system()
    
    # Demonstrate adapter system in console
    demonstrate_adapter_system(adapter_registry)
    
    # Create demo node
    demo_node = create_demo_node()
    
    with ui.row().classes('w-full gap-4'):
        # Left column: Original node rendering info
        with ui.column().classes('w-1/2'):
            ui.label('Node Information').classes('text-h6 mb-2')
            ui.label(f'Node ID: {demo_node.id}')
            ui.label(f'Configs: {len(demo_node.configs)}')
            ui.label(f'Inlets: {len(demo_node.inlets)}')
            ui.label(f'Outlets: {len(demo_node.outlets)}')
            
            ui.separator()
            
            ui.label('Widget Registry Status').classes('text-h6 mb-2 mt-4')
            ui.label(f'Registered widgets: {len(widget_registry.list_names())}')
            for widget_name in widget_registry.list_names():
                ui.label(f'• {widget_name}').classes('text-sm ml-4')
            
            ui.separator()
            
            ui.label('Adapter Registry Status').classes('text-h6 mb-2 mt-4')
            conversions = adapter_registry.list_conversions()
            ui.label(f'Available conversions: {len(conversions)}')
            for source, target in conversions:
                ui.label(f'• {source.value} → {target.value}').classes('text-sm ml-4')
        
        # Right column: Rendered node using new system
        with ui.column().classes('w-1/2'):
            ui.label('Rendered Node (Registry-Based)').classes('text-h6 mb-2')
            
            # Create renderer with widget registry
            renderer = ModularNiceGUINodeRenderer(demo_node, widget_registry)
            
            # Render the node
            renderer.render_node("Demo Node with Library System")
            
            ui.separator()
            
            # Show widget instances created
            ui.label('Widget Instances Created').classes('text-h6 mb-2 mt-4')
            for element_id, widget_instance in renderer.widget_instances.items():
                widget_type = widget_instance.__class__.__name__
                ui.label(f'• {element_id}: {widget_type}').classes('text-sm')


def main():
    """Run the demo"""
    print("Starting Haywire Library System Demo...")
    ui.run(title='Haywire Library System Demo', port=8080)


if __name__ in {"__main__", "__mp_main__"}:
    main()
