"""
Test Library B for Haywire

Minimal test library to demonstrate multi-library support and for testing purposes.
Contains folders for nodes, widgets, adapters, renderers, and custom types.
"""

from pathlib import Path
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    label="Testing",
    id="testing",
    version="1.0.0",
    description="Test library for test support",
    url="https://github.com/maybites/haywire",
    help_url="https://github.com/maybites/haywire",
    author="Haywire Team",
    author_url="https://github.com/maybites/haywire",
    dependencies=["haybale_core", "haybale_test_a"],
    tags=["testing", "development", "debug"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Test library implementation"""

    def register_components(self):
        """Register all test components with the global registries"""

        """Register nodes and types"""
        base_path = Path(__file__).parent

        # Register types
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        # Register adapters
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        # Register themes
        self.add_folder_to_registry(folder_path=str(base_path / "themes"), registry_cls=ThemeRegistry)

        # Register widgets
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        # Register skins (node skins)
        self.add_folder_to_registry(folder_path=str(base_path / "skins"), registry_cls=SkinRegistry)

        # Register settings
        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

        # Register panels
        self.add_folder_to_registry(folder_path=str(base_path / "panels"), registry_cls=PanelRegistry)

    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True


# Export for entry point discovery
__all__ = ["Library"]
