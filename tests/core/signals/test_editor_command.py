"""EditorCommand base and the core editor-command vocabulary."""

import pytest

from haywire.core.access.tier import AccessTier
from haywire.core.signals import CommandSignal
from haywire.core.signals.keys import normalize_combo
from haywire.core.signals.signal import EditorCommand
from haywire.core.signals.vocabulary import (
    Copy,
    Cut,
    Delete,
    Duplicate,
    Paste,
    Redo,
    SelectAll,
    Undo,
)

COMMANDS = [Copy, Cut, Paste, Duplicate, Delete, Undo, Redo, SelectAll]


def test_command_ids_are_unique():
    ids = [c.command_id for c in COMMANDS]
    assert len(set(ids)) == len(ids)


@pytest.mark.parametrize("cmd", COMMANDS)
def test_default_keys_are_normalized(cmd):
    for key in cmd.default_keys:
        assert key == normalize_combo(key)


@pytest.mark.parametrize("cmd", COMMANDS)
def test_commands_are_editor_commands(cmd):
    assert issubclass(cmd, EditorCommand)
    assert issubclass(cmd, CommandSignal)


def test_a_command_requires_edit_by_default():
    assert EditorCommand.requires is AccessTier.EDIT


def test_access_requirements():
    assert Copy.requires is AccessTier.VIEW
    assert SelectAll.requires is AccessTier.VIEW
    assert Delete.requires is AccessTier.EDIT


def test_paste_carries_text_and_native_event():
    assert Paste(binding_id="b", text="x").text == "x"
    assert Paste(binding_id="b").text == ""
    assert Paste.native_event == "paste"
    assert Copy.native_event is None


def test_position_defaults_to_none():
    assert Copy(binding_id="b").position is None
    assert Copy(binding_id="b", position=(1.0, 2.0)).position == (1.0, 2.0)


def test_binding_id_is_required():
    with pytest.raises(TypeError):
        Copy()  # type: ignore[call-arg]


def test_toggle_lock_identity():
    from haywire.core.signals.vocabulary import ToggleLock

    assert ToggleLock.command_id == "toggle_lock"
    assert ToggleLock.label == "Lock / Unlock"
    assert ToggleLock.default_keys == ("Mod+E",)
    assert ToggleLock.requires is AccessTier.EDIT


def test_toggle_stage_view_identity():
    from haywire.core.signals.keys import RESERVED_COMBOS
    from haywire.core.signals.vocabulary import ToggleStageView

    assert ToggleStageView.command_id == "toggle_stage_view"
    assert ToggleStageView.label == "Patch / Stage"
    assert ToggleStageView.default_keys == ("Mod+Shift+E",)
    assert ToggleStageView.requires is AccessTier.VIEW
    assert not set(ToggleStageView.default_keys) & RESERVED_COMBOS


def test_the_graph_editor_keymap_binds_toggle_stage_view_without_conflict():
    from haybale_graph_editor.editors.graph_editor import GraphEditor
    from haywire.core.signals.vocabulary import ToggleStageView
    from haywire.ui.keymap import build_keymap

    keymap = build_keymap({"graph": GraphEditor}, lambda tier: True)

    assert ToggleStageView in keymap.editor_commands("graph")
    assert (keymap.reserved, keymap.invalid, keymap.duplicate_ids) == ((), (), ())


def test_save_is_an_edit_command_that_fires_in_text_fields():
    from haywire.core.access.tier import AccessTier
    from haywire.core.signals import EditorCommand, Save

    assert issubclass(Save, EditorCommand)
    assert (Save.command_id, Save.label, Save.default_keys) == ("save", "Save", ("Mod+S",))
    assert Save.requires is AccessTier.EDIT
    assert Save.in_text_fields is True
    assert EditorCommand.in_text_fields is False
