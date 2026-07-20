"""Shared helpers for baseline tools: pagination, kind maps, target-library resolution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haywire.core.farmhand import FarmhandContext, FarmhandError
from haywire.core.library.install_type import InstallType
from haywire.core.library.registry import LibraryRegistry


def page(items: list, limit: int, offset: int) -> tuple[list, int]:
    return items[offset : offset + limit], len(items)


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


def resolve_component_class(ctx: FarmhandContext, registry_key: str) -> Any:
    parts = registry_key.split(":")
    if len(parts) != 3 or parts[1] not in kind_registry_map():
        raise FarmhandError(
            "bad_registry_key",
            f"Registry keys look like '{{lib_id}}:{{kind}}:{{name}}' with kind one of "
            f"{sorted(kind_registry_map())}; got '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    registry: Any = ctx.registry(kind_registry_map()[parts[1]])
    cls = registry.get(registry_key)
    if cls is None:
        raise FarmhandError(
            "component_not_found",
            f"No component registered under '{registry_key}'.",
            ids={"registry_key": registry_key},
        )
    return cls


def project_local_libraries(ctx: FarmhandContext) -> list[str]:
    """Libraries installed from a folder inside this workspace (haywire init layout)."""
    registry = ctx.registry(LibraryRegistry)
    workspace = str(ctx.workspace_root())
    result = []
    for lib_id in registry.list_names():
        install_type = registry.get_library_install_type(lib_id)
        source = registry.get_library_source(lib_id) or ""
        if install_type == InstallType.FOLDER and source.startswith(workspace):
            result.append(lib_id)
    return sorted(result)


def resolve_target_library(ctx: FarmhandContext, library: str | None) -> str:
    locals_ = project_local_libraries(ctx)
    if library is not None:
        if library not in locals_:
            raise FarmhandError(
                "not_project_library",
                f"'{library}' is not a project-local library (project-local: {locals_ or 'none'}). "
                f"Farmhand writes source only into project-local libraries.",
                ids={"library": library},
            )
        return library
    if not locals_:
        raise FarmhandError(
            "no_project_library",
            "No project-local library exists in this workspace — create one with 'haywire init'.",
        )
    if len(locals_) > 1:
        raise FarmhandError(
            "ambiguous_project_library",
            f"Several project-local libraries exist; pass library= explicitly: {locals_}.",
        )
    return locals_[0]


def library_folder(ctx: FarmhandContext, lib_id: str) -> Path:
    registry = ctx.registry(LibraryRegistry)
    identity = registry.get_library_identity(lib_id)
    return Path(identity.folder_path)
