"""
Test Library A for Haywire

Minimal test library to demonstrate multi-library support and for testing purposes.
Contains folders for nodes, widgets, adapters, renderers, and custom types.
"""

from __future__ import annotations

from pathlib import Path

from haywire.api import (
    AdapterRegistry,
    BaseLibrary,
    NodeRegistry,
    SkinRegistry,
    TypeRegistry,
    WidgetRegistry,
    library,
)


@library(
    file_watcher=False,
)
class Library(BaseLibrary):
    """Test A library implementation"""

    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and types"""
        base_path = Path(__file__).parent

        # Register types
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        # Register adapters
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        # Register widgets
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        # Register skins (node skins)
        self.add_folder_to_registry(folder_path=str(base_path / "skins"), registry_cls=SkinRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True


# Export for entry point discovery
__all__ = ["Library"]
