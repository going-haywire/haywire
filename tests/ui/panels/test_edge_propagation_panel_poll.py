"""The edge inspector's propagation panel applies only to an edge that has propagation."""

from types import SimpleNamespace

import pytest

from haybale_graph_editor.panels.properties.introspect.edge import EdgePropagationPanel
from haybale_graph_editor.state.edit_state import EditState
from haywire.core.types import Propagation

pytestmark = pytest.mark.unit


def _ctx(edge):
    return SimpleNamespace(data={EditState: SimpleNamespace(active_edge=edge)})


def test_it_applies_to_an_edge_with_propagation():
    assert EdgePropagationPanel.poll(_ctx(SimpleNamespace(propagation=Propagation.EAGER)))


def test_it_does_not_apply_to_an_edge_without_propagation():
    assert not EdgePropagationPanel.poll(_ctx(SimpleNamespace(propagation=None)))


def test_it_does_not_apply_without_an_edge():
    assert not EdgePropagationPanel.poll(_ctx(None))
