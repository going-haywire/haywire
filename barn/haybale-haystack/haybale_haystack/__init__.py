"""Haybale-Haystack: file-centric multi-graph manager.

Provides:
  - HaystackState (AppState): in-memory registry of open graphs.
  - HaystackSettings (LibrarySettings): per-workspace persistence of
    last_haystack_name and new_counter.
  - persistence module: free functions for per-haystack TOML I/O.
  - GraphEditor and HaystackEditor: UI surfaces.
  - "Open in Haystack" file-context-menu panel.

Intended as ONE possible graph-management library for Haywire. Future
libraries may provide alternative managers; haybale-haystack does not
claim exclusive ownership of GraphEditor.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry

from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry


@library(
    label="Haystack",
    id="haystack",
    version="0.1.0",
    description="File-centric multi-graph manager",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=["haybale_core", "haybale_studio", "haybale_graph_editor"],
    tags=["graph-management"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Haystack library — file-centric graph management."""

    def register_components(self):
        base_path = Path(__file__).parent

        # Within-library folder ordering no longer matters for the
        # HaystackState rehydrate path: LibraryStateContainer.on_library_enabled
        # is called by LibraryRegistry only AFTER this library's enable()
        # returns, so HaystackSettings (in settings/) is always wired by the
        # time HaystackState.on_enable fires. Keeping settings/ first is just
        # convention.
        self.add_folder_to_registry(
            folder_path=str(base_path / "settings"),
            registry_cls=SettingsRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "state"),
            registry_cls=LibraryStateRegistry,
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
        return True
