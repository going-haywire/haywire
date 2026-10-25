"""AppShell keyboard shortcuts: the page's key listener, the session keymap, published commands."""

from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, ClassVar, cast
from unittest.mock import MagicMock, patch

import pytest
from nicegui import Client

from haywire.core.access.tier import AccessTier
from haywire.core.session.handlers import react_on
from haywire.core.signals import Copy, EditorCommand, Paste, RosterChanged
from haywire.ui.app.shell import AppShell
from haywire.ui.components.keymap import KeymapListener
from haywire.ui.keymap import reset_reported_keymap_problems


def _noop_page() -> None:  # registration target for a headless Client
    pass


@dataclass(frozen=True, kw_only=True)
class _ReservedClose(EditorCommand):
    command_id: ClassVar[str] = "test.reserved_close"
    label: ClassVar[str] = "Reserved Close"
    default_keys: ClassVar[tuple[str, ...]] = ("Mod+W",)


class _ClipboardEditor:
    class_identity = SimpleNamespace(registry_key="test:clipboard", label="Clipboard")

    @react_on(Copy, Paste)
    def _on_command(self, ctx, signal): ...


class _ReservedEditor:
    class_identity = SimpleNamespace(registry_key="test:reserved", label="Reserved")

    @react_on(_ReservedClose)
    def _on_command(self, ctx, signal): ...


class _FakeSession:
    def __init__(self, can_access: Callable[[AccessTier], bool] = lambda _tier: True) -> None:
        self.context = SimpleNamespace(can_access=can_access, keymap=None, target_binding_id=None)
        self.published: list = []
        self.subscriptions: dict[type, list[Callable]] = {}

    def subscribe(self, signal_type: type, handler: Callable) -> Callable[[], None]:
        self.subscriptions.setdefault(signal_type, []).append(handler)
        return lambda: self.subscriptions[signal_type].remove(handler)

    def publish(self, signal: Any) -> None:
        self.published.append(signal)
        for handler in list(self.subscriptions.get(type(signal), [])):
            handler(signal)


class _FakeEditorRegistry:
    def __init__(self, classes: dict[str, type]) -> None:
        self.classes = classes
        self.batch_subscribers: list[Callable] = []

    def list_names(self) -> list[str]:
        return list(self.classes)

    def get(self, key: str) -> type | None:
        return self.classes.get(key)

    def add_batch_event_subscriber(self, callback: Callable) -> None:
        if callback not in self.batch_subscribers:
            self.batch_subscribers.append(callback)

    def remove_batch_event_subscriber(self, callback: Callable) -> None:
        if callback in self.batch_subscribers:
            self.batch_subscribers.remove(callback)

    def fire(self) -> None:
        for callback in list(self.batch_subscribers):
            callback([])


@pytest.fixture(autouse=True)
def _fresh_problem_reports():
    reset_reported_keymap_problems()
    yield
    reset_reported_keymap_problems()


def _shell(session: _FakeSession | None = None, registry: _FakeEditorRegistry | None = None) -> AppShell:
    return AppShell(
        session=cast(Any, session or _FakeSession()),
        editor_registry=cast(Any, registry or _FakeEditorRegistry({"ed": _ClipboardEditor})),
    )


def _mount(shell: AppShell) -> None:
    """Mount the shell's key listener into a headless page."""
    with Client(cast(Any, _noop_page), request=None):
        shell._mount_keymap_listener()


def _mounted_shell(
    session: _FakeSession | None = None, registry: _FakeEditorRegistry | None = None
) -> AppShell:
    shell = _shell(session, registry)
    _mount(shell)
    return shell


# ---------------------------------------------------------------------------
# Browser -> bus
# ---------------------------------------------------------------------------


def test_key_command_publishes_editor_command() -> None:
    session = _FakeSession()
    shell = _mounted_shell(session)

    shell._on_key_command({"command_id": "copy", "binding_id": "ed::a", "position": None, "text": ""})

    assert session.published[-1] == Copy(binding_id="ed::a")


def test_paste_carries_text_and_position() -> None:
    session = _FakeSession()
    shell = _mounted_shell(session)

    shell._on_key_command({"command_id": "paste", "binding_id": "ed::a", "position": [1, 2], "text": "t"})

    assert session.published[-1] == Paste(binding_id="ed::a", position=(1.0, 2.0), text="t")


def test_unknown_command_id_ignored() -> None:
    session = _FakeSession()
    shell = _mounted_shell(session)
    before = list(session.published)

    shell._on_key_command({"command_id": "nope", "binding_id": "ed::a", "position": None, "text": ""})

    assert session.published == before


@pytest.mark.parametrize("position", [[], [1], [1, 2, 3], ["a", "b"], [True, 2], "12", {"x": 1}, 5])
def test_malformed_position_becomes_none(position: Any) -> None:
    session = _FakeSession()
    shell = _mounted_shell(session)

    shell._on_key_command({"command_id": "paste", "binding_id": "ed::a", "position": position, "text": "t"})

    assert session.published[-1] == Paste(binding_id="ed::a", position=None, text="t")


def test_denied_key_command_is_refused_with_a_notice() -> None:
    session = _FakeSession(can_access=lambda tier: tier is AccessTier.VIEW)
    shell = _mounted_shell(session)

    with patch("haywire.ui.app.shell.ui.notify") as notify:
        shell._on_key_command({"command_id": "paste", "binding_id": "ed::a", "position": None, "text": "t"})

    assert session.published == []
    notify.assert_called_once_with("Paste needs edit access", type="warning")


def test_key_command_before_mount_ignored() -> None:
    session = _FakeSession()
    shell = _shell(session)

    shell._on_key_command({"command_id": "copy", "binding_id": "ed::a", "position": None, "text": ""})

    assert session.published == []


def test_key_target_sets_context() -> None:
    session = _FakeSession()
    shell = _mounted_shell(session)

    shell._on_key_target({"binding_id": "ed::b"})

    assert session.context.target_binding_id == "ed::b"


# ---------------------------------------------------------------------------
# Keymap kept current
# ---------------------------------------------------------------------------


def test_mount_builds_keymap_into_context_and_listener() -> None:
    session = _FakeSession()
    with patch.object(KeymapListener, "set_keymap") as set_keymap:
        _mounted_shell(session)

    assert session.context.keymap is not None
    assert set(session.context.keymap.commands) == {"copy", "paste"}
    set_keymap.assert_called_once_with(session.context.keymap.to_client())


def test_keymap_filtered_by_session_tier() -> None:
    session = _FakeSession(can_access=lambda tier: tier is AccessTier.VIEW)
    _mounted_shell(session)

    assert set(session.context.keymap.commands) == {"copy"}


def test_keymap_rebuilt_on_editor_reload() -> None:
    registry = _FakeEditorRegistry({"ed": _ClipboardEditor})
    session = _FakeSession()
    with patch.object(KeymapListener, "set_keymap") as set_keymap:
        _mounted_shell(session, registry)
        registry.classes = {}
        registry.fire()

    assert set_keymap.call_count == 2
    assert set_keymap.call_args.args[0] == {"editors": {}, "native": {}, "text_fields": []}
    assert session.context.keymap.commands == {}


def test_reload_batch_off_the_loop_rebuilds_on_the_loop() -> None:
    registry = _FakeEditorRegistry({"ed": _ClipboardEditor})
    session = _FakeSession()
    rebuild_threads: list[int] = []

    def record_thread(_client_keymap: Any) -> None:
        rebuild_threads.append(threading.get_ident())

    async def mount_then_reload_from_watcher_thread() -> tuple[list[int], int]:
        with patch.object(KeymapListener, "set_keymap", side_effect=record_thread):
            _mounted_shell(session, registry)
            registry.classes = {}
            watcher = threading.Thread(target=registry.fire)
            watcher.start()
            watcher.join()
            after_fire = list(rebuild_threads)
            for _ in range(3):
                await asyncio.sleep(0)
        return after_fire, threading.get_ident()

    after_fire, loop_thread = asyncio.run(mount_then_reload_from_watcher_thread())

    assert after_fire == [loop_thread], "the rebuild ran on the watcher thread"
    assert rebuild_threads == [loop_thread, loop_thread]
    assert session.context.keymap.commands == {}


def test_roster_change_does_not_rebuild_keymap() -> None:
    """A tier change reloads the page (which rebuilds the keymap); the shell no longer rebuilds in place."""
    session = _FakeSession()
    with patch.object(KeymapListener, "set_keymap") as set_keymap:
        _mounted_shell(session)
        session.publish(RosterChanged())

    assert set_keymap.call_count == 1


def test_cleanup_drops_registry_subscription() -> None:
    registry = _FakeEditorRegistry({"ed": _ClipboardEditor})
    session = _FakeSession()
    shell = _mounted_shell(session, registry)
    assert registry.batch_subscribers

    shell.cleanup()

    assert registry.batch_subscribers == []


def test_keymap_problems_logged_once_across_sessions() -> None:
    registry = _FakeEditorRegistry({"ed": _ClipboardEditor, "r": _ReservedEditor})
    ledger = MagicMock()
    with patch("haywire.core.errors.ledger.get_error_ledger", return_value=ledger):
        _mounted_shell(_FakeSession(), registry)
        _mounted_shell(_FakeSession(), registry)
        registry.fire()

    recorded = [call.args[0] for call in ledger.record.call_args_list]
    assert len(recorded) == 1
    assert "Mod+W" in recorded[0].message
