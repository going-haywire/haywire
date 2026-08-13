# barn/haybale-graph-editor/haybale_graph_editor/panels/properties/introspect/node.py
"""
Node introspection panels — identity info, instance properties, status, and errors.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel, PanelLayout
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.render_utils import render_settings

from ....focuses import NodeFocus
from ....state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    focus=NodeFocus,
    label="Node Properties",
    icon=hui.icon.node_info,
    default_open=False,
    order=10,
)
class NodeInfoPanel(BasePanel):
    """Displays basic identity information for the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        try:
            label = node.node.identity.label if hasattr(node, "node") else str(node)
            cls_name = node.node.__class__.__name__ if hasattr(node, "node") else type(node).__name__
            node_id = getattr(node, "node_id", str(node))
        except Exception:
            label, cls_name, node_id = "?", "?", "?"
        with layout:
            hui.info_row("Name", str(label))
            hui.info_row("Class", str(cls_name))
            hui.info_row("ID", str(node_id))


@panel(
    focus=NodeFocus,
    label="Node Properties",
    icon=hui.icon.node,
    order=20,
    default_open=True,
)
class NodePropertiesPanel(BasePanel):
    """Displays per-instance node settings (muted, collapsed, pinned, etc.)."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        node = ctx.data[EditState].active_node
        return (
            node is not None
            and hasattr(node, "node")
            and node.node is not None
            and hasattr(node.node, "props")
        )

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node_wrapper = ctx.data[EditState].active_node
        if node_wrapper is None:
            return
        render_settings(node_wrapper.node.props)


@panel(
    focus=NodeFocus,
    label="Status",
    icon=hui.icon.node_status,
    order=30,
    default_open=False,
)
class NodeStatusPanel(BasePanel):
    """Displays the validation and lifecycle status of the selected node."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return ctx.data[EditState].active_node is not None

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        node = ctx.data[EditState].active_node
        if node is None:
            return
        with layout:
            try:
                wrapper_state = getattr(node, "state", None)
                if wrapper_state is None:
                    hui.empty_state("No state available", icon=hui.icon.node_status)
                    return

                _is_valid_fn = getattr(wrapper_state, "is_valid", None)
                is_valid = wrapper_state.is_valid() if callable(_is_valid_fn) else "?"
                hui.info_row("Valid", str(is_valid))
                hui.info_row("Registered", str(getattr(wrapper_state, "is_registered", "?")))
                hui.info_row("Initialized", str(getattr(wrapper_state, "is_initialized", "?")))
                hui.info_row("Structural", str(getattr(wrapper_state, "is_structural", "?")))
                hui.info_row("Tested", str(getattr(wrapper_state, "has_test_passed", "?")))

                _get_errors_fn = getattr(wrapper_state, "get_errors", None)
                errors = wrapper_state.get_errors() if callable(_get_errors_fn) else None
                if errors:
                    hui.section_label("Errors")
                    for err in errors:
                        hui.error_label(str(err))

            except Exception:
                hui.error_label("Error reading status")


def _node_has_errors(ctx: "SessionContext") -> bool:
    node = ctx.data[EditState].active_node
    return node is not None and bool(node.state.get_errors())


def _render_node_errors(ctx: "SessionContext", layout: PanelLayout) -> None:
    from haywire.ui.errors.error_info import error_render_detail

    node = ctx.data[EditState].active_node
    if node is None:
        return
    errors = node.state.get_errors()
    if not errors:
        return
    with layout.container:
        for error in errors:
            error_render_detail(error)


@panel(
    focus=NodeFocus,
    label="Node Errors",
    icon=hui.icon.error,
    order=0,
)
class NodeErrorsPanel(BasePanel):
    """Node errors panel for PropertiesEditor."""

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return _node_has_errors(ctx)

    def draw(
        self,
        ctx: "SessionContext",
        layout: PanelLayout,
    ) -> None:
        _render_node_errors(ctx, layout)
