"""Haybale-Models: model references, local model store, downloads and needs-list.

Component folders (registered in ``register_components``):
  - ``state``: ``ModelsState`` with the two model volumes.
  - ``settings``, ``types``, ``widgets``, ``nodes``, ``editors``, ``farmhands``, ``panels``.

Never imports ``torch``: variant choice comes from the consuming node's settings.
"""

from pathlib import Path

from haywire.api.workbench import EditorTypeRegistry, FarmhandRegistry, LibraryStateRegistry, PanelRegistry
from haywire.api import BaseLibrary, NodeRegistry, SettingsRegistry, TypeRegistry, WidgetRegistry, library


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Models library — model references, store and downloads."""

    def register_components(self):
        """Register the component folders with their registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(folder_path=str(base_path / "states"), registry_cls=LibraryStateRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "settings"), registry_cls=SettingsRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "editors"), registry_cls=EditorTypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "farmhands"), registry_cls=FarmhandRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "panels"), registry_cls=PanelRegistry)

    def validate(self) -> bool:
        return True
