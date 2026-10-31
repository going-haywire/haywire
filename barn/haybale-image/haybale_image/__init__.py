"""Haybale-Image: image values shared by vision and ML libraries.

Provides:
  - ImageValue (``haybale_image.value``): an image with fixed semantics (RGB order,
    values in [0, 1], layout, source depth) and free storage (dtype, channel order,
    numpy array or torch tensor on any device), reached only through accessors.

Component folders (registered in ``register_components``):
  - ``settings``, ``types``, ``adapters``, ``widgets``, ``nodes``: the IMAGE types,
    adapters, widgets and IO nodes.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.core.settings.registry import SettingsRegistry
from haywire.core.adapter.registry import AdapterRegistry
from haywire.core.node.registry import NodeRegistry
from haywire.core.types.registry import TypeRegistry
from haywire.ui.widget.registry import WidgetRegistry


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Image library — image values, types and IO."""

    def register_components(self):
        """Register the component folders with their registries."""
        base_path = Path(__file__).parent

        self.add_folder_to_registry(folder_path=str(base_path / "settings"), registry_cls=SettingsRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)
        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

    def validate(self) -> bool:
        return True
