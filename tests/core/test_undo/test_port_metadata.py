"""Editing a port's own presentation — its label, docs and default.

Distinct from ``SetPropertyAction``, which writes a port's *value*. Only a
``RESOLVED`` port may be edited: a ``DECLARED`` one is the node author's
contract, and a ``PROMOTED`` one is regenerated from its setting descriptor on
load, so an edit could not persist.
"""

from __future__ import annotations

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.editor import Editor
from haywire.core.types.enums import PortOrigin
from haywire.core.undo.actions.graph_actions import SetPortMetadataAction

from tests.conftest import make_node

pytestmark = [pytest.mark.integration]

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def node_with_a_resolved_port(graph_with_library_system: BaseGraph):
    """A node carrying one user-grown port and one the author declared."""
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)
    with wrapper.node.rejig():
        wrapper.node.add(
            FLOAT.as_inlet("grown", label="Grown", description="seeded", origin=PortOrigin.RESOLVED)
        )
        wrapper.node.add(FLOAT.as_inlet("authored", label="Authored", origin=PortOrigin.DECLARED))
    return graph, wrapper


class TestEditingAResolvedPort:
    def test_it_writes_the_label(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port

        action = SetPortMetadataAction(graph, wrapper.node_id, "grown", label="Confidence")
        action.execute()

        assert wrapper.node.ports["grown"].label == "Confidence"

    def test_it_writes_every_field_given(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port

        SetPortMetadataAction(
            graph,
            wrapper.node_id,
            "grown",
            label="Confidence",
            description="0 to 1",
            default={"value": 0.5},
        ).execute()

        port = wrapper.node.ports["grown"]
        assert port.label == "Confidence"
        assert port.description == "0 to 1"
        assert port.default == {"value": 0.5}

    def test_a_field_left_out_is_untouched(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port

        SetPortMetadataAction(graph, wrapper.node_id, "grown", label="Confidence").execute()

        assert wrapper.node.ports["grown"].description == "seeded"

    def test_the_edit_serializes(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port

        SetPortMetadataAction(graph, wrapper.node_id, "grown", label="Confidence").execute()

        assert wrapper.node.ports["grown"].to_dict()["kwargs"]["label"] == "Confidence"


class TestUndo:
    def test_undo_restores_every_field(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port
        action = SetPortMetadataAction(
            graph, wrapper.node_id, "grown", label="Confidence", description="0 to 1"
        )
        action.execute()

        action.undo()

        port = wrapper.node.ports["grown"]
        assert port.label == "Grown"
        assert port.description == "seeded"

    def test_one_gesture_is_one_undo_step(self, node_with_a_resolved_port, library_system):
        """A dialog applying three fields reverts in one Ctrl+Z."""
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())

        ok, reason = editor.set_port_metadata(
            wrapper.node_id, "grown", label="Confidence", description="0 to 1"
        )
        assert (ok, reason) == (True, None)

        editor.undo()

        port = wrapper.node.ports["grown"]
        assert port.label == "Grown"
        assert port.description == "seeded"

    def test_redo_reapplies_it(self, node_with_a_resolved_port, library_system):
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())
        editor.set_port_metadata(wrapper.node_id, "grown", label="Confidence")

        editor.undo()
        editor.redo()

        assert wrapper.node.ports["grown"].label == "Confidence"


class TestWhatIsRefused:
    def test_a_declared_port_is_refused(self, node_with_a_resolved_port):
        """The node author's contract — it appears in the component's docs.

        ``ActionBase.execute`` wraps the refusal in a ``RuntimeError``, so the
        reason travels in the message rather than the type.
        """
        graph, wrapper = node_with_a_resolved_port

        with pytest.raises(RuntimeError, match="not resolved"):
            SetPortMetadataAction(graph, wrapper.node_id, "authored", label="Mine").execute()

        assert wrapper.node.ports["authored"].label == "Authored"

    def test_the_refusal_reaches_the_caller_through_the_editor(
        self, node_with_a_resolved_port, library_system
    ):
        """The history manager swallows execute() failures, so the verb pre-flights."""
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())

        ok, reason = editor.set_port_metadata(wrapper.node_id, "authored", label="Mine")

        assert ok is False
        assert reason is not None
        assert wrapper.node.ports["authored"].label == "Authored"

    def test_a_refused_edit_records_no_undo_step(self, node_with_a_resolved_port, library_system):
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())

        editor.set_port_metadata(wrapper.node_id, "authored", label="Mine")

        assert editor.can_undo() is False

    def test_an_unknown_field_is_refused_at_construction(self, node_with_a_resolved_port):
        graph, wrapper = node_with_a_resolved_port

        with pytest.raises(ValueError, match="cannot write"):
            SetPortMetadataAction(graph, wrapper.node_id, "grown", widget_key="x")

    def test_an_unknown_port_is_reported(self, node_with_a_resolved_port, library_system):
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())

        ok, reason = editor.set_port_metadata(wrapper.node_id, "nobody", label="Mine")

        assert ok is False
        assert "nobody" in str(reason)


class TestTheEditIsPublished:
    """Writing the port is not enough — two surfaces have to be told.

    A rename changes no structure, so neither the canvas nor a Graph-node
    watching this Subgraph would otherwise hear about it. The node is marked
    ``NODE_VALIDATION_REQUESTED``, which is in the redraw set (the card
    rebuilds, taking its cached pin tooltips with it) and in the reassembly
    set (the card watching this definition reconciles).
    """

    def test_the_node_is_marked_for_a_redraw(self, node_with_a_resolved_port, library_system):
        graph, wrapper = node_with_a_resolved_port
        graph.force_validation()
        seen: list = []
        graph.subscribe_to_validation(lambda r: seen.append(dict(r.nodes)))

        Editor(graph, library_system.get_node_factory()).set_port_metadata(
            wrapper.node_id, "grown", label="Confidence"
        )
        graph.force_validation()

        reasons = [reason for batch in seen for reason in batch.values()]
        assert any(reason.requires_redraw() for reason in reasons)

    def test_the_reason_also_triggers_reassembly(self, node_with_a_resolved_port, library_system):
        """What a Graph-node's definition watcher gates on."""
        graph, wrapper = node_with_a_resolved_port
        graph.force_validation()
        seen: list = []
        graph.subscribe_to_validation(lambda r: seen.append(dict(r.nodes)))

        Editor(graph, library_system.get_node_factory()).set_port_metadata(
            wrapper.node_id, "grown", label="Confidence"
        )
        graph.force_validation()

        reasons = [reason for batch in seen for reason in batch.values()]
        assert any(reason.requires_graph_reassembly() for reason in reasons)

    def test_it_publishes_even_when_the_node_is_already_dirty(
        self, node_with_a_resolved_port, library_system
    ):
        """The wrapper's mark_as_structuraly_dirty no-ops while the node's own
        flag is still set from an earlier rejig — and that flag is cleared by
        the very housekeeping pass this call is trying to cause."""
        graph, wrapper = node_with_a_resolved_port
        assert wrapper._is_dirty_structural is True  # left set by the fixture's rejig
        seen: list = []
        graph.subscribe_to_validation(lambda r: seen.append(dict(r.nodes)))

        Editor(graph, library_system.get_node_factory()).set_port_metadata(
            wrapper.node_id, "grown", label="Confidence"
        )
        graph.force_validation()

        assert any(wrapper.node_id in batch for batch in seen)

    def test_undo_publishes_too(self, node_with_a_resolved_port, library_system):
        """Reverting the name must repaint the card the same way."""
        graph, wrapper = node_with_a_resolved_port
        editor = Editor(graph, library_system.get_node_factory())
        editor.set_port_metadata(wrapper.node_id, "grown", label="Confidence")
        graph.force_validation()
        seen: list = []
        graph.subscribe_to_validation(lambda r: seen.append(dict(r.nodes)))

        editor.undo()
        graph.force_validation()

        assert wrapper.node.ports["grown"].label == "Grown"
        assert any(wrapper.node_id in batch for batch in seen)
