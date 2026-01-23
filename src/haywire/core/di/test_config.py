"""
Test-specific DI configuration for Haywire.

Provides lightweight configurations for different test scenarios.
"""

from typing import Optional, List, TYPE_CHECKING
from injector import Injector

if TYPE_CHECKING:
    from .config import LibrarySystemService


def create_test_injector(
    project_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    enable_file_watching: bool = False,
    undo_config: Optional[object] = None,  # Use object to avoid import
    load_libraries: bool = False
) -> Injector:
    """
    Create a test-specific DI injector with minimal overhead.
    
    Args:
        project_root: Root path (auto-detected if None)
        library_paths: Additional library paths
        enable_file_watching: Disable for faster tests
        undo_config: Optional undo configuration
        load_libraries: Whether to load libraries (slow, integration only)
        
    Returns:
        Configured test injector
    """
    # Import here to avoid circular imports at module level
    from .config import HaywireModule
    
    module = HaywireModule(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        undo_config=undo_config,
        default_theme='default'
    )
    
    return Injector([module])


def create_test_library_system(
    project_root: Optional[str] = None,
    library_paths: Optional[List[str]] = None,
    load_libraries: bool = True,
    enable_file_watching: bool = False
) -> 'LibrarySystemService':
    """
    Create library system for integration tests.
    
    Args:
        project_root: Root path (auto-detected if None)
        library_paths: Additional library paths
        load_libraries: Whether to initialize libraries
        enable_file_watching: Usually False for tests
        
    Returns:
        LibrarySystemService (initialized if load_libraries=True)
    """
    # Import here to avoid circular imports
    from .config import LibrarySystemService
    
    injector = create_test_injector(
        project_root=project_root,
        library_paths=library_paths,
        enable_file_watching=enable_file_watching,
        load_libraries=load_libraries
    )
    
    service = LibrarySystemService(injector)
    
    if load_libraries:
        service.initialize()
    
    return service
