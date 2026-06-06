"""NodeWrapperState carries advisory warnings, separate from errors."""

import haywire.core.graph.editor  # noqa: F401  circular-import guard (CLAUDE.md)

import pytest

from haywire.core.node.node_warning import NodeWarning
from haywire.core.node.node_wrapper import NodeWrapperState


@pytest.mark.unit
class TestNodeWrapperStateWarnings:
    def test_new_state_has_no_warnings(self):
        state = NodeWrapperState()
        assert state.warnings == []
        assert state.has_warning() is False

    def test_add_warning_records_it(self):
        state = NodeWrapperState()
        w = NodeWarning(message="old graph", source_version="0.0.13", kind="compatibility")
        state.add_warning(w)
        assert state.warnings == [w]
        assert state.has_warning() is True

    def test_warnings_do_not_affect_validity(self):
        # A warning must NOT make a node invalid (advisory only).
        state = NodeWrapperState(
            is_registered=True,
            is_imported=True,
            is_instantiated=True,
            is_initialized=True,
            is_structural=True,
            has_test_passed=True,
        )
        assert state.is_valid() is True
        state.add_warning(NodeWarning("x", None, "compatibility"))
        assert state.is_valid() is True

    def test_clear_warnings_empties_the_list(self):
        state = NodeWrapperState()
        state.add_warning(NodeWarning("x", None, "compatibility"))
        state.clear_warnings()
        assert state.warnings == []
        assert state.has_warning() is False
