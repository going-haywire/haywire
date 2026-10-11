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


def test_access_tiers():
    assert Copy.access is AccessTier.VIEW
    assert SelectAll.access is AccessTier.VIEW
    assert Delete.access is AccessTier.EDIT


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
