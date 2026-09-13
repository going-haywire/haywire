"""A fold's header is a disclosure triangle, never a widget."""

from __future__ import annotations

import inspect

import pytest

pytestmark = pytest.mark.unit


def test_group_header_renders_no_widget() -> None:
    """A fold carries no widget; the header must not try to render one."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "render_widget" not in source


def test_group_header_emits_fold_attributes() -> None:
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "data-hw-fold-id" in source
    assert "data-hw-fold-open" in source


def test_group_header_states_the_boolean_with_a_checkbox() -> None:
    """A fold's value is a real boolean a node can read, so the header shows it
    as one — checked while open, since the value IS the open state."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "hui.icon.checked if is_expanded else hui.icon.unchecked" in source


def test_group_header_hosts_a_tooltip_off_its_triangle() -> None:
    """Hosted on the row, triggered by the triangle: a trigger must be small
    and must never be a layout container (see add_pin_tooltip)."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "add_pin_tooltip(header_row, group_port, trigger_el=triangle)" in source


def test_group_header_uses_the_central_icon_tokens() -> None:
    """Icons come from hui.icon.*, never raw Material strings."""
    from haybale_studio.skins.stacked_skin import StackedNodeSkin

    source = inspect.getsource(StackedNodeSkin._render_group)
    assert "fold_open" in source
    assert "fold_closed" in source


@pytest.fixture
def graph(library_system):
    from haywire.core.graph.base import BaseGraph
    from haywire.core.graph.scheduler import SyncScheduler

    return BaseGraph(filestem="fold toggle test", validation_scheduler=SyncScheduler())


@pytest.mark.integration
class TestToggleFold:
    """_toggle_fold must redraw unconditionally: most folds declare no
    on_change, so the click cannot depend on the node opting in to redraw
    itself (see set_value — on_change is the only path it drives a redraw
    through)."""

    def _add_node(self, graph_obj):
        from haybale_testing.nodes.testbed.fold_probe import FoldProbeNode

        return graph_obj.create_node_wrapper(FoldProbeNode.class_identity.registry_key, position=(100, 100))

    def test_toggle_flips_the_value(self, graph):
        from haybale_studio.skins.stacked_skin import StackedNodeSkin

        wrapper = self._add_node(graph)
        skin_instance = StackedNodeSkin.__new__(StackedNodeSkin)

        before = wrapper.node.value("inputs")
        skin_instance._toggle_fold(wrapper, "inputs")
        assert wrapper.node.value("inputs") is not before

    def test_toggle_redraws_even_without_on_change(self, graph, monkeypatch):
        """FoldProbeNode's folds declare no on_change — the redraw must not
        depend on it."""
        from haybale_studio.skins.stacked_skin import StackedNodeSkin

        wrapper = self._add_node(graph)
        assert wrapper.node.ports["inputs"].on_change is None, "fixture assumption: no on_change"

        skin_instance = StackedNodeSkin.__new__(StackedNodeSkin)

        redraw_calls = []
        monkeypatch.setattr(wrapper, "redraw", lambda: redraw_calls.append(True))

        skin_instance._toggle_fold(wrapper, "inputs")

        assert redraw_calls, "_toggle_fold must call wrapper.redraw() itself"
