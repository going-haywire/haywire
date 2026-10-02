"""Builtin Library: framework-owned types (primitives, vectors, colour, and the
EXEC and CALLBACK signal types), their basic adapters, and the reroute node and
skin. Loaded at Priority 1 before any entry-point plugin, so that
``haywire-core:type:*``, ``haywire-core:node:*`` and ``haywire-core:skin:*`` keys
resolve when graphs and plugins reference them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


@library(
    file_watcher=False,
)
class Library(BaseLibrary):
    """Framework-internal builtin library."""

    def register_components(self):
        from haywire.core.types.registry import TypeRegistry

        base_path = Path(__file__).parent
        self.add_folder_to_registry(folder_path=str(base_path / "types"), registry_cls=TypeRegistry)

        from haywire.core.adapter.registry import AdapterRegistry

        self.add_folder_to_registry(folder_path=str(base_path / "adapters"), registry_cls=AdapterRegistry)

        from haywire.ui.widget.registry import WidgetRegistry

        self.add_folder_to_registry(folder_path=str(base_path / "widgets"), registry_cls=WidgetRegistry)

        from haywire.core.node.registry import NodeRegistry

        self.add_folder_to_registry(folder_path=str(base_path / "nodes"), registry_cls=NodeRegistry)

        from haywire.ui.skin.registry import SkinRegistry

        self.add_folder_to_registry(folder_path=str(base_path / "skins"), registry_cls=SkinRegistry)

    def validate(self) -> bool:
        return True
