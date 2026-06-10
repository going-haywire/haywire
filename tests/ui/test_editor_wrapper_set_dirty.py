# tests/ui/test_editor_wrapper_set_dirty.py
import haywire.core.graph.editor  # noqa: F401  (circular-import guard, CLAUDE.md)

from unittest.mock import MagicMock
import pytest


@pytest.mark.unit
def test_set_dirty_refresh_true_calls_slot_refresh_bar():
    from haywire.ui.editor.wrapper import EditorWrapper, EditorWrapperState

    slot = MagicMock()
    w = EditorWrapper.__new__(EditorWrapper)  # avoid full ctor
    w._state = EditorWrapperState()
    w._slot = slot

    w.set_dirty(True, refresh=True)

    assert w._state.is_dirty is True
    slot._refresh_bar.assert_called_once()


@pytest.mark.unit
def test_set_dirty_default_is_lazy():
    from haywire.ui.editor.wrapper import EditorWrapper, EditorWrapperState

    slot = MagicMock()
    w = EditorWrapper.__new__(EditorWrapper)
    w._state = EditorWrapperState()
    w._slot = slot

    w.set_dirty(True)  # no refresh kwarg

    slot._refresh_bar.assert_not_called()  # lazy default preserved
