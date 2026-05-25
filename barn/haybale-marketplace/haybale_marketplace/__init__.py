"""
haybale-marketplace — library installer + browser editors.

Optional plugin. When enabled, registers:
- state/library_manager_state.py — publishes the LibraryManager for editor consumption
- state/library_enable_state.py — runtime user enable/disable toggles (write path)
- state/marketplace_state.py — marketstall orchestration (parse/refresh/etc.)
- editors/* — the library browser, overview, component, marketplace dialog, and component-source editors

If absent, the library browser slot is simply empty; haybale-studio works
unmodified. See ADR-0001.
"""

from importlib.metadata import version as _pkg_version
from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.state import LibraryStateRegistry

from haywire.ui.editor.registry import EditorTypeRegistry


@library(
    label="Library Marketplace",
    id="marketplace",
    version=_pkg_version("haybale-marketplace"),
    description="Library installer + browser editors",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=[],
    tags=["marketplace"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Marketplace library — install/uninstall/enable UI + manager service."""

    def register_components(self):
        base_path = Path(__file__).parent

        # state/ MUST be scanned before editors/. Editor modules transitively
        # import classes from state/ (e.g. LibraryManagerState, MarketplaceState);
        # if a state module isn't in sys.modules yet, the editor's scan would
        # force_reload-replace the class object and leave already-imported
        # references stale. Same reasoning as haybale-studio's __init__.py.
        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "editors"),
            registry_cls=EditorTypeRegistry,
        )

    def validate(self) -> bool:
        return True
