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

from typing import Any

from haywire.core.access import AccessTier
from haywire.core.farmhand import (
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
    truncation_note,
)
from haywire.core.node.inspector import NodeInstanceInspector, PortInfo, SettingInfo, _port_type_key
from haywire.core.node.promotion import demote_setting, promote_setting
from haywire.core.signals import GraphDataMutated
from haywire.core.types.enums import PortType

_READ_ONLY = ToolAnnotations(read_only_hint=True)
_MUTATING = ToolAnnotations()


def _editor(ctx: FarmhandContext, binding_id: str):
    from haybale_graph_editor.state.graph_app_state import GraphAppState

    container = ctx.state(GraphAppState).get(binding_id)
    if container is None:
        raise FarmhandError(
            "graph_not_found",
            f"No open graph '{binding_id}'.",
            ids={"binding_id": binding_id},
            help="Run haystack_list_graphs to see open graphs, or haystack_open_graph to open one.",
        )
    return container.editor


def _node(editor, node_id):
    wrapper = editor.get_node_wrapper(node_id)
    if wrapper is None:
        raise FarmhandError(
            "node_not_found",
            f"No node '{node_id}'.",
            ids={"node_id": node_id},
            help="Run graph_editor_query_graph to list the node ids in this graph.",
        )
    return wrapper


def _port_direction(port) -> str:
    if port.is_inlet():
        return "inlet"
    if port.is_outlet():
        return "outlet"
    return "config"


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
# non-serializable widget_config on a plain port). We resolve it the same way
# the widget does, and drop anything else that can't cross a JSON boundary
# rather than leaking an object repr to the agent.
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


def _inspect_port_row(pid: str, port, data: str, expand: bool = False) -> dict:
    """One port at the requested depth. ``name`` is the join key across depths."""
    row: dict = {"name": pid}
    # A hidden port is not rendered in the studio at all, so an agent reading it
    # in full works from a different reality than the user it shares the graph
    # with. Collapse to existence-only unless asked for by name.
    if port.hidden and not expand:
        return {"name": pid, "hidden": True}
    if data == "info":
        # The orientation payload: what this port IS, per its author. Grouping
        # by direction upstream makes the direction key itself redundant.
        info = PortInfo(
            id=pid,
            direction="inlet" if port.is_inlet() else "outlet",
            label=port.label or "",
            description=port.description or "",
            flow_type=port.flow_type.value,
            data_type=_port_type_key(port),
            hidden=bool(port.hidden),
            deprecation=port.deprecation_warning or "",
        )
        row["label"] = info.label
        row["description"] = info.description
        row["flow_type"] = info.flow_type
        row["data_type"] = info.data_type
        if info.hidden:
            row["hidden"] = True
        if info.deprecation:
            row["deprecated"] = info.deprecation
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


def _inspect_setting_row(
    bag, accessor: str, name: str, descriptor, data: str, info: SettingInfo, expand: bool = False
) -> dict:
    """One settings field at the requested depth.

    ``name`` is the flat handle ``graph_editor_set_property`` takes and the key
    that joins an ``info`` row to its ``value``/``all`` counterpart;
    ``accessor`` is the bag handle ``graph_editor_promote_setting`` takes.
    ``info`` is this field's schema, pre-computed once by ``NodeInstanceInspector``.
    """
    row: dict = {"name": name, "accessor": accessor}

    # HIDDEN removes the row from the properties panel entirely (a category
    # whose every field is hidden loses its header too), so these fields are
    # inaccessible to the human sharing this graph. Report existence — the
    # gate can flip and the field become live — but not schema the agent
    # cannot act on. Naming it in by_name expands it in full.
    if not expand and bag.effective_ui_state(name).name == "HIDDEN":
        row["ui_state"] = "hidden"
        if data == "info":
            row["category"] = info.category
        return row

    if data == "info":
        row["label"] = info.label
        row["description"] = info.description
        row["category"] = info.category
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
        # Composed presentation state (imperative seed + enabled_when /
        # visible_when gates), severity-max. watch() seeds DISABLED — read-only is
        # convention, not enforcement (a direct write still lands), so report the
        # state and let the agent decide rather than promising a guarantee.
        ui_state = bag.effective_ui_state(name)
        if ui_state.name != "NORMAL":
            row["ui_state"] = ui_state.name.lower()
        row.update(_constraints(descriptor.widget_config))
        # The only constraint that actually REJECTS a write. min/max above are
        # UI hints and are not enforced, so without this the agent sees the
        # decorative constraint and not the real one. The predicate is an opaque
        # Callable[[Any], bool] — presence, __name__ and first docstring line are
        # all that is recoverable; the agent cannot evaluate it locally.
        validator = getattr(descriptor, "_validator", None)
        if validator is not None:
            vrow: dict = {"name": getattr(validator, "__name__", None)}
            doc = (getattr(validator, "__doc__", None) or "").strip().splitlines()
            if doc:
                vrow["doc"] = doc[0].strip()
            row["validator"] = vrow
    return row


class _Filters:
    """The four selection axes, ANDed across axes and ORed within each.

    Split into one parameter per axis because the values are drawn from
    different namespaces: names and bag accessors are code-declared
    identifiers, a category is a free-text display label, and a direction is
    a closed enum. A single combined filter could not tell the ``depth`` bag
    from a ``"Depth"`` category, which would make the ``unmatched`` report
    untrustworthy.

    ``dirs`` applies to ports only — ports carry no bag or category, so they
    do not route through :meth:`keeps` at all.
    """

    def __init__(self, names: list[str], bags: list[str], cats: list[str], dirs: list[str]) -> None:
        self.names = set(names)
        self.bags = set(bags)
        self.cats = set(cats)
        self.dirs = set(dirs)
        self.hit_names: set[str] = set()
        self.hit_bags: set[str] = set()
        self.hit_cats: set[str] = set()
        self.hit_dirs: set[str] = set()

    @property
    def active(self) -> bool:
        return bool(self.names or self.bags or self.cats)

    def keeps(self, name: str, accessor: str, category: str) -> bool:
        """True if this row survives every active axis (AND across axes)."""
        if self.bags:
            if accessor not in self.bags:
                return False
            self.hit_bags.add(accessor)
        if self.cats:
            if category not in self.cats:
                return False
            self.hit_cats.add(category)
        if self.names:
            if name not in self.names:
                return False
            self.hit_names.add(name)
        return True

    def note_existing(self, name: str, accessor: str, category: str) -> None:
        """Record that these identifiers exist, regardless of AND outcome.

        ``unmatched`` must mean "no such thing on this node", not "excluded by
        a sibling axis" — otherwise a valid narrowing call reports phantom typos.
        """
        if name in self.names:
            self.hit_names.add(name)
        if accessor in self.bags:
            self.hit_bags.add(accessor)
        if category in self.cats:
            self.hit_cats.add(category)

    def unmatched(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for key, asked, hit in (
            ("by_name", self.names, self.hit_names),
            ("by_bag", self.bags, self.hit_bags),
            ("by_category", self.cats, self.hit_cats),
            ("by_dir", self.dirs, self.hit_dirs),
        ):
            missing = sorted(asked - hit)
            if missing:
                out[key] = missing
        return out


def _settings_payload(node, accessors: list[str], data: str, filters: _Filters):
    """Settings rows nested by bag, then by author category at ``info`` depth.

    Bag is the outer key because it is the code-declared identity (and the
    handle ``promote_setting`` takes), while ``category`` is a display label an
    author may reuse across bags — a flat category map would silently merge
    fields from different bags.
    """
    schema = {(s.bag, s.name): s for s in NodeInstanceInspector(node).settings()}

    # Per bag: {category: [rows]} at info depth, a flat [rows] list deeper.
    out: dict[str, dict[str, list[dict]] | list[dict]] = {}
    for accessor in accessors:
        bag = getattr(node, accessor, None)
        if bag is None:
            continue
        rows: list[dict] = []
        for name, descriptor in type(bag)._property_settings().items():
            info = schema[(accessor, name)]
            category = info.category
            filters.note_existing(name, accessor, category)
            if filters.active and not filters.keeps(name, accessor, category):
                continue
            # An explicitly named field is expanded even when hidden: naming it
            # IS the explicit request. Bulk selectors (bag/cat) do not expand.
            expand = name in filters.names
            rows.append(_inspect_setting_row(bag, accessor, name, descriptor, data, info, expand))
        if not rows:
            continue
        if data == "info":
            grouped: dict[str, list[dict]] = {}
            for row in rows:
                grouped.setdefault(row.pop("category", "root"), []).append(row)
            out[accessor] = grouped
        else:
            out[accessor] = rows
    return out


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
    description="Nodes (with ports) and edges of an open graph.",
    instructions=(
        "Nodes (with ports) and edges of an open graph. Pass detail=true for the full "
        "per-port setup (data_type, allow_multiple_links, is_linked, link_count, use_mode, "
        "promoted, has_widget, is_linked_lazy) AND per-edge health (is_functional, is_linked, "
        "is_lazy, adapter_chain, has_adapters, error); default returns the base id/direction/"
        "flow_type per port and id/topology/flow_type per edge."
    ),
    registry_id="query_graph",
    annotations=_READ_ONLY,
    access=AccessTier.VIEW,
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
        result = {
            "summary": (
                f"{total} nodes, {len(edges)} edges in {binding_id}."
                f"{truncation_note(len(page), total, offset)}"
            ),
            "nodes": page,
            "edges": edges,
            "total": total,
        }
        if page:
            result["help"] = (
                f"Run graph_editor_inspect_node binding_id={binding_id!r} node_id=<id> "
                f"get=['summary'] to survey one node's bags before pulling them"
                + ("." if detail else ", or re-run with detail=true for full port/edge health.")
            )
        else:
            result["help"] = (
                f"Graph is empty — run graph_editor_add_node binding_id={binding_id!r} "
                f"registry_key=<key> (find keys with studio_list_components kind=node)."
            )
        return result


_SECTIONS = ("summary", "node_id", "ports", "settings", "props", "state")
_DATA_LEVELS = ("info", "value", "all")
_DIRECTIONS = ("inlet", "outlet", "config")


@farmhand(
    label="Inspect node",
    description="One node's ports, settings, and health, at a chosen depth.",
    instructions="Drill down on ONE node in three steps — name only the sections and depth you "
    "need, because a node can carry 30+ settings fields and an unfocused call wastes most of "
    "what it returns. The read counterpart to graph_editor_set_property: a row's 'name' is "
    "exactly what you pass back as name=, and it joins a row across all depths.\n"
    "Typical drill-down: get=['summary'] (returns setting_counts per bag, so you can see which "
    "bags are big) -> get=['settings'] by_bag=['the_relevant_bag'] at data='info' to learn "
    "what exists -> data='value' or 'all' with by_name=['the_one_field'].\n"
    f"get: any of {', '.join(_SECTIONS)} (required, non-empty)\n"
    "  summary: always returned — identity, per-bag setting_counts, validity (name it alone for "
    "a cheap survey)\n"
    "  node_id: node_id + registry_key\n"
    "  ports: ports grouped as inlets/outlets/configs\n"
    "  settings: author-declared settings bags, nested {bag: {category: [rows]}} at data='info' "
    "and {bag: [rows]} deeper — never a flat list, so bag identity is always explicit\n"
    "  props: framework properties (position, size, muted, skin) — never mixed into settings\n"
    "  state: is_valid + per-stage lifecycle booleans + errors [{stage, message}] + warnings; "
    "read this after editing a node's source to learn WHICH stage failed\n"
    f"data: one of {', '.join(_DATA_LEVELS)} (default info) — how much per row\n"
    "  info: what it IS — label, description, category/data_type. NO values. Start here.\n"
    "  value: what it is SET to — value, is_set, default, is_linked\n"
    "  all: value plus everything writable — type, min/max/options, mirrors, ui_state, use_mode, "
    "validator\n"
    "Four independent filters, ANDed together (each defaults to [] = no constraint). Values that "
    "match nothing on this node come back under 'unmatched', keyed by which filter missed.\n"
    "  by_name: exact field or port names, e.g. ['confidence_threshold']\n"
    "  by_bag: settings-bag accessors, e.g. ['depth'] returns that whole bag (see the "
    "per-bag counts in summary to pick one)\n"
    "  by_category: author category labels, e.g. ['Exposure']\n"
    f"  by_dir: port directions, any of {', '.join(_DIRECTIONS)} — PORTS ONLY. Ports carry no bag "
    "or category, so by_bag/by_category exclude them outright; combining either with by_dir "
    "returns no ports and reports by_dir under 'unmatched'.\n"
    "Value notes: a port holding a non-JSON value (mesh, frame) reports value_omitted instead "
    "of value. A field hidden by its node's own gating (e.g. a disabled feature flag) is NOT "
    "shown to the user either, so it collapses to {name, ui_state:'hidden'} — name it in "
    "by_name to expand it. is_set=false means the field INHERITS its value — writing the "
    "same value back is a silent no-op. min/max are UI hints and are NOT enforced on writes. The "
    "validator IS enforced: at data='all' a field carrying one reports validator {name, doc} — "
    "the predicate is opaque, so you cannot pre-check a value, and a rejected write is dropped "
    "silently by the framework; set_property verifies the write and reports the rejection.",
    registry_id="inspect_node",
    annotations=_READ_ONLY,
    access=AccessTier.VIEW,
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
            "by_name": {"type": "array", "items": {"type": "string"}},
            "by_bag": {"type": "array", "items": {"type": "string"}},
            "by_category": {"type": "array", "items": {"type": "string"}},
            "by_dir": {"type": "array", "items": {"type": "string", "enum": list(_DIRECTIONS)}},
        },
        "required": ["binding_id", "node_id", "get"],
    }

    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        node_id: str,
        get: list[str] | None = None,
        data: str = "info",
        by_name: list[str] | None = None,
        by_bag: list[str] | None = None,
        by_category: list[str] | None = None,
        by_dir: list[str] | None = None,
    ) -> dict:
        # The published schema comes from input_schema_override above, so these
        # defaults are internal only — normalizing None here cannot change the
        # tool's advertised contract.
        by_name = by_name or []
        by_bag = by_bag or []
        by_category = by_category or []
        by_dir = by_dir or []

        editor = _editor(ctx, binding_id)
        wrapper = _node(editor, node_id)
        node = wrapper.node

        sections = list(dict.fromkeys(get or []))
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

        bad_dirs = [d for d in by_dir if d not in _DIRECTIONS]
        if bad_dirs:
            raise FarmhandError(
                "unknown_direction",
                f"Unknown by_dir value(s): {', '.join(bad_dirs)}. Valid: {', '.join(_DIRECTIONS)}.",
                ids={"node_id": node_id, "unknown": ",".join(bad_dirs)},
            )

        filters = _Filters(by_name, by_bag, by_category, by_dir)

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
                # Ports have no bag or category, so those axes exclude them
                # outright rather than matching everything. by_dir is then
                # left unhit on purpose: combining it with by_bag/by_category
                # is a caller confusion worth surfacing under 'unmatched',
                # not silently swallowing.
                if filters.bags or filters.cats:
                    continue
                direction = _port_direction(port)
                if filters.dirs:
                    if direction not in filters.dirs:
                        continue
                    filters.hit_dirs.add(direction)
                if pid in filters.names:
                    filters.hit_names.add(pid)
                elif filters.names:
                    continue
                bucket = {"inlet": "inlets", "outlet": "outlets"}.get(direction, "configs")
                groups[bucket].append(_inspect_port_row(pid, port, data, expand=pid in filters.names))
            result["ports"] = {k: v for k, v in groups.items() if v}
        if "settings" in sections:
            result["settings"] = _settings_payload(node, author_bags, data, filters)
        if "props" in sections:
            result["props"] = _settings_payload(node, [b for b in bags if b == "props"], data, filters)
        if "state" in sections:
            result["state"] = _state_row(wrapper)

        # A filter value that matched nothing is reported per-axis rather than
        # silently absent: "typo" and "does not exist" must not look identical
        # to an agent about to write.
        missing = filters.unmatched()
        if missing:
            result["unmatched"] = missing

        # summary is unconditional (canon: every result carries one) and is the
        # whole payload when it was the only section named. Per-bag counts turn
        # the survey call into an informed choice about what to fetch next —
        # without them, requesting 'settings' is all-or-nothing.
        bag_counts = {b: len(type(getattr(node, b))._property_settings()) for b in author_bags}
        n_settings = sum(bag_counts.values())
        result["setting_counts"] = bag_counts
        state = wrapper.state
        health = "valid" if state.is_valid() else "INVALID"
        n_errors = len(state.get_errors() or [])
        err_note = f", {n_errors} error(s)" if n_errors else ""
        warn = f", {len(state.warnings)} warning(s)" if state.warnings else ""
        bags_note = ", ".join(f"{b}: {n}" for b, n in bag_counts.items()) or "none"
        active = [
            f"{k}={v}"
            for k, v in (
                ("by_name", by_name),
                ("by_bag", by_bag),
                ("by_category", by_category),
                ("by_dir", by_dir),
            )
            if v
        ]
        scope = f" [{'; '.join(active)}]" if active else ""
        result["summary"] = (
            f"{wrapper.node_id} ({node.class_identity.registry_key}): "
            f"{len(node.ports)} port(s), {n_settings} setting(s) in {len(author_bags)} bag(s) "
            f"({bags_note}) — {health}{err_note}{warn}. "
            f"Returned: {', '.join(sections)} at data='{data}'{scope}."
        )
        return result


@farmhand(
    label="Add node",
    description="Add a node by registry key. Call studio_describe_component first to learn its ports.",
    instructions="Add a node instance to an open graph by registry_key, at an optional (x, y) "
    "canvas position (defaults near the origin). Call studio_describe_component or "
    "studio_list_components first to find a valid registry_key. Opens one undo fence and "
    "broadcasts to open studio UIs. Follow up with graph_editor_inspect_node to see the new "
    "node's ports/settings before wiring or setting them.",
    registry_id="add_node",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
                help="Run studio_list_components with kind=node to confirm the registry_key exists.",
            )
        ctx.broadcast(GraphDataMutated())
        return {
            "summary": f"Added {wrapper.node_id}.",
            "node_id": wrapper.node_id,
            "help": (
                f"Run graph_editor_inspect_node binding_id={binding_id!r} "
                f"node_id={wrapper.node_id!r} get=['ports','settings'] to see what to wire or set, "
                f"then graph_editor_connect."
            ),
        }


@farmhand(
    label="Connect",
    description="Connect an outlet to an inlet.",
    instructions="Create an edge from one node's outlet to another node's inlet, by exact pin "
    "id. Use graph_editor_inspect_node get=['ports'] on both endpoints first to find valid pin "
    "ids and confirm type compatibility — a bad id or an incompatible pair raises "
    "connect_failed. Opens one undo fence and broadcasts to open studio UIs on success.",
    registry_id="connect",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
                help=(
                    f"Run graph_editor_inspect_node node_id={source_node_id!r} get=['ports'] "
                    f"(and for {sink_node_id!r}) to see valid pin ids and their types."
                ),
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
    instructions="Remove nodes and/or edges from an open graph by id, in one call — pass "
    "nodes=[...] and/or edges=[...] (either or both, each defaults to empty). This is also how "
    "to disconnect two nodes: pass the edge_id under edges=. Removing a node also removes its "
    "own edges. Opens one undo fence and broadcasts to open studio UIs on success.",
    registry_id="remove_elements",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class GraphEditorRemoveElementsTool(Farmhand):
    async def run(
        self,
        ctx: FarmhandContext,
        binding_id: str,
        # noqa: B006 — this tool has no input_schema_override, so the signature
        # IS the published MCP schema: `[]` derives `"default": []`, while
        # `None` would derive `"default": null` and change the tool contract.
        # Both lists are read-only below, so the shared-default trap is inert.
        nodes: list[str] = [],  # noqa: B006
        edges: list[str] = [],  # noqa: B006
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
    instructions="Move one or more nodes to absolute canvas positions in a single call: "
    "positions={node_id: {x, y}, ...}. Positions are absolute, not deltas — read current "
    "positions with graph_editor_query_graph first if you need a relative move. Opens one undo "
    "fence and broadcasts to open studio UIs on success.",
    registry_id="move_nodes",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
    description="Set a node property (port value or settings field) by name. Undo-recorded.",
    instructions="Set a node property (port value or settings field) by name. Undo-recorded. "
    "'name' resolves to a port id first, then a settings field — use the exact 'name' from a "
    "graph_editor_inspect_node row. The write is verified by reading the value back: a value "
    "rejected by the field's validator raises set_rejected rather than reporting a success that "
    "did not happen. Note min/max are UI hints only and are NOT enforced — an out-of-range write "
    "succeeds, so respect the bounds inspect_node reports.",
    registry_id="set_property",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
)
class GraphEditorSetPropertyTool(Farmhand):
    async def run(
        self, ctx: FarmhandContext, binding_id: str, node_id: str, name: str, value: Any = None
    ) -> dict:
        editor = _editor(ctx, binding_id)
        ctx.fence(editor)
        ok = editor.set_property(node_id, name, value)
        if not ok:
            raise FarmhandError(
                "set_property_failed",
                f"Could not set '{name}' on node '{node_id}' (unknown node or property).",
                ids={"node_id": node_id, "name": name},
                help=(
                    f"Run graph_editor_inspect_node node_id={node_id!r} get=['ports','settings'] "
                    f"to see the writable property names."
                ),
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
                f"drops such writes silently).",
                ids={"node_id": node_id, "name": name},
                help=(
                    f"Run graph_editor_inspect_node node_id={node_id!r} get=['settings'] "
                    f"to see the field's type and constraints."
                ),
            )
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Set '{name}' on {node_id} to {actual!r}."}


@farmhand(
    label="Promote setting",
    description="Promote a settings field to a data port. Not undo-routed (UI parity; later work).",
    instructions="Promote a settings field to a live data port, so it can be wired instead of "
    "just set directly. accessor is the settings-bag accessor (e.g. 'depth') and field the "
    "field name within it — both come from a graph_editor_inspect_node settings row. direction "
    "is one of inlet/outlet/config (default inlet); an invalid direction raises bad_direction, "
    "and a field that can't be promoted raises not_promotable. NOT undo-routed — this does not "
    "join the undo timeline (UI parity gap, tracked for later work).",
    registry_id="promote_setting",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
        except KeyError as exc:
            raise FarmhandError(
                "bad_direction",
                f"direction must be one of inlet/outlet/config; got '{direction}'.",
                ids={"direction": direction},
            ) from exc
        node = _node(editor, node_id).node
        try:
            promote_setting(node, accessor, field, port_type)
        except ValueError as exc:
            raise FarmhandError(
                "not_promotable", str(exc), ids={"node_id": node_id, "field": field}
            ) from exc
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Promoted {accessor}.{field} on {node_id} as {direction}."}


@farmhand(
    label="Demote setting",
    description="Remove a promoted port, returning the field to a plain setting.",
    instructions="Reverse graph_editor_promote_setting: remove a promoted port by its port_id, "
    "returning the underlying field to a plain (non-port) setting. Any edges on that port are "
    "removed along with it. Broadcasts to open studio UIs on success.",
    registry_id="demote_setting",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
    instructions="Undo the last change on this graph's undo timeline — SHARED between the human "
    "editing in the studio UI and any agent calling these tools, so this can undo a change "
    "either one made. Returns performed=false with no error when there is nothing to undo. "
    "Broadcasts to open studio UIs only when a change was actually undone.",
    registry_id="undo",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
    instructions="Redo the last undone change on this graph's undo timeline — SHARED between "
    "the human editing in the studio UI and any agent calling these tools. Returns "
    "performed=false with no error when there is nothing to redo. Broadcasts to open studio "
    "UIs only when a change was actually redone.",
    registry_id="redo",
    annotations=_MUTATING,
    access=AccessTier.EDIT,
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
