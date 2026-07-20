# tests/ui/test_editor_wrapper_set_dirty.py

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


@pytest.mark.unit
def test_refresh_tab_bar_calls_slot_refresh_bar_without_touching_state():
    from haywire.ui.editor.wrapper import EditorWrapper, EditorWrapperState

    slot = MagicMock()
    w = EditorWrapper.__new__(EditorWrapper)
    w._state = EditorWrapperState()
    w._slot = slot

    w.refresh_tab_bar()

    slot._refresh_bar.assert_called_once()
    assert w._state.is_dirty is False  # pure repaint — no state change


@pytest.mark.unit
def test_refresh_tab_bar_noop_for_detached_wrapper():
    from haywire.ui.editor.wrapper import EditorWrapper, EditorWrapperState

    w = EditorWrapper.__new__(EditorWrapper)
    w._state = EditorWrapperState()
    w._slot = None

    w.refresh_tab_bar()  # must not raise
