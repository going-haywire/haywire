"""
Demonstration of the Haywire Library System

This script shows how to:
1. Discover and load libraries from multiple locations
2. Use the widget registry with fallback strategies
3. Use the adapter registry for type conversion validation
4. Load nodes from different libraries
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

from haywire.core.registry.registry import LibraryRegistry, WidgetRegistry, AdapterRegistry
from haywire.core.registry.discovery import LibraryDiscovery
from haywire.core.data.enums import DataType, DataCategory
from haywire.core.data.fields import SingleField
from haywire.core.registry.node_system import NodeRegistry


def main():
    """Demonstrate the library system"""
    print("=== Haywire Library System Demo ===\n")
    

    logger.setLevel(logging.DEBUG)

    # 1. Create registries
    print("1. Creating registries...")
    library_registry = LibraryRegistry()
    widget_registry = WidgetRegistry()
    adapter_registry = AdapterRegistry()
    node_registry = NodeRegistry()
    
    # 2. Set up library discovery
    print("2. Setting up library discovery...")
    discovery = LibraryDiscovery()
    
    # Add library search paths
    core_library_path = os.path.join(project_root, 'src', 'haywire', 'libraries')
    test_library_path = os.path.join(project_root, 'libraries')
    
    discovery.add_library_path(core_library_path)
    discovery.add_library_path(test_library_path)
    
    # 3. Discover and load libraries
    print("3. Discovering libraries...")
    discovered = discovery.discover_libraries()
    
    for name, info in discovered.items():
        status = "✓ Valid" if info['valid'] else "✗ Invalid"
        print(f"   {name}: {status} at {info['path']}")
        if not info['valid']:
            print(f"      Missing: {info['missing_dirs']}")
    
    print("\n4. Loading libraries...")
    loaded = discovery.load_libraries(library_registry, widget_registry, adapter_registry, node_registry)
    
    for lib_name in loaded:
        metadata = library_registry.get_library_metadata(lib_name)
        print(f"   ✓ Loaded: {lib_name} v{metadata.version}")
    
    # 4. Demonstrate widget registry
    print("\n5. Testing widget registry...")
    
    # Test exact widget lookup
    test_field = SingleField('test', DataType.FLOAT, DataCategory.SCALAR, 25.5, False)
    
    print("   Widget lookups:")
    widgets_to_test = ['slider', 'knob', 'temperature', 'nonexistent']
    
    for widget_name in widgets_to_test:
        try:
            widget_class = widget_registry.get_widget_class(widget_name, test_field)
            print(f"   - '{widget_name}' → {widget_class.__name__}")
        except Exception as e:
            print(f"   - '{widget_name}' → Error: {e}")
    
    # Test default widget fallback
    print("\n   Default widget fallbacks:")
    data_types = [DataType.INT, DataType.FLOAT, DataType.STRING, DataType.BOOL]
    
    for data_type in data_types:
        test_field = SingleField('test', data_type, DataCategory.SCALAR, None, False)
        widget_class = widget_registry.get_widget_class(None, test_field)
        print(f"   - {data_type.value} → {widget_class.__name__}")
    
    # 5. Demonstrate adapter registry
    print("\n6. Testing adapter registry...")
    
    conversions_to_test = [
        (DataType.INT, DataType.FLOAT),
        (DataType.STRING, DataType.INT),
        (DataType.FLOAT, DataType.STRING),
        (DataType.BOOL, DataType.INT),  # This should fail
    ]
    
    print("   Type conversion availability:")
    for source, target in conversions_to_test:
        has_adapter = adapter_registry.has_adapter(source, target)
        status = "✓" if has_adapter else "✗"
        print(f"   {status} {source.value} → {target.value}")
    
    # Test connection validation
    print("\n   Connection validation:")
    source_field = SingleField('source', DataType.STRING, DataCategory.SCALAR, "123", False)
    target_field = SingleField('target', DataType.INT, DataCategory.SCALAR, 0, False)
    
    can_connect = adapter_registry.can_connect(source_field, target_field)
    print(f"   STRING → INT connection: {'✓ Allowed' if can_connect else '✗ Blocked'}")
    
    # 6. Show loaded nodes
    print("\n7. Loaded nodes:")
    for lib_name in loaded:
        print(f"   From {lib_name} library:")
        # This would show nodes if we had access to the node registry contents
        if lib_name == 'core':
            print("     - ConstantNode")
            print("     - DisplayNode")
        elif lib_name == 'example':
            print("     - TemperatureConverterNode")
    
    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    main()
