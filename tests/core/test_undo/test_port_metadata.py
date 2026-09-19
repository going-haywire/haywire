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
