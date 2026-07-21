"""studio_list_libraries / studio_list_components / studio_describe_component."""

from __future__ import annotations

import inspect
from typing import Any

from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.library.registry import LibraryRegistry

from ._helpers import kind_registry_map, page, resolve_component_class

_READ_ONLY = ToolAnnotations(read_only_hint=True)


@farmhand(
    label="List libraries",
    description="Installed libraries: id, label, version, description, tags, enabled.",
    registry_id="list_libraries",
    annotations=_READ_ONLY,
)
class StudioListLibrariesTool(Farmhand):
    async def run(self, ctx: FarmhandContext, limit: int = 50, offset: int = 0) -> dict:
        registry = ctx.registry(LibraryRegistry)
        rows = []
        for lib_id in sorted(registry.list_names()):
            identity = registry.get_library_identity(lib_id)
            rows.append(
                {
                    "id": lib_id,
                    "label": identity.label,
                    "version": identity.version,
                    "description": identity.description,
                    "tags": list(identity.tags or []),
                    "enabled": registry.is_library_enabled(lib_id),
                }
            )
        rows, total = page(rows, limit, offset)
        return {
            "summary": f"{total} libraries installed.{truncation_note(len(rows), total, offset)}",
            "libraries": rows,
            "total": total,
        }


@farmhand(
    label="List components",
    description="Component catalog, filterable by library and/or kind (registry prefix-scan).",
    registry_id="list_components",
    annotations=_READ_ONLY,
)
class StudioListComponentsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        library: str | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        kinds = kind_registry_map()
        selected = {kind: kinds[kind]} if kind in kinds else kinds
        rows = []
        for seg, registry_cls in selected.items():
            registry: Any = ctx.registry(registry_cls)
            for key in registry.list_names():
                parts = key.split(":")
                if len(parts) != 3 or parts[1] != seg:
                    continue  # e.g. library-level keys in mixed registries
                if library is not None and parts[0] != library:
                    continue
                rows.append({"registry_key": key, "library": parts[0], "kind": seg, "name": parts[2]})
        rows.sort(key=lambda r: r["registry_key"])
        rows, total = page(rows, limit, offset)
        return {
            "summary": f"{total} components match.{truncation_note(len(rows), total, offset)}",
            "components": rows,
            "total": total,
        }


@farmhand(
    label="Describe component",
    description="One component's identity and docstring. For nodes: read before graph_editor_add_node.",
    registry_id="describe_component",
    annotations=_READ_ONLY,
)
class StudioDescribeComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        cls = resolve_component_class(ctx, registry_key)
        identity = getattr(cls, "class_identity", None)
        return {
            "summary": f"{registry_key}: {getattr(identity, 'label', cls.__name__)}",
            "registry_key": registry_key,
            "class_name": cls.__name__,
            "label": getattr(identity, "label", cls.__name__),
            "description": getattr(identity, "description", ""),
            "docstring": inspect.getdoc(cls) or "",
        }
