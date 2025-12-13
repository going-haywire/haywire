#!/usr/bin/env python3
"""
Test script to verify library discovery system

Tests all loading priorities:
1. Core libraries
2. Regular pip installs
3. Editable pip installs  
4. Manual folder paths
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

def test_library_discovery():
    """Test the library discovery system"""
    print("=" * 70)
    print("Testing Haywire Library Discovery System")
    print("=" * 70)
    
    from haywire.core.di.config import create_library_system_service
    
    # Create library system with default configuration
    print("\n🔧 Creating library system service...")
    service = create_library_system_service(
        project_root=str(project_root),
        enable_file_watching=True
    )
    
    # Get library registry
    library_registry = service.get_library_registry()
    
    print("\n📊 Library Discovery Results:")
    print("-" * 70)
    
    # List all loaded libraries
    loaded_libraries = library_registry.list_names()
    
    if not loaded_libraries:
        print("⚠️  No libraries loaded!")
        return False
    
    print(f"\n✅ Loaded {len(loaded_libraries)} libraries:\n")
    
    for lib_id in loaded_libraries:
        identity = library_registry.get_library_identity(lib_id)
        source = library_registry.get_library_source(lib_id)
        enabled = library_registry.is_library_enabled(lib_id)
        
        status = "✓" if enabled else "✗"
        print(f"  {status} {identity.label}")
        print(f"      ID: {lib_id}")
        print(f"      Version: {identity.version}")
        print(f"      Source: {source}")
        print(f"      Dependencies: {identity.dependencies}")
        print(f"      Enabled: {enabled}")
        print()
    
    print("-" * 70)
    
    # Test entry point discovery directly
    print("\n🔍 Testing Entry Point Discovery:")
    print("-" * 70)
    
    from haywire.core.library.discovery import LibraryDiscovery
    
    discovered = LibraryDiscovery.discover_installed_libraries()
    
    if discovered:
        print(f"\n✅ Found {len(discovered)} libraries via entry points:\n")
        
        for lib_info in discovered:
            print(f"  • {lib_info.identity.label} ({lib_info.identity.id})")
            print(f"      Type: {lib_info.install_type.value}")
            print(f"      Path: {lib_info.library_path}")
            if lib_info.entry_point_name:
                print(f"      Entry Point: {lib_info.entry_point_name}")
            print()
    else:
        print("ℹ️  No libraries found via entry points")
        print("   (This is normal if libraries aren't pip installed)")
    
    print("-" * 70)
    
    # Print registry status
    print("\n📋 Registry Status:")
    print("-" * 70)
    service.print_registry_status()
    
    return True


def check_example_library():
    """Check if example library is installable"""
    example_path = project_root / 'libraries' / 'haybale-example'
    pyproject_path = example_path / 'pyproject.toml'
    
    print("\n" + "=" * 70)
    print("Checking Example Library")
    print("=" * 70)
    
    if not pyproject_path.exists():
        print("❌ Example library pyproject.toml not found!")
        return False
    
    print(f"✅ Found pyproject.toml at: {pyproject_path}")
    
    # Check if it's installed
    try:
        import importlib.metadata
        version = importlib.metadata.version('haybale-example')
        print(f"✅ Example library is installed (version {version})")
        
        # Check if editable
        import subprocess
        result = subprocess.run(
            ['uv', 'pip', 'list', '--editable'],
            capture_output=True,
            text=True
        )
        
        if 'haybale-example' in result.stdout:
            print("✅ Installed as editable (hot-reload enabled)")
        else:
            print("ℹ️  Installed as regular package (hot-reload disabled)")
            
    except importlib.metadata.PackageNotFoundError:
        print("ℹ️  Example library not installed as pip package")
        print("\n   To install in editable mode:")
        print(f"   cd {example_path}")
        print("   uv pip install -e .")
    
    return True


if __name__ == '__main__':
    success = test_library_discovery()
    check_example_library()
    
    print("\n" + "=" * 70)
    if success:
        print("✅ Library discovery system test completed successfully!")
    else:
        print("❌ Library discovery system test failed!")
    print("=" * 70 + "\n")
    
    sys.exit(0 if success else 1)
