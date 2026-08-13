"""haybale-graph-editor: graph editor library for Haywire.

Provides the GraphContainer protocol, GraphAppState registry, and
GraphEditor surface. Decoupled from any specific graph source — source
libraries register their containers, this library renders them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.farmhand import FarmhandRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.skin.registry import SkinRegistry

# Public API re-exports
from haybale_graph_editor.protocols import GraphContainer
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haywire.ui.panel.registry import PanelRegistry

__all__ = ["GraphContainer", "GraphAppState", "Library"]


@library(
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

        # Register MCP tools (canonical order: after state — tools reference GraphAppState)
        self.add_folder_to_registry(
            folder_path=str(base_path / "farmhands"),
            registry_cls=FarmhandRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "nodes"),
            registry_cls=NodeRegistry,
        )

        self.add_folder_to_registry(
            folder_path=str(base_path / "skins"),
            registry_cls=SkinRegistry,
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
