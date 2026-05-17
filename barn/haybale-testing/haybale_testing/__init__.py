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
from haywire.core.state import LibraryStateRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.widget.registry import WidgetRegistry


# --8<-- [start:testing_library]
@library(
    label="Testing",
    id="testing",
    version="1.0.0",
    description="Test library for test support",
    url="https://github.com/maybites/haywire",
    help_url="https://github.com/maybites/haywire",
    author="Haywire Team",
    author_url="https://github.com/maybites/haywire",
    dependencies=["haybale_core", "haybale_graph_editor"],
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

        # Register state LAST — deliberately adversarial ordering. Panels
        # registered above eagerly import TestSessionState, so by the time
        # state/ is scanned the module is already in sys.modules. This is
        # the placement that broke pre-fix: BaseRegistry._on_creation used
        # to force-reload the module, producing a second class object and
        # leaving the panel's reference stale. The fix makes class
        # identity stable regardless of scan order. See
        # tests/core/test_libraries/test_registries.py.
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )

    def validate(self) -> bool:
        """Validate that the test library is properly structured"""
        return True


# --8<-- [end:testing_library]


# Export for entry point discovery
__all__ = ["Library"]
