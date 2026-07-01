"""Builtin Library — framework-owned primitive types, vectors, color, and their
basic adapters. Loaded at Priority 1 before any entry-point plugin so that
``builtin:type:*`` keys resolve when graphs and plugins reference them.
"""

from pathlib import Path

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


@library(
    label="Builtin",
    id="builtin",
    version="0.0.0",
    description="Framework-owned primitive types and adapters",
    url="https://github.com/going-haywire/haywire",
    help_url="https://github.com/going-haywire/haywire",
    author="maybites",
    author_url="https://maybites.ch",
    dependencies=[],
    tags=["builtin", "types", "adapters"],
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

    def validate(self) -> bool:
        return True
