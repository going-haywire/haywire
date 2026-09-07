"""Tests for the SelectionMenu "Edit…" submenu (Node / Skin / Theme).

The submenu mirrors the pin menu's: ungated navigation that resolves a
registry key and publishes ``RevealComponentSource``. ``poll`` is the
load-bearing half — the rows are single-node only (skin and theme resolve per
node), and each declines rather than pointing at something arbitrary.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from haywire.core.session.context import SessionContext
from haybale_graph_editor.panels.graph.menu.selection.selection import (
    EditSelectionMenuPanel,
    NodeSkinMenuPanel,
    NodeSourceMenuPanel,
    NodeThemeMenuPanel,
    _single_node,
)


def _ctx(
    *,
    nodes: set[str] | None = None,
    edges: set[str] | None = None,
    active_node: Any = None,
    default_skin: str = "",
) -> SessionContext:
    """A SessionContext whose EditState lookup yields the given selection.

    Mirrors ``test_session_context_menu_provider._make_provider``: the data
    namespace is stubbed so the lookup resolves regardless of the EditState
    class identity, which differs across a library hot-reload.
    """
    edit_stub = SimpleNamespace(
        selected_nodes=nodes if nodes is not None else set(),
        selected_edges=edges if edges is not None else set(),
        active_node=active_node,
    )
    fake_data = MagicMock()
    fake_data.__getitem__.return_value = edit_stub

    app = MagicMock()
    app.skin_factory._skin_registry.get_default_skin_registry_key.return_value = default_skin
    ctx = SessionContext(session_id="t", app=app)
    ctx.data = fake_data
    ctx.session = MagicMock()
    return ctx


def _wrapper(*, registry_key: str = "lib:node:Thing", skin: Any = None, node_theme: Any = None) -> Any:
    node = SimpleNamespace(
        props=SimpleNamespace(skin=skin, node_theme=node_theme),
        identity=SimpleNamespace(label="Thing"),
    )
    return SimpleNamespace(registry_key=registry_key, node=node)


# ---------------------------------------------------------------------------
# Single-node gating — shared by every row in the submenu
# ---------------------------------------------------------------------------


def test_single_node_requires_exactly_one_node():
    w = _wrapper()
    assert _single_node(_ctx(nodes={"a"}, active_node=w)) is w


def test_single_node_declines_a_multi_node_selection():
    """Skin and theme resolve per node, so several nodes have no one answer."""
    assert _single_node(_ctx(nodes={"a", "b"}, active_node=_wrapper())) is None


def test_single_node_declines_a_mixed_selection():
    assert _single_node(_ctx(nodes={"a"}, edges={"e"}, active_node=_wrapper())) is None


def test_single_node_declines_an_empty_selection():
    assert _single_node(_ctx()) is None


def test_edit_row_polls_with_the_single_node_rule():
    assert EditSelectionMenuPanel.poll(_ctx(nodes={"a"}, active_node=_wrapper())) is True
    assert EditSelectionMenuPanel.poll(_ctx(nodes={"a", "b"}, active_node=_wrapper())) is False


# ---------------------------------------------------------------------------
# Node row
# ---------------------------------------------------------------------------


def test_node_row_polls_true_for_one_selected_node():
    assert NodeSourceMenuPanel.poll(_ctx(nodes={"a"}, active_node=_wrapper())) is True


# ---------------------------------------------------------------------------
# Skin row
# ---------------------------------------------------------------------------


def test_skin_row_uses_the_nodes_own_skin_when_set():
    ctx = _ctx(nodes={"a"}, active_node=_wrapper(skin="lib:skin:Fancy"))
    assert NodeSkinMenuPanel._skin_key(ctx) == "lib:skin:Fancy"


def test_skin_row_falls_back_to_the_registry_default():
    """props.skin is None on every node that never overrode it — which is
    most of them — and the registry default is what actually draws the card,
    so the row must not vanish there."""
    ctx = _ctx(nodes={"a"}, active_node=_wrapper(skin=None), default_skin="core:skin:Default")
    assert NodeSkinMenuPanel._skin_key(ctx) == "core:skin:Default"
    assert NodeSkinMenuPanel.poll(ctx) is True


def test_skin_row_declines_when_nothing_resolves():
    ctx = _ctx(nodes={"a"}, active_node=_wrapper(skin=None), default_skin="")
    assert NodeSkinMenuPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# Theme row
# ---------------------------------------------------------------------------


def test_theme_row_reads_the_resolved_node_theme():
    ctx = _ctx(nodes={"a"}, active_node=_wrapper(node_theme="lib:nodetheme:Neon"))
    assert NodeThemeMenuPanel._theme_key(ctx) == "lib:nodetheme:Neon"
    assert NodeThemeMenuPanel.poll(ctx) is True


def test_theme_row_declines_with_no_node_theme():
    """An empty node_theme means the card takes its colours from the
    workbench theme — there is no node theme to open, unlike skin, which has
    a registry default standing behind it."""
    ctx = _ctx(nodes={"a"}, active_node=_wrapper(node_theme=None))
    assert NodeThemeMenuPanel.poll(ctx) is False


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------


def test_rows_are_ordered_node_skin_theme():
    orders = [
        NodeSourceMenuPanel.class_identity.order,
        NodeSkinMenuPanel.class_identity.order,
        NodeThemeMenuPanel.class_identity.order,
    ]
    assert orders == sorted(orders)
    assert len(set(orders)) == 3


def test_edit_row_sits_before_detail_on_the_parent_menu():
    from haybale_graph_editor.panels.graph.menu.selection.selection import (
        DetailSelectionMenuPanel,
    )

    assert EditSelectionMenuPanel.class_identity.order < DetailSelectionMenuPanel.class_identity.order
