"""The Ports panel mirrors the fold hierarchy and drags within one sibling group."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, cast

import pytest
from nicegui import Client, ui
from nicegui.elements.sortable.sortable import Sortable
from nicegui.page import page as page_deco

pytestmark = pytest.mark.unit


@page_deco("/_ports_panel_reorder_test")
def _noop_page() -> None:  # registration target for a headless Client
    pass


@dataclass
class _FakePort:
    """The attributes ``_render_lane`` reads off a port."""

    id: str
    label: str
    parent_group: str | None = None
    is_group: bool = False
    widget_key: str | None = None

    def should_show_widget(self) -> bool:
        return False


def _walk(element):
    yield element
    for child in element.default_slot.children:
        yield from _walk(child)


def _render_lane(ports: list[_FakePort], lane: str = "inlet"):
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        anchor = ui.column()
        with anchor:
            NodePortsPanel()._render_lane(object(), ports, lane, "n1", None)
    return anchor


def _sortables(anchor) -> list[Sortable]:
    # make_sortable parents its controller to client.layout, not to the
    # container, so the controller is reachable only through the container.
    return [
        e._sortable  # noqa: SLF001
        for e in _walk(anchor)
        if getattr(e, "_sortable", None) is not None
    ]


def test_panel_renders_lanes_recursively() -> None:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    assert hasattr(NodePortsPanel, "_render_lane")
    params = inspect.signature(NodePortsPanel._render_lane).parameters
    assert "parent_group" in params
    assert "depth" in params


def test_panel_is_fold_aware() -> None:
    """A flat panel cannot express a legal drop; it must read parent_group."""
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel)
    assert "parent_group" in source


def test_sortable_group_name_is_scoped_per_sibling_group() -> None:
    """Two sibling groups must never share a sortable group name.

    A shared name is what would let SortableJS move an inlet into the outlet
    lane — a drop the model cannot represent.
    """
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    a = NodePortsPanel._sortable_group("n1", "inlet", None)
    b = NodePortsPanel._sortable_group("n1", "outlet", None)
    c = NodePortsPanel._sortable_group("n1", "inlet", "solver")
    d = NodePortsPanel._sortable_group("n2", "inlet", None)
    assert len({a, b, c, d}) == 4


def test_panel_makes_lanes_sortable() -> None:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel)
    assert "make_sortable" in source
    assert "_on_reorder" in source


def test_importing_the_panel_registers_the_sortable_esm_module() -> None:
    """The importmap is written when a page is served.

    ``make_sortable`` imports the Sortable class at render time, which is after
    the page the user is looking at was built — its importmap then has no
    ``nicegui-sortable`` entry and the bare specifier fails to resolve in the
    browser. Importing the panel must be enough to register it.
    """
    import haybale_graph_editor.panels.properties.introspect.node_ports  # noqa: F401
    from nicegui import dependencies

    names = {m.name for m in dependencies.esm_modules.values()}
    assert "nicegui-sortable" in names


def test_each_row_drags_by_a_grip_only() -> None:
    """A whole-row drag would swallow every click into a port's widget."""
    from haywire.ui import elements as hui

    from haybale_graph_editor.panels.properties.introspect.node_ports import (
        _DRAG_HANDLE_CLASS,
        NodePortsPanel,
    )

    assert hui.icon.drag_handle
    source = inspect.getsource(NodePortsPanel._render_lane)
    # The grip is rendered AND named as the sortable's handle selector.
    assert "hui.icon.drag_handle" in source
    assert source.count("_DRAG_HANDLE_CLASS") == 2
    assert 'handle=f".{_DRAG_HANDLE_CLASS}"' in source
    assert _DRAG_HANDLE_CLASS.startswith("hw-")


def test_every_rendered_row_has_a_visible_grip() -> None:
    """The affordance is the feature: without a grip nothing says a row drags."""
    from haywire.ui import elements as hui

    from haybale_graph_editor.panels.properties.introspect.node_ports import _DRAG_HANDLE_CLASS

    anchor = _render_lane([_FakePort("a", "A"), _FakePort("b", "B")])
    grips = [
        e
        for e in _walk(anchor)
        if isinstance(e, ui.icon) and _DRAG_HANDLE_CLASS in e._classes  # noqa: SLF001
    ]
    assert len(grips) == 2
    assert all(g._props["name"] == hui.icon.drag_handle for g in grips)  # noqa: SLF001


def test_the_sortable_only_accepts_a_drag_from_the_grip() -> None:
    """Without `handle`, dragging a row would swallow clicks into its widget."""
    from haybale_graph_editor.panels.properties.introspect.node_ports import _DRAG_HANDLE_CLASS

    anchor = _render_lane([_FakePort("a", "A"), _FakePort("b", "B")])
    sortables = _sortables(anchor)
    assert len(sortables) == 1
    assert sortables[0].options["handle"] == f".{_DRAG_HANDLE_CLASS}"


def _labels(anchor) -> list[str]:
    """Every rendered label, in document order."""
    return [e.text for e in _walk(anchor) if isinstance(e, ui.label) and e.text]


def _two_folds() -> list[_FakePort]:
    """Two sibling folds, one child each — the FoldProbe config lane."""
    return [
        _FakePort("solver", "Solver", is_group=True),
        _FakePort("substeps", "Substeps", parent_group="solver"),
        _FakePort("advanced", "Advanced", is_group=True),
        _FakePort("epsilon", "Epsilon", parent_group="advanced"),
    ]


def test_each_folds_children_follow_that_fold() -> None:
    """A child must sit under its OWN fold, not under the last one rendered.

    A fold renders its label; a plain port renders as an id/type metadata row.
    """
    labels = _labels(_render_lane(_two_folds(), "config"))
    assert labels.index("substeps") < labels.index("Advanced")
    assert [t for t in labels if t != "—"] == ["Solver", "substeps", "Advanced", "epsilon"]


def test_a_fold_child_renders_once() -> None:
    """Rendering the children both inline and in a trailing pass duplicates them."""
    labels = _labels(_render_lane(_two_folds(), "config"))
    assert labels.count("substeps") == 1
    assert labels.count("epsilon") == 1


def test_a_fold_child_is_indented_below_its_fold() -> None:
    """Depth drives the child block's padding; a flat panel misreports the card."""
    anchor = _render_lane(_two_folds(), "config")
    pads = {
        e._style.get("padding-left")  # noqa: SLF001
        for e in _walk(anchor)
        if hasattr(e, "_style") and e._style.get("padding-left")  # noqa: SLF001
    }
    assert "0px" in pads
    assert "12px" in pads


def test_a_fold_child_renders_in_its_own_sortable() -> None:
    """A shared sortable is what would let a child be dropped out of its fold."""
    ports = [
        _FakePort("solver", "Solver", is_group=True),
        _FakePort("substeps", "Substeps", parent_group="solver"),
        _FakePort("a", "A"),
    ]
    anchor = _render_lane(ports)
    groups = {s.options["group"] for s in _sortables(anchor)}
    assert len(groups) == 2


def test_sibling_folds_each_get_their_own_sortable() -> None:
    """Root plus one per fold — two folds sharing a group would let a child cross."""
    groups = {s.options["group"] for s in _sortables(_render_lane(_two_folds(), "config"))}
    assert len(groups) == 3


def test_reorder_handler_reads_indices() -> None:
    from haybale_graph_editor.panels.properties.introspect.node_ports import NodePortsPanel

    source = inspect.getsource(NodePortsPanel._on_reorder)
    assert "old_index" in source
    assert "new_index" in source
    # The panel subscribes to GraphDataMutated; publishing one redraws the list
    # out from under the gesture.
    assert "GraphDataMutated" not in source
