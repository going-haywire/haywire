"""
Test Library for Haywire

Minimal test library to demonstrate multi-library support.
Contains one node, one widget, one adapter, and one data struct.
"""

from __future__ import annotations

from pathlib import Path

from haywire.api import (
    AdapterRegistry,
    BaseLibrary,
    CatalogRegistry,
    MacroRegistry,
    NodeRegistry,
    TypeRegistry,
    WidgetRegistry,
    library,
)


@library(
    file_watcher=False,
)
class Library(BaseLibrary):
    """Example library implementation"""

    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and types"""
        base_path = Path(__file__).parent

        # Register types (both variants and custom types)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        # Register adapters
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        # Register widgets
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

        # Register macros (.hwm documents)
        self.add_folder_to_registry(folder_path=str(base_path / "macros"), registry_cls=MacroRegistry)

        # Register the demo model catalog (.json entries)
        self.add_folder_to_registry(folder_path=str(base_path / "catalog"), registry_cls=CatalogRegistry)

    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True


# Export for entry point discovery
__all__ = ["Library"]
