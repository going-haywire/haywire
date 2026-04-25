"""
Haywire Core Library

Contains fundamental nodes, widgets, adapters, and data definitions
that form the foundation of the Haywire system.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.widget.registry import WidgetRegistry
from haywire.ui.skin.registry import SkinRegistry


@library(
    label="Haywire Core",
    id="core",
    version="1.0.0",
    description="Core Haywire library with fundamental components",
    url="https://github.com/maybites/haywire",
    help_url="https://github.com/maybites/haywire",
    author="maybites",
    author_url="https://maybites.ch",
    dependencies=[],
    tags=["core", "types", "widgets", "skins"],
    file_watcher=False,
)
class Library(BaseLibrary):
    """Core Haywire library implementation"""

    def register_components(self):
        """Register all core components with the global registries"""

        """Register nodes and custom types"""
        base_path = Path(__file__).parent

        # Register settings
        self.add_folder_to_registry(folder_path=str(base_path / "settings"), registry_cls=SettingsRegistry)

        # Register themes (workbench and node themes)
        self.add_folder_to_registry(folder_path=str(base_path / "themes"), registry_cls=ThemeRegistry)

        # Register types (both variants and custom types)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        # Register adapters (now includes data types)
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        # Register widgets
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        # Register skins (node skins)
        self.add_folder_to_registry(folder_path=str(base_path / "skins"), registry_cls=SkinRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "panels"), registry_cls=PanelRegistry)

        # Register nodes
        self.add_folder_to_registry(folder_path=str(base_path / "editors"), registry_cls=EditorTypeRegistry)

    def validate(self) -> bool:
        """Validate that the core library is properly structured"""
        # Core library is always valid since it's part of the system
        return True
