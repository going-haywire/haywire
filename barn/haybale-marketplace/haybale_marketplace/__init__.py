from pathlib import Path

from haywire.core.farmhand import FarmhandRegistry
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Marketplace library — install/uninstall/enable UI
    - publishes the LibraryManager for editor consumption
    - marketstall orchestration (parse/refresh/etc.)
    - library browser, overview, component..
    """

    def register_components(self):
        base_path = Path(__file__).parent

        # states/ MUST be scanned before editors/. Editor modules transitively
        # import classes from states/ (e.g. LibraryManagerState, MarketplaceState);
        # if a state module isn't in sys.modules yet, the editor's scan would
        # force_reload-replace the class object and leave already-imported
        # references stale. Same reasoning as haybale-studio's __init__.py.
        self.add_folder_to_registry(
            folder_path=str(base_path / "states"),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )

        # Register MCP tools (canonical order: after state — tools reference marketplace states)
        self.add_folder_to_registry(
            folder_path=str(base_path / "farmhands"),
            registry_cls=FarmhandRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "panels"),
            registry_cls=PanelRegistry,
        )

    def validate(self) -> bool:
        return True
