from __future__ import annotations

import inspect
from typing import Any

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.library.kinds import kind_registry_map
from haywire.core.node.inspector import NodeInstanceInspector
from haywire_studio.docs_gen.model import ComponentRecord, LibraryDoc


def _extra_for_kind(kind: str, cls: Any, identity: Any) -> dict[str, Any]:
    """Kind-specific introspected payload. Only reads declared class/identity
    data — never infers. Unknown kinds return {}."""
    if kind == "type":
        return {
            "flow_type": getattr(identity, "flow_type", None) and identity.flow_type.value,
            "default": getattr(identity, "default", None),
            "widget_key": getattr(identity, "widget_key", None),
            "color": getattr(identity, "color", None),
        }
    if kind == "adapter":
        cf = getattr(identity, "converts_from", None)
        ct = getattr(identity, "converts_to", None)
        return {
            "converts_from": getattr(getattr(cf, "class_identity", None), "registry_key", None),
            "converts_to": getattr(getattr(ct, "class_identity", None), "registry_key", None),
            "priority": getattr(identity, "priority", 0),
        }
    if kind == "farmhand":
        from haywire.core.farmhand import derive_input_schema

        annotations = getattr(identity, "annotations", None)
        return {
            "input_schema": cls.input_schema()
            if hasattr(cls, "input_schema")
            else derive_input_schema(cls.run),
            "annotations": vars(annotations) if annotations is not None else {},
        }
    if kind == "widget":
        return {
            "min_width": getattr(identity, "min_width", None),
            "min_height": getattr(identity, "min_height", None),
            "max_height": getattr(identity, "max_height", None),
        }
    if kind == "panel":
        return {
            "editor_keys": list(getattr(identity, "editor_keys", []) or []),
            "scopes": list(getattr(identity, "scopes", []) or []),
            "order": getattr(identity, "order", None),
        }
    if kind == "editor":
        return {
            "default_slot": getattr(identity, "default_slot", None),
            "opens": str(getattr(identity, "opens", "")),
            "order": getattr(identity, "order", None),
        }
    if kind == "theme":
        return {"theme_type": getattr(identity, "theme_type", "")}
    return {}


def _record_from_class(kind: str, key: str, cls: Any) -> ComponentRecord:
    identity = cls.class_identity
    return ComponentRecord(
        registry_key=key,
        kind=kind,
        library_id=key.split(":")[0],
        label=getattr(identity, "label", "") or "",
        description=getattr(identity, "description", "") or "",
        deprecation=getattr(identity, "deprecation_warning", "") or "",
        hidden=bool(getattr(identity, "hidden", False)),
        search_tags=list(getattr(identity, "search_tags", []) or []),
        menu=getattr(identity, "menu", "") or "",
        docstring=inspect.getdoc(cls) or "",
        ports=[],
        settings=[],
        extra=_extra_for_kind(kind, cls, identity),
    )


def _node_record(key: str, cls: Any, graph: BaseGraph) -> ComponentRecord:
    """Build a node's ComponentRecord by instantiating it in a throwaway graph.

    Ports/settings can only be read off a live instance (declared purely at
    the class level they don't exist yet), so nodes get a different path from
    the other 10 kinds: a headless build via ``create_node_wrapper``, then
    ``NodeInstanceInspector`` over the resulting ``BaseNode``. A node that
    cannot instantiate headlessly still gets a thin doc from its class alone —
    the coverage report (not built in this task) is meant to flag the empty
    port list, never a fabricated one.
    """
    base = _record_from_class("node", key, cls)
    try:
        wrapper = graph.create_node_wrapper(key, position=(0, 0))
        if wrapper is None:
            raise RuntimeError(f"create_node_wrapper returned None for '{key}'")
        inspector = NodeInstanceInspector(wrapper.node)
        ports = inspector.ports()
        settings = inspector.settings()
    except Exception:
        ports, settings = [], []
    return ComponentRecord(
        registry_key=base.registry_key,
        kind="node",
        library_id=base.library_id,
        label=base.label,
        description=base.description,
        deprecation=base.deprecation,
        hidden=base.hidden,
        search_tags=base.search_tags,
        menu=base.menu,
        docstring=base.docstring,
        ports=ports,
        settings=settings,
        extra={},
    )


def extract_library(service: Any, library_id: str) -> LibraryDoc:
    lib_identity = service.get_library_registry().get_library_identity(library_id)
    records: list[ComponentRecord] = []
    graph = BaseGraph(graph_id="docs_gen", name="docs", validation_scheduler=SyncScheduler())
    for kind, registry_cls in kind_registry_map().items():
        registry = service_registry(service, registry_cls)
        for key in registry.list_names():
            parts = key.split(":")
            if len(parts) != 3 or parts[1] != kind or parts[0] != library_id:
                continue
            cls = registry.get(key)
            if cls is None:
                continue
            if kind == "node":
                records.append(_node_record(key, cls, graph))
            else:
                records.append(_record_from_class(kind, key, cls))
    records.sort(key=lambda r: r.registry_key)
    return LibraryDoc(
        library_id=library_id,
        label=lib_identity.label,
        version=lib_identity.version,
        description=lib_identity.description,
        components=records,
    )


def service_registry(service: Any, registry_cls: type) -> Any:
    """Fetch a registry instance from the service by its class."""
    return service.injector.get(registry_cls)
