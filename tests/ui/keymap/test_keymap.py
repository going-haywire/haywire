"""A keymap is derived from the EditorCommands each editor class subscribes to."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, ClassVar
from unittest.mock import MagicMock, patch

from haywire.core.access.tier import AccessTier
from haywire.core.session.handlers import react_on, redraw_on
from haywire.core.signals import Copy, EditorCommand, Paste, Redo, Signal, Undo
from haywire.ui.keymap import (
    KeymapClash,
    KeymapEntry,
    build_keymap,
    report_keymap_problems,
    report_new_keymap_problems,
    reset_reported_keymap_problems,
)


def _identity(label: str) -> Any:
    return SimpleNamespace(registry_key=f"test:{label}", label=label)


def _always(_tier: AccessTier) -> bool:
    return True


@dataclass(frozen=True)
class _Plain(Signal):
    pass


@dataclass(frozen=True, kw_only=True)
class _OwnK(EditorCommand):
    command_id: ClassVar[str] = "zzz.own_k"
    label: ClassVar[str] = "Own K"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+K",)


@dataclass(frozen=True, kw_only=True)
class _ForeignK(EditorCommand):
    command_id: ClassVar[str] = "aaa.foreign_k"
    label: ClassVar[str] = "Foreign K"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+K",)


# The clash rule compares top-level packages; place the two K commands in different ones.
_OwnK.__module__ = "lib_a.commands"
_ForeignK.__module__ = "lib_b.commands"


@dataclass(frozen=True, kw_only=True)
class _CloseTab(EditorCommand):
    command_id: ClassVar[str] = "test.close_tab"
    label: ClassVar[str] = "Close Tab"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+W",)


@dataclass(frozen=True, kw_only=True)
class _DupA(EditorCommand):
    command_id: ClassVar[str] = "test.dup"
    label: ClassVar[str] = "Dup A"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+J",)


@dataclass(frozen=True, kw_only=True)
class _DupB(EditorCommand):
    command_id: ClassVar[str] = "test.dup"
    label: ClassVar[str] = "Dup B"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+L",)


class _CopyRedoEditor:
    class_identity = _identity("Copy Redo")

    @react_on(Copy)
    def _on_copy(self, ctx, signal): ...

    @redraw_on(Redo, _Plain)
    def _on_redo(self, ctx, signal): ...


class _PlainEditor:
    class_identity = _identity("Plain")

    @react_on(_Plain)
    def _on_plain(self, ctx, signal): ...


class _CopyUndoEditor:
    class_identity = _identity("Copy Undo")

    @react_on(Copy, Undo)
    def _on_command(self, ctx, signal): ...


class _LibAEditor:
    __module__ = "lib_a.editors"
    class_identity = _identity("Lib A")

    @react_on(_ForeignK, _OwnK)
    def _on_k(self, ctx, signal): ...


class _LibCEditor:
    __module__ = "lib_c.editors"
    class_identity = _identity("Lib C")

    @react_on(_OwnK, _ForeignK)
    def _on_k(self, ctx, signal): ...


class _ReservedEditor:
    class_identity = _identity("Reserved")

    @react_on(_CloseTab, Copy)
    def _on_command(self, ctx, signal): ...


class _DupAEditor:
    class_identity = _identity("Dup A Editor")

    @react_on(_DupA, Copy)
    def _on_command(self, ctx, signal): ...


class _DupBEditor:
    class_identity = _identity("Dup B Editor")

    @react_on(_DupB)
    def _on_command(self, ctx, signal): ...


class _PasteEditor:
    class_identity = _identity("Paste Editor")

    @react_on(Copy, Paste)
    def _on_command(self, ctx, signal): ...


class _NoIdentityEditor:
    @react_on(Copy)
    def _on_copy(self, ctx, signal): ...


def test_editor_claims_keys_of_subscribed_commands():
    keymap = build_keymap({"ed": _CopyRedoEditor}, _always)

    entries = keymap.editors["ed"]
    assert set(entries) == {"Mod+C", "Mod+Shift+Z", "Mod+Y"}
    assert entries["Mod+C"] == KeymapEntry(combo="Mod+C", command=Copy)
    assert entries["Mod+Shift+Z"].command is Redo
    assert entries["Mod+Y"].command is Redo
    assert keymap.commands == {"copy": Copy, "redo": Redo}
    assert keymap.editor_labels == {"ed": "Copy Redo"}
    assert keymap.editor_commands("ed") == [Copy, Redo]


def test_unsubscribed_editor_claims_nothing():
    keymap = build_keymap({"ed": _CopyRedoEditor, "plain": _PlainEditor}, _always)

    assert "plain" not in keymap.editors
    assert "plain" not in keymap.editor_labels
    assert keymap.editor_commands("plain") == []


def test_below_tier_command_not_claimed():
    keymap = build_keymap({"ed": _CopyUndoEditor}, lambda tier: tier is AccessTier.VIEW)

    assert "Mod+Z" not in keymap.editors["ed"]
    assert "Mod+C" in keymap.editors["ed"]
    assert "undo" not in keymap.commands


def test_clash_prefers_own_library_then_command_id():
    own = build_keymap({"ed": _LibAEditor}, _always)
    assert own.editors["ed"]["Mod+K"].command is _OwnK
    assert own.clashes == (KeymapClash(editor_key="ed", combo="Mod+K", winner=_OwnK, losers=(_ForeignK,)),)

    neither = build_keymap({"ed": _LibCEditor}, _always)
    assert neither.editors["ed"]["Mod+K"].command is _ForeignK
    assert neither.clashes == (
        KeymapClash(editor_key="ed", combo="Mod+K", winner=_ForeignK, losers=(_OwnK,)),
    )
    # A losing command stays listed for the editor so its row can show the clash.
    assert neither.editor_commands("ed") == [_ForeignK, _OwnK]


def test_reserved_combo_recorded_not_claimed():
    keymap = build_keymap({"ed": _ReservedEditor}, _always)

    assert "Mod+W" not in keymap.editors["ed"]
    assert keymap.reserved == (("Mod+W", _CloseTab),)
    assert keymap.clashes == ()


def test_reserved_only_editor_is_absent():
    class _OnlyReserved:
        class_identity = _identity("Only Reserved")

        @react_on(_CloseTab)
        def _on_close(self, ctx, signal): ...

    keymap = build_keymap({"ed": _OnlyReserved}, _always)

    assert keymap.editors == {}
    assert keymap.reserved == (("Mod+W", _CloseTab),)


def test_duplicate_command_id_excluded():
    keymap = build_keymap({"a": _DupAEditor, "b": _DupBEditor}, _always)

    assert keymap.duplicate_ids == (("test.dup", (_DupA, _DupB)),)
    assert "test.dup" not in keymap.commands
    assert set(keymap.editors["a"]) == {"Mod+C"}
    assert "b" not in keymap.editors


def test_editor_without_identity_labelled_by_key():
    keymap = build_keymap({"bare": _NoIdentityEditor}, _always)

    assert keymap.editor_labels == {"bare": "bare"}


def test_to_client_shape():
    keymap = build_keymap({"ed": _PasteEditor}, _always)

    assert keymap.to_client() == {
        "editors": {"ed": {"Mod+C": "copy", "Mod+V": "paste"}},
        "native": {"paste": "paste"},
    }


def test_report_logs_each_problem():
    keymap = build_keymap(
        {"k": _LibCEditor, "r": _ReservedEditor, "a": _DupAEditor, "b": _DupBEditor},
        _always,
    )
    assert len(keymap.clashes) == 1
    assert len(keymap.reserved) == 1
    assert len(keymap.duplicate_ids) == 1

    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        report_keymap_problems(keymap)

    recorded = [call.args[0] for call in ledger.record.call_args_list]
    assert len(recorded) == 3
    assert all(e.category == "Keyboard Shortcuts" for e in recorded)
    assert all(e.is_warning() for e in recorded)
    messages = " | ".join(e.message for e in recorded)
    assert "Mod+K" in messages
    assert "Mod+W" in messages
    assert "test.dup" in messages


def test_report_clean_keymap_logs_nothing():
    keymap = build_keymap({"ed": _CopyRedoEditor}, _always)

    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        report_keymap_problems(keymap)

    ledger.record.assert_not_called()


def _recorded_messages(ledger: MagicMock) -> list[str]:
    return [call.args[0].message for call in ledger.record.call_args_list]


def test_report_new_logs_each_problem_once_per_process():
    reset_reported_keymap_problems()
    keymap = build_keymap({"k": _LibCEditor, "r": _ReservedEditor}, _always)

    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        report_new_keymap_problems(keymap)
        report_new_keymap_problems(build_keymap({"k": _LibCEditor, "r": _ReservedEditor}, _always))

    assert len(_recorded_messages(ledger)) == 2
    reset_reported_keymap_problems()


def test_report_new_logs_only_problems_not_yet_reported():
    reset_reported_keymap_problems()
    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        report_new_keymap_problems(build_keymap({"r": _ReservedEditor}, _always))
        report_new_keymap_problems(
            build_keymap({"r": _ReservedEditor, "a": _DupAEditor, "b": _DupBEditor}, _always)
        )

    messages = _recorded_messages(ledger)
    assert len(messages) == 2
    assert "Mod+W" in messages[0]
    assert "test.dup" in messages[1]
    reset_reported_keymap_problems()


def test_reset_reported_problems_reports_again():
    reset_reported_keymap_problems()
    keymap = build_keymap({"r": _ReservedEditor}, _always)
    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        report_new_keymap_problems(keymap)
        reset_reported_keymap_problems()
        report_new_keymap_problems(keymap)

    assert len(_recorded_messages(ledger)) == 2
    reset_reported_keymap_problems()
