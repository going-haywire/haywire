"""haybale-graph-editor: graph editor library for Haywire.

Provides the GraphContainer protocol, GraphAppState registry, and
GraphEditor surface. Decoupled from any specific graph source — source
libraries register their containers, this library renders them.
"""

from importlib.metadata import version as _pkg_version
from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.state import LibraryStateRegistry
from haywire.ui.editor.registry import EditorTypeRegistry

# Public API re-exports
from haybale_graph_editor.protocols import GraphContainer
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haywire.ui.panel.registry import PanelRegistry

__all__ = ["GraphContainer", "GraphAppState", "Library"]


@library(
    label="Graph Editor",
    id="graph_editor",
    version=_pkg_version("haybale-graph-editor"),
    description="Visual graph editor library — host-agnostic",
    url="",
    help_url="",
    author="",
    author_url="",
    dependencies=[],
    tags=["graph-editor"],
    file_watcher=True,
)
class Library(BaseLibrary):
    """Graph Editor library."""

    def register_components(self):
        base_path = Path(__file__).parent

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
