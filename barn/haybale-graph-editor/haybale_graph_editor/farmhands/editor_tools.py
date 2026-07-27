"""graph_editor_* MCP tools: query, inspect, structural edits, set_property, promotion, undo/redo.

Every mutating tool opens exactly one undo fence FIRST (ctx.fence(editor)) so one
tool call is one undo gesture, then broadcasts GraphDataMutated after success.
undo/redo drive the SHARED human+agent timeline.

Read tools split by breadth: query_graph is the MAP (topology of every node and
edge, no values), inspect_node is the INSPECTOR (one node's live port/settings
values, schema and health). inspect_node and set_property are counterparts — a
row's flat ``name`` is what set_property takes, and its ``accessor`` is what
promote_setting takes.
"""

from __future__ import annotations

from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.node.promotion import demote_setting, promote_setting
from haywire.core.session.signals import GraphDataMutated
from haywire.core.types.enums import PortType

_READ_ONLY = ToolAnnotations(read_only_hint=True)
_MUTATING = ToolAnnotations()


def _editor(ctx: FarmhandContext, binding_id: str):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    container = ctx.state(GraphAppState).get(binding_id)
    if container is None:
        raise FarmhandError(
            "graph_not_found", f"No open graph '{binding_id}'.", ids={"binding_id": binding_id}
        )
    return container.editor


def _node(editor, node_id):
    wrapper = editor.get_node_wrapper(node_id)
    if wrapper is None:
        raise FarmhandError("node_not_found", f"No node '{node_id}'.", ids={"node_id": node_id})
    return wrapper


def _port_direction(port) -> str:
    if port.is_inlet():
        return "inlet"
    if port.is_outlet():
        return "outlet"
    return "config"


def _port_type_key(port) -> str | None:
    """The concrete data-type registry key (e.g. 'visiongraph:rgb_frame'), or None.

    flow_type only distinguishes data/exec/callback; this names the actual type
    flowing through the port. Defensive: type_cls or its class_identity can be
    absent on edge cases, so miss quietly rather than raise inside a read tool.
    """
    identity = getattr(port.type_cls, "class_identity", None)
    return getattr(identity, "registry_key", None)


def _port_row(pid: str, port, detail: bool) -> dict:
    row = {"id": pid, "direction": _port_direction(port), "flow_type": port.flow_type.value}
    if detail:
        row.update(
            {
                "data_type": _port_type_key(port),
                "allow_multiple_links": port.allow_multiple_links,
                "is_linked": port.is_linked(),
                "link_count": len(port._get_linked_edges_uuid()),
                "use_mode": port.use_mode,
                "promoted": port.promoted,
                "has_widget": port.widget_key is not None,
                "is_linked_lazy": port.is_linked_lazy,
            }
        )
    return row


def _node_row(wrapper, detail: bool = False) -> dict:
    node = wrapper.node
    return {
        "node_id": wrapper.node_id,
        "registry_key": node.class_identity.registry_key,
        "ports": [_port_row(pid, port, detail) for pid, port in node.ports.items()],
    }


# ---------------------------------------------------------------------------
# inspect_node row builders
#
# Both ports and settings keep their UI constraints in the SAME place —
# widget_config["properties"] (min/max folded in at setting.__set_name__ time,
# options for CHOICES, vec_meta for vectors) — so one extraction helper serves
# both kinds. widget_config may legitimately hold a live zero-arg callable at
# properties["options"] (resolved by SelectWidget at every build(), and only
# reachable here on a PROMOTED port — DataPort.__post_init__ rejects a
# non-serializable widget_config on a plain port, ADR 0018). We resolve it the
# same way the widget does, and drop anything else that can't cross a JSON
# boundary rather than leaking an object repr to the agent.
# ---------------------------------------------------------------------------


def _properties_bag(widget_config) -> dict:
    """The ``properties`` sub-dict of a widget_config, in either spelling.

    ``widget_config`` accepts a ``{"properties": {...}}`` wrapper or a bare
    properties dict — both are equivalent per the ``setting`` docstring.
    """
    if not isinstance(widget_config, dict):
        return {}
    props = widget_config.get("properties")
    return props if isinstance(props, dict) else widget_config


# Row keys a widget property must never overwrite: the agent's write handles
# (name/accessor) and the value semantics it reasons about. A third-party
# widget is free to name a property 'value'; silently clobbering the row's own
# value would corrupt the read->write round-trip, so reserved keys win.
_RESERVED_ROW_KEYS = frozenset(
    {
        "name",
        "accessor",
        "kind",
        "value",
        "value_omitted",
        "is_set",
        "default",
        "type",
        "error",
        "mirrors",
        "graph_mirror",
        "promoted",
        "promoted_as",
        "ui_state",
        "direction",
        "flow_type",
        "data_type",
        "is_linked",
    }
)


def _constraints(widget_config) -> dict:
    """JSON-safe constraint hints an agent needs before writing a value.

    Resolves a callable ``options`` (the documented dynamic-dropdown
    mechanism) and drops any entry that cannot be serialized, so an exotic
    widget config degrades to fewer hints instead of an object repr.
    """
    from haywire.core.types.utils import is_cattrs_serializable

    out: dict = {}
    for key, value in _properties_bag(widget_config).items():
        if key in _RESERVED_ROW_KEYS:
            continue
        if key == "options" and callable(value):
            # Same contract as SelectWidget.build(): resolve at read time so
            # the agent sees the live valid set. A probe against absent
            # hardware must not fail the whole inspection.
            try:
                value = value()
            except Exception as exc:
                out["options_unavailable"] = str(exc)
                continue
        ok, _ = is_cattrs_serializable(value)
        if ok:
            out[key] = value
    return out


def _jsonable(value) -> bool:
    """True if *value* survives a JSON boundary without a str() fallback.

    Vec2i/Vec3f/... are ``list`` subclasses and Color/Icon are ``str``, so
    every settings type passes; an arbitrary port BaseType (mesh, frame) does
    not and is reported as omitted rather than stringified into the payload.
    """
    return value is None or isinstance(value, (bool, int, float, str, list, dict))


def _inspect_port_row(pid: str, port, data: str) -> dict:
    """One port at the requested depth. ``name`` is the join key across depths."""
    row: dict = {"name": pid}
    if data == "info":
        # The orientation payload: what this port IS, per its author. Grouping
        # by direction upstream makes the direction key itself redundant.
        row["label"] = port.label or ""
        row["description"] = port.description or ""
        row["flow_type"] = port.flow_type.value
        row["data_type"] = _port_type_key(port)
        if port.hidden:
            row["hidden"] = True
        if port.deprecation_warning:
            row["deprecated"] = port.deprecation_warning
        return row

    row["is_linked"] = port.is_linked()
    row["promoted"] = port.promoted
    try:
        value = port.get_value()
    except Exception as exc:
        row["error"] = str(exc)
        return row
    # A linked inlet is driven by its edge — writing it is pointless, so the
    # agent needs is_linked next to the value to judge whether a write sticks.
    if _jsonable(value):
        row["value"] = value
    else:
        row["value_omitted"] = type(value).__name__

    if data == "all":
        row["data_type"] = _port_type_key(port)
        row["flow_type"] = port.flow_type.value
        row["use_mode"] = port.use_mode
        row["allow_multiple_links"] = port.allow_multiple_links
        row.update(_constraints(port.widget_config))
    return row


def _inspect_setting_row(bag, accessor: str, name: str, descriptor, data: str) -> dict:
    """One settings field at the requested depth.

    ``name`` is the flat handle ``graph_editor_set_property`` takes and the key
    that joins an ``info`` row to its ``value``/``all`` counterpart;
    ``accessor`` is the bag handle ``graph_editor_promote_setting`` takes.
    """
    row: dict = {"name": name, "accessor": accessor}

    if data == "info":
        row["label"] = descriptor._label or ""
        row["description"] = descriptor._description or ""
        row["category"] = descriptor._category or "root"
        return row

    try:
        row["value"] = getattr(bag, name)
        # is_set is the write-relevant opinion: a field that merely INHERITS a
        # value is not overridden here, and writing its current value is a
        # no-op (setting.__set__ returns early on equality).
        row["is_set"] = bag._is_locally_set(descriptor)
        default = descriptor._default
        row["default"] = default() if callable(default) else default
    except Exception as exc:
        # _cell_for raises for a descriptor that bypassed IType enforcement —
        # a genuine bug. Report it per-field so one broken field can't blind
        # the agent to the other 28.
        row["error"] = str(exc)
        return row

    if data == "all":
        itype = getattr(descriptor, "_type", None)
        row["type"] = getattr(itype, "__name__", None)
        if descriptor.is_mirror:
            row["mirrors"] = descriptor._mirror_key or None
        if descriptor.is_graph_mirror:
            row["graph_mirror"] = True
        if bag.is_promoted(name):
            direction = bag.get_promoted_direction(name)
            row["promoted_as"] = direction.value if direction is not None else None
        # ADR 0020: composed presentation state (imperative seed + enabled_when /
        # visible_when gates), severity-max. watch() seeds DISABLED — read-only is
        # convention, not enforcement (a direct write still lands), so report the
        # state and let the agent decide rather than promising a guarantee.
        ui_state = bag.effective_ui_state(name)
        if ui_state.name != "NORMAL":
            row["ui_state"] = ui_state.name.lower()
        row.update(_constraints(descriptor.widget_config))
    return row


def _settings_payload(node, accessors: list[str], data: str, wanted: set[str] | None):
    """Settings rows, grouped by author category at ``info`` depth.

    ``info`` mirrors how the properties panel clusters fields, so the agent
    inherits the author's own grouping; deeper levels stay a flat list because
    by then the agent is working from names it already has.
    """
    rows: list[dict] = []
    for accessor in accessors:
        bag = getattr(node, accessor, None)
        if bag is None:
            continue
        for name, descriptor in type(bag)._property_settings().items():
            if wanted is not None and name not in wanted:
                continue
            rows.append(_inspect_setting_row(bag, accessor, name, descriptor, data))
    if data != "info":
        return rows
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.pop("category", "root"), []).append(row)
    return grouped


def _matched_names(node, accessors: list[str], wanted: set[str] | None) -> set[str]:
    """Which of *wanted* exist as fields on *accessors*' bags.

    Fed into the ``unmatched`` report, so the caller learns a filter name hit
    nothing instead of inferring absence from a short list.
    """
    if wanted is None:
        return set()
    found: set[str] = set()
    for accessor in accessors:
        bag = getattr(node, accessor, None)
        if bag is not None:
            found |= wanted & set(type(bag)._property_settings())
    return found


def _state_row(wrapper) -> dict:
    """Lifecycle state: which stage failed, and why.

    The per-stage booleans are the primary diagnostic after an agent edits a
    node's source and hot-reloads it — is_imported False is a syntax/import
    error, is_instantiated False a constructor bug, is_structural False a bad
    port declaration. Tracebacks stay in studio_get_errors.
    """
    state = wrapper.state
    errors = state.get_errors() or []
    stages = (
        "error_import",
        "error_instantiate",
        "error_initialize",
        "error_structural",
        "error_test",
        "error_custom",
        "error_runtime",
    )
    return {
        "is_valid": state.is_valid(),
        "is_registered": state.is_registered,
        "is_imported": state.is_imported,
        "is_instantiated": state.is_instantiated,
        "is_initialized": state.is_initialized,
        "is_structural": state.is_structural,
        "has_test_passed": state.has_test_passed,
        "errors": [
            {"stage": stage, "message": str(exc)}
            for stage in stages
            if (exc := getattr(state, stage, None)) is not None
        ],
        "warnings": [str(w) for w in state.warnings],
        "total_errors": len(errors),
    }


def _edge_error(edge) -> str | None:
    """The edge's main error message (state-prioritised), or None when healthy."""
    err = edge.state.get_error()
    return getattr(err, "message", None) if err is not None else None


def _edge_row(edge, detail: bool = False) -> dict:
    row = {
        "edge_id": edge.edge_id,
        "source_node": edge.source_node_id,
        "outlet": edge.outlet_port_id,
        "sink_node": edge.sink_node_id,
        "inlet": edge.inlet_port_id,
        "flow_type": edge.edge_type.value,  # "data" | "control" | "callback"
    }
    if detail:
        # chain_adapter_keys is the BUILT chain (ordered adapter registry keys):
        # empty => endpoints type-compatible (direct); non-empty => coercion inserted.
        adapters = list(edge.edge.chain_adapter_keys)
        row.update(
            {
                "is_functional": edge.is_functional(),
                "is_linked": edge.state.is_linked,
                "is_lazy": edge.is_lazy,
                "adapter_chain": adapters,
                "has_adapters": bool(adapters),
                "error": _edge_error(edge),
            }
        )
    return row


@farmhand(
    label="Query graph",
    description=(
        "Nodes (with ports) and edges of an open graph. Pass detail=true for the full "
        "per-port setup (data_type, allow_multiple_links, is_linked, link_count, use_mode, "
        "promoted, has_widget, is_linked_lazy) AND per-edge health (is_functional, is_linked, "
        "is_lazy, adapter_chain, has_adapters, error); default returns the base id/direction/"
        "flow_type per port and id/topology/flow_type per edge."
    ),
    registry_id="query_graph",
    annotations=_READ_ONLY,
)
class GraphEditorQueryGraphTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        limit: int = 100,
        offset: int = 0,
        detail: bool = False,
    ) -> dict:
        editor = _editor(ctx, binding_id)
        nodes = [_node_row(w, detail) for w in editor.list_node_wrappers()]
        edges = [_edge_row(e, detail) for e in editor.list_edges()]
        total = len(nodes)
        page = nodes[offset : offset + limit]
        return {
            "summary": (
                f"{total} nodes, {len(edges)} edges in {binding_id}."
                f"{truncation_note(len(page), total, offset)}"
            ),
            "nodes": page,
            "edges": edges,
            "total": total,
        }


_SECTIONS = ("summary", "node_id", "ports", "settings", "props", "state")
_DATA_LEVELS = ("info", "value", "all")


@farmhand(
    label="Inspect node",
    description="Drill down on ONE node in three steps — name only the sections and depth you "
    "need, because a node can carry 30+ settings fields and an unfocused call wastes most of "
    "what it returns. The read counterpart to graph_editor_set_property: a row's 'name' is "
    "exactly what you pass back as name=, and it joins a row across all depths.\n"
    "Typical drill-down: get=['summary'] -> get=['ports','settings'] (data='info', the default, "
    "to learn what exists) -> add data='value' or 'all' with filter=['the_one_field'].\n"
    f"get: any of {', '.join(_SECTIONS)} (required, non-empty)\n"
    "  summary: always returned — identity, counts, validity (name it alone for a cheap survey)\n"
    "  node_id: node_id + registry_key\n"
    "  ports: ports grouped as inlets/outlets/configs\n"
    "  settings: author-declared settings bags (at data='info', grouped by author category)\n"
    "  props: framework properties (position, size, muted, skin) — never mixed into settings\n"
    "  state: is_valid + per-stage lifecycle booleans + errors [{stage, message}] + warnings; "
    "read this after editing a node's source to learn WHICH stage failed\n"
    f"data: one of {', '.join(_DATA_LEVELS)} (default info) — how much per row\n"
    "  info: what it IS — label, description, category/data_type. NO values. Start here.\n"
    "  value: what it is SET to — value, is_set, default, is_linked\n"
    "  all: value plus everything writable — type, min/max/options, mirrors, ui_state, use_mode\n"
    "filter: exact row names to return, e.g. ['threshold'] (default [] = all rows). Applies to "
    "ports, settings and props alike; names that match nothing come back under 'unmatched'.\n"
    "Value notes: a port holding a non-JSON value (mesh, frame) reports value_omitted instead "
    "of value. is_set=false means the field INHERITS its value — writing the same value back is "
    "a silent no-op. min/max are UI hints and are NOT enforced on writes; a value failing a "
    "field's validator is rejected silently by the framework, so set_property verifies the write "
    "and reports the rejection.",
    registry_id="inspect_node",
    annotations=_READ_ONLY,
)
class GraphEditorInspectNodeTool(Farmhand):
    input_schema_override = {
        "type": "object",
        "properties": {
            "binding_id": {"type": "string"},
            "node_id": {"type": "string"},
            "get": {
                "type": "array",
                "items": {"type": "string", "enum": list(_SECTIONS)},
                "minItems": 1,
            },
            "data": {"type": "string", "enum": list(_DATA_LEVELS)},
            "filter": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["binding_id", "node_id", "get"],
    }

    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        node_id: str,
        get: list[str] = [],
        data: str = "info",
        filter: list[str] = [],
    ) -> dict:
        editor = _editor(ctx, binding_id)
        wrapper = _node(editor, node_id)
        node = wrapper.node

        sections = list(dict.fromkeys(get))
        if not sections:
            raise FarmhandError(
                "no_section_selected",
                f"get= must name at least one section: {', '.join(_SECTIONS)}.",
                ids={"node_id": node_id},
            )
        unknown = [s for s in sections if s not in _SECTIONS]
        if unknown:
            raise FarmhandError(
                "unknown_section",
                f"Unknown get= section(s): {', '.join(unknown)}. Valid: {', '.join(_SECTIONS)}.",
                ids={"node_id": node_id, "unknown": ",".join(unknown)},
            )
        if data not in _DATA_LEVELS:
            raise FarmhandError(
                "unknown_data_level",
                f"Unknown data level '{data}'. Valid: {', '.join(_DATA_LEVELS)}.",
                ids={"node_id": node_id, "data": data},
            )

        # None means "no filtering" — distinct from an empty match set.
        wanted: set[str] | None = set(filter) or None
        matched: set[str] = set()

        # props IS a settings bag (it sits in _settings_bags beside author bags),
        # so the settings section must exclude it explicitly or every node grows
        # 13 framework rows.
        bags = list(type(node)._settings_bags)
        author_bags = [b for b in bags if b != "props"]

        result: dict = {}
        if "node_id" in sections:
            result["node_id"] = wrapper.node_id
            result["registry_key"] = node.class_identity.registry_key
        if "ports" in sections:
            # Grouped by direction: it is how ports are declared
            # (as_inlet/as_outlet/as_config) and how an agent wiring an edge
            # thinks, and it makes a per-row direction key redundant.
            groups: dict[str, list[dict]] = {"inlets": [], "outlets": [], "configs": []}
            for pid, port in node.ports.items():
                if wanted is not None and pid not in wanted:
                    continue
                matched.add(pid)
                bucket = {"inlet": "inlets", "outlet": "outlets"}.get(_port_direction(port), "configs")
                groups[bucket].append(_inspect_port_row(pid, port, data))
            result["ports"] = {k: v for k, v in groups.items() if v}
        if "settings" in sections:
            result["settings"] = _settings_payload(node, author_bags, data, wanted)
            matched |= _matched_names(node, author_bags, wanted)
        if "props" in sections:
            prop_bags = [b for b in bags if b == "props"]
            result["props"] = _settings_payload(node, prop_bags, data, wanted)
            matched |= _matched_names(node, prop_bags, wanted)
        if "state" in sections:
            result["state"] = _state_row(wrapper)

        # A filter name that matched nothing is reported rather than silently
        # absent: "typo" and "field does not exist" must not look identical to
        # an agent about to write.
        if wanted is not None:
            missing = sorted(wanted - matched)
            if missing:
                result["unmatched"] = missing

        # summary is unconditional (canon: every result carries one) and is the
        # whole payload when it was the only section named.
        n_settings = sum(len(type(getattr(node, b))._property_settings()) for b in author_bags)
        state = wrapper.state
        health = "valid" if state.is_valid() else "INVALID"
        n_errors = len(state.get_errors() or [])
        err_note = f", {n_errors} error(s)" if n_errors else ""
        warn = f", {len(state.warnings)} warning(s)" if state.warnings else ""
        scope = f" filter={len(filter)} name(s)" if filter else ""
        result["summary"] = (
            f"{wrapper.node_id} ({node.class_identity.registry_key}): "
            f"{len(node.ports)} port(s), {n_settings} setting(s) in {len(author_bags)} bag(s) "
            f"— {health}{err_note}{warn}. Returned: {', '.join(sections)} at data='{data}'{scope}."
        )
        return result


@farmhand(
    label="Add node",
    description="Add a node by registry key. Call studio_describe_component first to learn its ports.",
    registry_id="add_node",
    annotations=_MUTATING,
)
class GraphEditorAddNodeTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        registry_key: str,
        x: float = 3750.0,
        y: float = 3750.0,
    ) -> dict:
        editor = _editor(ctx, binding_id)
        ctx.fence(editor)
        wrapper = editor.create_wrapper(registry_key, (x, y))
        if wrapper is None:
            raise FarmhandError(
                "add_node_failed",
                f"Could not add node '{registry_key}'.",
                ids={"registry_key": registry_key},
            )
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Added {wrapper.node_id}.", "node_id": wrapper.node_id}


@farmhand(
    label="Connect",
    description="Connect an outlet to an inlet.",
    registry_id="connect",
    annotations=_MUTATING,
)
class GraphEditorConnectTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        source_node_id: str,
        outlet: str,
        sink_node_id: str,
        inlet: str,
    ) -> dict:
        editor = _editor(ctx, binding_id)
        # Editor.create_edge returns True even when the underlying action fails,
        # because HistoryManager.add_action swallows execute() errors. Validate the
        # endpoints up front and verify the edge really landed so the tool reports
        # honest success/failure.
        _node(editor, source_node_id)
        _node(editor, sink_node_id)
        before = len(editor.list_edges())
        ctx.fence(editor)
        editor.create_edge(source_node_id, outlet, sink_node_id, inlet)
        if len(editor.list_edges()) <= before:
            raise FarmhandError(
                "connect_failed",
                f"Could not connect {source_node_id}:{outlet} -> {sink_node_id}:{inlet} "
                f"(check the pin ids and type compatibility).",
                ids={
                    "source_node_id": source_node_id,
                    "outlet": outlet,
                    "sink_node_id": sink_node_id,
                    "inlet": inlet,
                },
            )
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Connected {source_node_id}:{outlet} -> {sink_node_id}:{inlet}."}


@farmhand(
    label="Remove elements",
    description="Remove nodes and/or edges (also the way to disconnect).",
    registry_id="remove_elements",
    annotations=_MUTATING,
)
class GraphEditorRemoveElementsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        nodes: list[str] = [],
        edges: list[str] = [],
    ) -> dict:
        editor = _editor(ctx, binding_id)
        ctx.fence(editor)
        ok = editor.remove_elements(nodes, edges)
        if not ok:
            raise FarmhandError(
                "remove_failed",
                "Could not remove the given elements — re-check the node/edge id lists.",
                ids={"nodes": ",".join(nodes), "edges": ",".join(edges)},
            )
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Removed {len(nodes)} nodes, {len(edges)} edges."}


@farmhand(
    label="Move nodes",
    description="Move nodes to absolute positions ({node_id: {x, y}}).",
    registry_id="move_nodes",
    annotations=_MUTATING,
)
class GraphEditorMoveNodesTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, positions: dict) -> dict:
        editor = _editor(ctx, binding_id)
        ctx.fence(editor)
        ok = editor.move_nodes_to(positions)
        if not ok:
            raise FarmhandError("move_failed", "Could not move the given nodes.")
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Moved {len(positions)} nodes."}


def _read_property(node, name: str):
    """Read *name* the way SetPropertyAction resolves it: port first, then bags.

    Returns ``(found, value)``. Used to verify a write actually landed — the
    settings write path rejects a value failing its validator SILENTLY
    (``setting.__set__`` returns early), so the action reports success either
    way and only a read-back can tell them apart.
    """
    if name in node.ports:
        return True, node.ports[name].get_value()
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        if name in type(bag)._property_settings():
            return True, getattr(bag, name)
    return False, None


@farmhand(
    label="Set property",
    description="Set a node property (port value or settings field) by name. Undo-recorded. "
    "'name' resolves to a port id first, then a settings field — use the exact 'name' from a "
    "graph_editor_inspect_node row. The write is verified by reading the value back: a value "
    "rejected by the field's validator raises set_rejected rather than reporting a success that "
    "did not happen. Note min/max are UI hints only and are NOT enforced — an out-of-range write "
    "succeeds, so respect the bounds inspect_node reports.",
    registry_id="set_property",
    annotations=_MUTATING,
)
class GraphEditorSetPropertyTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, node_id: str, name: str, value=None) -> dict:
        editor = _editor(ctx, binding_id)
        ctx.fence(editor)
        ok = editor.set_property(node_id, name, value)
        if not ok:
            raise FarmhandError(
                "set_property_failed",
                f"Could not set '{name}' on node '{node_id}' (unknown node or property).",
                ids={"node_id": node_id, "name": name},
            )
        # Post-condition check: is the field now what was asked for? Writing a
        # value the field already held is a legitimate no-op and still passes,
        # because the read-back equals the request either way.
        found, actual = _read_property(_node(editor, node_id).node, name)
        if found and actual != value:
            raise FarmhandError(
                "set_rejected",
                f"Write to '{name}' on '{node_id}' did not take: requested {value!r}, "
                f"value is still {actual!r}. The field's validator rejected it (the framework "
                f"drops such writes silently) — call graph_editor_inspect_node with "
                f"get=['settings'] to see its type and constraints.",
                ids={"node_id": node_id, "name": name},
            )
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Set '{name}' on {node_id} to {actual!r}."}


@farmhand(
    label="Promote setting",
    description="Promote a settings field to a data port. Not undo-routed (UI parity; later work).",
    registry_id="promote_setting",
    annotations=_MUTATING,
)
class GraphEditorPromoteSettingTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        node_id: str,
        accessor: str,
        field: str,
        direction: str = "inlet",
    ) -> dict:
        editor = _editor(ctx, binding_id)
        try:
            port_type = PortType[direction.upper()]
        except KeyError:
            raise FarmhandError(
                "bad_direction",
                f"direction must be one of inlet/outlet/config; got '{direction}'.",
                ids={"direction": direction},
            )
        node = _node(editor, node_id).node
        try:
            promote_setting(node, accessor, field, port_type)
        except ValueError as exc:
            raise FarmhandError("not_promotable", str(exc), ids={"node_id": node_id, "field": field})
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Promoted {accessor}.{field} on {node_id} as {direction}."}


@farmhand(
    label="Demote setting",
    description="Remove a promoted port, returning the field to a plain setting.",
    registry_id="demote_setting",
    annotations=_MUTATING,
)
class GraphEditorDemoteSettingTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str, node_id: str, port_id: str) -> dict:
        editor = _editor(ctx, binding_id)
        node = _node(editor, node_id).node
        demote_setting(node, port_id)
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Demoted port {port_id} on {node_id}."}


@farmhand(
    label="Undo",
    description="Undo the last change on this graph's SHARED human+agent timeline.",
    registry_id="undo",
    annotations=_MUTATING,
)
class GraphEditorUndoTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        editor = _editor(ctx, binding_id)
        performed = editor.undo()
        if performed:
            ctx.broadcast(GraphDataMutated())
        return {
            "summary": f"Undo {'performed' if performed else 'nothing to undo'}.",
            "performed": performed,
        }


@farmhand(
    label="Redo",
    description="Redo the last undone change on this graph's SHARED human+agent timeline.",
    registry_id="redo",
    annotations=_MUTATING,
)
class GraphEditorRedoTool(Farmhand):
    async def run(self, ctx: FarmhandContext, binding_id: str) -> dict:
        editor = _editor(ctx, binding_id)
        performed = editor.redo()
        if performed:
            ctx.broadcast(GraphDataMutated())
        return {
            "summary": f"Redo {'performed' if performed else 'nothing to redo'}.",
            "performed": performed,
        }
