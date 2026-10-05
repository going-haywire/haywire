"""An edge's style bag: bound while the edge validates, saved under "style", rebound on a new class."""

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.types import ChangeReason
from haywire.core.settings import EdgeSettings, setting

from tests.conftest import make_edge, make_node

pytestmark = pytest.mark.integration

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def graph(library_system) -> BaseGraph:
    return BaseGraph(filestem="Edge Style Graph", validation_scheduler=SyncScheduler())


def _probe_key() -> str:
    from haybale_testing.nodes.testbed.visual_probe import VisualProbeNode

    return VisualProbeNode.class_identity.registry_key


def _visual_edge(graph, **kwargs):
    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "note_in", **kwargs)
    graph.force_validation()
    return source, sink, edge


def test_a_styled_edge_has_a_bag_of_its_wire_types_class(graph):
    from haybale_testing.wires import TestVisualStyle

    _, _, edge = _visual_edge(graph)
    assert isinstance(edge.style, TestVisualStyle)
    assert edge.style._edge is edge


def test_a_computed_edge_has_no_bag(graph):
    a = make_node(graph, _ADD, position=(0, 0))
    b = make_node(graph, _ADD, position=(300, 0))
    edge = make_edge(graph, a.node_id, "result", b.node_id, "value_a")
    graph.force_validation()
    assert edge.style is None
    assert "style" not in edge.serialize()


def test_an_unset_style_saves_no_key(graph):
    _, _, edge = _visual_edge(graph)
    assert "style" not in edge.serialize()


def test_a_set_value_saves_and_loads(graph):
    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    edge.style.color = "#ff0000"
    assert edge.serialize()["style"] == {"color": "#ff0000"}

    data = graph.to_dict()
    loaded = BaseGraph(filestem="Loaded", validation_scheduler=SyncScheduler())
    assert loaded.load_from_dict(data)
    loaded.force_validation()
    from haybale_testing.wires import TestVisualStyle

    (reloaded,) = loaded.edge_wrappers.values()
    assert isinstance(reloaded.style, TestVisualStyle)
    assert reloaded.style.color == "#ff0000"


def test_a_style_passed_at_creation_is_bound(graph):
    _, _, edge = _visual_edge(graph, style={"width": 6.0, "unknown": 1})
    assert edge.style is not None
    assert edge.style.width == 6.0
    # Q26: a key the bag does not declare is skipped and gone at the next save.
    assert edge.serialize()["style"] == {"width": 6.0}


def test_a_failing_edge_keeps_its_style_verbatim_and_rebinds_it(graph):
    from haybale_testing.types import TEST_VISUAL

    source = make_node(graph, _probe_key(), position=(0, 0))
    sink = make_node(graph, _probe_key(), position=(300, 0))
    # The inlet does not exist yet: the edge fails formal validation ("Ports not found").
    edge = make_edge(graph, source.node_id, "note_out", sink.node_id, "late_in", style={"color": "#00ff00"})
    graph.force_validation()
    assert not edge.is_valid()
    assert edge.style is None
    assert edge.serialize()["style"] == {"color": "#00ff00"}

    sink.node.add(TEST_VISUAL.as_inlet("late_in"))
    graph.request_node_revalidation(sink.node_id)
    graph.force_validation()
    assert edge.is_valid()
    assert edge.style is not None
    assert edge.style.color == "#00ff00"


def test_a_new_bag_class_takes_the_old_values(graph, monkeypatch):
    from haybale_testing.wires import TestVisualWire

    from haywire.barn.builtin.types import COLOR

    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    edge.style.color = "#123456"
    edge.style.width = 4.0
    old_bag = edge.style

    class Narrower(EdgeSettings):
        color = setting[COLOR]("#000000", label="Colour")

    monkeypatch.setattr(TestVisualWire, "style", Narrower)
    graph.request_edge_revalidation(edge.edge_id)
    graph.force_validation()

    assert isinstance(edge.style, Narrower)
    assert edge.style is not old_bag
    assert edge.style.color == "#123456"
    assert edge.serialize()["style"] == {"color": "#123456"}, "width is not declared any more"
    assert old_bag._cleaned_up


def test_a_style_edit_marks_the_edge_style_changed(graph, monkeypatch):
    _, _, edge = _visual_edge(graph)
    assert edge.style is not None
    marks = []
    original = graph._validation.mark_edge_dirty

    def _record(edge_id, reason):
        marks.append(reason)
        original(edge_id, reason)

    monkeypatch.setattr(graph._validation, "mark_edge_dirty", _record)
    edge.style.dash = "dotted"
    assert ChangeReason.EDGE_STYLE_CHANGED in marks


def test_edge_style_changed_redraws_and_persists():
    reason = ChangeReason.EDGE_STYLE_CHANGED
    assert reason.requires_redraw()
    assert not reason.is_visual_only()


def test_cleanup_releases_the_bag(graph):
    _, _, edge = _visual_edge(graph)
    bag = edge.style
    assert bag is not None
    graph.remove_edge_wrapper(edge.edge_id)
    edge.cleanup()
    assert bag._cleaned_up
