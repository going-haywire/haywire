"""Canonical component-kind maps: kind -> registry, kind -> source folder,
kind -> canon-doc area. Single source shared by the studio farmhands, the
docs generator, and the marketplace drill-down tools."""

from __future__ import annotations


def kind_registry_map() -> dict[str, type]:
    """Registry-key kind segment -> registry class (the ten registries + farmhand)."""
    from haywire.core.adapter.registry import AdapterRegistry
    from haywire.core.farmhand import FarmhandRegistry
    from haywire.core.node.registry import NodeRegistry
    from haywire.core.settings import SettingsRegistry
    from haywire.core.state import LibraryStateRegistry
    from haywire.core.types.registry import TypeRegistry
    from haywire.ui.editor.registry import EditorTypeRegistry
    from haywire.ui.panel.registry import PanelRegistry
    from haywire.ui.skin.registry import SkinRegistry
    from haywire.ui.themes.registry import ThemeRegistry
    from haywire.ui.widget.registry import WidgetRegistry

    return {
        "node": NodeRegistry,
        "type": TypeRegistry,
        "adapter": AdapterRegistry,
        "widget": WidgetRegistry,
        "skin": SkinRegistry,
        "setting": SettingsRegistry,
        "theme": ThemeRegistry,
        "panel": PanelRegistry,
        "editor": EditorTypeRegistry,
        "state": LibraryStateRegistry,
        "farmhand": FarmhandRegistry,
    }


KIND_FOLDERS = {
    "node": "nodes",
    "type": "types",
    "adapter": "adapters",
    "widget": "widgets",
    "skin": "skins",
    "setting": "settings",
    "theme": "themes",
    "panel": "panels",
    "editor": "editors",
    "state": "state",
    "farmhand": "farmhands",
}

_KIND_TO_AREA = {
    "node": "nodes",
    "type": "datatypes",
    "adapter": "adapters",
    "widget": "widgets",
    "skin": "skins",
    "setting": "settings",
    "theme": "themes",
    "panel": "panels",
    "editor": "editors",
    "state": "states",
    "farmhand": "farmhands",
}


def canon_area(kind: str) -> str:
    """The ``docs/components/<area>`` directory name for a component kind."""
    return _KIND_TO_AREA.get(kind, f"{kind}s")
