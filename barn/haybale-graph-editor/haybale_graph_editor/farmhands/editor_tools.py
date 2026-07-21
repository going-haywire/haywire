"""graph_editor_* MCP tools: query, structural edits, set_property, promotion, shared undo/redo.

Every mutating tool opens exactly one undo fence FIRST (ctx.fence(editor)) so one
tool call is one undo gesture, then broadcasts GraphDataMutated after success.
undo/redo drive the SHARED human+agent timeline.
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


@farmhand(
    label="Set property",
    description="Set a node property (port value or settings field) by name. Undo-recorded.",
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
        ctx.broadcast(GraphDataMutated())
        return {"summary": f"Set '{name}' on {node_id}."}


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
