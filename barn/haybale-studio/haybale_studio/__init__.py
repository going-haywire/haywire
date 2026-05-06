"""
Local haybale library for the studio project.

Add your custom components in the corresponding folders:
- nodes/      — node definitions
- types/      — custom data types
- widgets/    — UI widgets for data types
- skins/      — custom node skins
- adapters/   — type-to-type conversion adapters
- settings/   — library settings definitions
- themes/     — workbench and node themes
- panels/     — custom UI panels
- editors/    — custom UI editors
- state/      — per-session library state (SessionState subclasses)
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.core.types.registry import TypeRegistry

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.skin.registry import SkinRegistry
from haywire.ui.themes.registry import ThemeRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    label="Haywire Studio",
    id="studio",
    version="0.1.0",
    description="Required library for haywire studio",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=["haybale_core"],
    tags=["experimental", "project-local"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Local project library — add your components in the subfolders."""

    def register_components(self):
        """Register all components with the global registries."""
        base_path = Path(__file__).parent

        # state/ MUST be scanned first. Panel and editor modules in later
        # scans transitively import classes from state/ (e.g. EditState).
        # Once a state module is in sys.modules, the state/ scan's
        # force_reload would replace the class object — leaving any
        # already-imported references stale. The container would then key
        # on the new class while writers held the old one, causing
        # KeyError on ctx.data[StateClass] lookups. Registering state/
        # first means every later import resolves to the same class
        # the container holds.
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "themes"),
            registry_cls=ThemeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "types"),
            registry_cls=TypeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "adapters"),
            registry_cls=AdapterRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "widgets"),
            registry_cls=WidgetRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "skins"),
            registry_cls=SkinRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "nodes"),
            registry_cls=NodeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "panels"),
            registry_cls=PanelRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        """Validate library structure."""
        return True
