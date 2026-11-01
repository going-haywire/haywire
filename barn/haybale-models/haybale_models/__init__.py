"""Haybale-Models: model references, local model store, downloads and needs-list.

Component folders (registered in ``register_components``):
  - ``state``: ``ModelsState`` with the two model volumes.
  - ``settings``, ``types``, ``widgets``, ``nodes``, ``editors``, ``farmhands``, ``panels``.

Never imports ``torch``: variant choice comes from the consuming node's settings.
"""

from pathlib import Path

from haywire.core.farmhand import FarmhandRegistry
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.node.registry import NodeRegistry
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.state import LibraryStateRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.ui.editor.registry import EditorTypeRegistry
from haywire.ui.panel.registry import PanelRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Models library — model references, store and downloads."""

    def register_components(self):
        """Register the component folders with their registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(folder_path=str(base_path / "state"), registry_cls=LibraryStateRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "settings"), registry_cls=SettingsRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "editors"), registry_cls=EditorTypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "farmhands"), registry_cls=FarmhandRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "panels"), registry_cls=PanelRegistry)

    def validate(self) -> bool:
        return True
