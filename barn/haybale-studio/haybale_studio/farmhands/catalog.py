"""studio_list_libraries / studio_list_components / studio_describe_component."""

from __future__ import annotations

import inspect
from collections import Counter
from typing import Any

from haywire.core.docs.canons import canon_uri
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


def _is_synthetic_library(lib_id: str) -> bool:
    """Dunder-wildcard: matches the '__system__' fallback and any future synthetic id."""
    return lib_id.startswith("__") and lib_id.endswith("__")


# --8<-- [start:list_libraries_tool]
@farmhand(
    label="List libraries",
    description="Installed libraries: id, label, version, description, tags, enabled. "
    "Synthetic libraries (dunder ids like '__system__') are excluded unless "
    "include_system=true.",
    registry_id="list_libraries",
    annotations=_READ_ONLY,
)
class StudioListLibrariesTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        include_system: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        registry = ctx.registry(LibraryRegistry)
        rows = []
        for lib_id in sorted(registry.list_names()):
            if not include_system and _is_synthetic_library(lib_id):
                continue
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


# --8<-- [end:list_libraries_tool]


_KIND_ENUM = sorted(kind_registry_map())

_LIST_COMPONENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "library": {"type": "string"},
        "kind": {"type": "string", "enum": _KIND_ENUM},
        "search": {"type": "string"},
        "include_hidden": {"type": "boolean", "default": False},
        "include_system": {"type": "boolean", "default": False},
        "count_only": {"type": "boolean", "default": False},
        "limit": {"type": "integer", "default": 100},
        "offset": {"type": "integer", "default": 0},
    },
    "required": [],
}


def _matches_search(identity: Any, query_lower: str) -> bool:
    """Same substring-over-label/description/search_tags algorithm as
    NodeFactory.search_nodes (packages/haywire-core/.../node/factory.py), applied
    generically since label/description live on BaseIdentity. search_tags is
    NodeIdentity-only, so other kinds match on label/description alone.
    """
    searchable = [identity.label.lower(), identity.description.lower()]
    searchable.extend(tag.lower() for tag in getattr(identity, "search_tags", ()))
    return any(query_lower in text for text in searchable)


@farmhand(
    label="List components",
    description="ALWAYS pass at least one of kind=/library=/search= — omitting all three "
    "returns every installed component (100+) and is slow and almost never what you want. "
    "Component catalog, filterable and searchable.\n"
    "Start with count_only=true to see totals per library/kind before listing rows — the "
    "cheapest way to survey scope.\n"
    f"kind: one of {', '.join(_KIND_ENUM)}\n"
    "library: exact library id (see studio_list_libraries)\n"
    "search: substring match against label/description/search_tags (same algorithm as the "
    "node-menu search)\n"
    "count_only: return counts grouped by library/kind instead of rows\n"
    "include_hidden: include internal components (e.g. reroute/error nodes), excluded by default\n"
    "include_system: include synthetic libraries (dunder ids like '__system__'), excluded by "
    "default",
    registry_id="list_components",
    annotations=_READ_ONLY,
)
class StudioListComponentsTool(Farmhand):
    input_schema_override = _LIST_COMPONENTS_SCHEMA

    async def run(
        self,
        ctx: FarmhandContext,
        library: str | None = None,
        kind: str | None = None,
        search: str | None = None,
        include_hidden: bool = False,
        include_system: bool = False,
        count_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        kinds = kind_registry_map()
        selected = {kind: kinds[kind]} if kind in kinds else kinds
        query_lower = search.lower() if search else None
        matches: list[tuple[str, Any]] = []  # (registry_key, class_identity)
        for seg, registry_cls in selected.items():
            registry: Any = ctx.registry(registry_cls)
            names = registry.list_names() if include_hidden else registry.list_visible_names()
            for key in names:
                parts = key.split(":")
                if len(parts) != 3 or parts[1] != seg:
                    continue  # e.g. library-level keys in mixed registries
                if library is not None and parts[0] != library:
                    continue
                if not include_system and _is_synthetic_library(parts[0]):
                    continue
                identity = registry.get(key).class_identity
                if query_lower is not None and not _matches_search(identity, query_lower):
                    continue
                matches.append((key, identity))
        matches.sort(key=lambda m: m[0])

        if count_only:
            counts: Counter[tuple[str, str]] = Counter()
            for key, _identity in matches:
                lib_id, seg, _ = key.split(":")
                counts[(lib_id, seg)] += 1
            grouped: dict[str, dict[str, int]] = {}
            for (lib_id, seg), n in sorted(counts.items()):
                grouped.setdefault(lib_id, {})[seg] = n
            return {
                "summary": f"{len(matches)} components match, across {len(grouped)} libraries.",
                "counts": grouped,
                "total": len(matches),
            }

        rows = [
            {"registry_key": key, "label": identity.label, "description": identity.description}
            for key, identity in matches
        ]
        rows, total = page(rows, limit, offset)
        summary = f"{total} components match.{truncation_note(len(rows), total, offset)}"
        if total > limit:
            # This call was truncated — the caller is either scanning everything
            # unfiltered or has a wide search; either way a scoping tip pays for
            # itself. Skipped when the page already covers the whole result (a
            # legitimately small unfiltered query shouldn't be nagged).
            summary += (
                " Tip: pass kind=/library=/search= to narrow this, or count_only=true to see totals first."
            )
        return {
            "summary": summary,
            "components": rows,
            "total": total,
        }


@farmhand(
    label="Describe component",
    description="One component's identity and docstring, plus the canon_doc_uri for its kind's "
    "authoring guide. For nodes: read before graph_editor_add_node.",
    registry_id="describe_component",
    annotations=_READ_ONLY,
)
class StudioDescribeComponentTool(Farmhand):
    async def run(self, ctx: FarmhandContext, registry_key: str) -> dict:
        from dataclasses import asdict

        cls = resolve_component_class(ctx, registry_key)
        identity = getattr(cls, "class_identity", None)
        kind = registry_key.split(":")[1]
        result: dict[str, Any] = {
            "summary": f"{registry_key}: {getattr(identity, 'label', cls.__name__)}",
            "registry_key": registry_key,
            "class_name": cls.__name__,
            "canon_doc_uri": canon_uri(kind),
            "label": getattr(identity, "label", cls.__name__),
            "description": getattr(identity, "description", ""),
            "docstring": inspect.getdoc(cls) or "",
        }
        if kind == "node":
            from haywire.core.graph.base import BaseGraph
            from haywire.core.graph.scheduler import SyncScheduler
            from haywire.core.node.inspector import NodeInstanceInspector

            try:
                graph = BaseGraph(graph_id="describe", name="describe", validation_scheduler=SyncScheduler())
                wrapper = graph.create_node_wrapper(registry_key, position=(0, 0))
                assert wrapper is not None
                inspector = NodeInstanceInspector(wrapper.node)
                result["ports"] = [asdict(p) for p in inspector.ports()]
                result["settings"] = [asdict(s) for s in inspector.settings()]
            except Exception as exc:
                # Never fail describe over an introspection hiccup; report it.
                result["ports"] = []
                result["settings"] = []
                result["inspect_error"] = str(exc)
        return result
