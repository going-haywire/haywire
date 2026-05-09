from __future__ import annotations

from haybale_studio.state.edit_state import EditState
from haywire.core.session.context import SessionContext
from haywire.ui.panel.focus import Focus


class AppFocus(Focus):
    id = "app"
    label = "Application"
    icon = "home"
    order = 10

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class ExecutionFocus(Focus):
    id = "execution"
    label = "Execution"
    icon = "rocket_launch"
    order = 20

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class CanvasFocus(Focus):
    id = "canvas"
    label = "Canvas & Nodes"
    icon = "grid_on"
    order = 30

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return True


class SettingsFocus(Focus):
    id = "settings"
    label = "Settings"
    icon = "tune"
    order = 65

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_node.value is not None


class GraphFocus(Focus):
    id = "graph"
    label = "Graph"
    icon = "polyline"
    order = 50

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_graph.value is not None


class NodeFocus(Focus):
    id = "node"
    label = "Node"
    icon = "account_tree"
    order = 60

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_node.value is not None


class EdgeFocus(Focus):
    id = "edge"
    label = "Edge"
    icon = "cable"
    order = 70

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_edge.value is not None


class PortFocus(Focus):
    id = "port"
    label = "Port"
    icon = "settings_input_component"
    order = 80

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        return ctx.data[EditState].active_port.value is not None


class SelectionFocus(Focus):
    id = "selection"
    label = "Selection"
    icon = "select_all"
    order = 90

    @classmethod
    def available(cls, ctx: SessionContext) -> bool:
        edit = ctx.data[EditState]
        return bool(edit.selected_nodes.value) or bool(edit.selected_edges.value)
