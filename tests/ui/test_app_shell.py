"""Tests for AppShell — post-refactor surface area.

After the event-bus merge, AppShell owns:
  - Theme CSS build + `apply_workbench_theme`
  - ``Reveal`` / ``Close`` / ``BroadcastClose`` bus subscriptions (handled
    by ``_reveal_editor`` and ``_close_payload``)
  - Slot construction via `_build_managed_slot`
  - `_on_slot_resize` dispatching to `slot.set_size`

Event dispatch flows through ``Session``'s typed event bus directly to
editors' auto-wired ``@redraw_on`` / ``@react_on`` handlers and to the
shell's own workspace-mutation handlers.

Bar rendering, tab-state mutations, visibility toggling, and hot-reload are
tested in test_icon_slot.py / test_tab_slot.py / test_slot.py.
"""

import logging
from types import SimpleNamespace

from typing import Any, cast

import haywire.core.graph.editor as graph_editor_module
from haywire.ui.app.shell import AppShell
from haywire.core.session.signals import Close, Reveal
from haywire.ui.editor.identity import OpenBehavior, SlotName


def _shell(*, session: Any, editor_registry: Any) -> AppShell:
    """Build an AppShell from structural test doubles.

    ``_FakeSession`` / ``_FakeEditorRegistry`` implement only the slice AppShell
    touches; casting here keeps that seam in one place.
    """
    return AppShell(session=cast(Any, session), editor_registry=cast(Any, editor_registry))


def _install_slot(shell: AppShell, name: SlotName, slot: Any) -> None:
    """Register a ``_FakeSlot`` in the shell's managed-slot table."""
    shell._managed_slots[name] = cast(Any, slot)


class _FakeSession:
    def __init__(self) -> None:
        self.workspace_manager = SimpleNamespace(
            snapshot={
                "action": {"active_key": "left:editor:one", "visible": True, "size": 300, "editors": []},
                "context": {"active_key": "right:editor:one", "visible": True, "size": 300, "editors": []},
                "edit": {"active_key": "main:editor:one", "editors": []},
                "info": {"active_key": None, "visible": False, "size": 200, "editors": []},
            }
        )
        self._editors: dict = {}
        self.signals_seen: list = []

    def subscribe(self, _event_type, _handler):
        """Stub. Real Session.subscribe returns an unsubscribe closure."""
        return lambda: None

    def publish(self, s) -> None:
        self.signals_seen.append(s)


class _FakeSlot:
    """Stand-in for any Slot subclass used by orchestrator + dispatch tests."""

    def __init__(self, name: str, active_key: str | None = None) -> None:
        self.name = name
        self.active_key = active_key
        self.visible = True
        self.bindings: list = []
        self.switch_calls: list = []
        self.size_calls: list[int] = []
        self.reveal_calls: list = []
        self.close_tabs_for_calls: list = []

    def switch_to(self, editor_key: str, binding_id=None) -> bool:
        self.switch_calls.append((editor_key, binding_id))
        if editor_key == self.active_key and binding_id is None:
            return False
        self.active_key = editor_key
        return True

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_size(self, size_px: int) -> None:
        self.size_calls.append(size_px)

    def find_binding(self, editor_key, binding_id=None):
        for b in self.bindings:
            if b.editor_key == editor_key and getattr(b, "binding_id", None) == binding_id:
                return b
        return None

    def reveal(self, command):
        editor_key = command.editor.class_identity.registry_key
        self.reveal_calls.append((editor_key, command.binding_id, command.label or ""))
        existing = self.find_binding(editor_key, command.binding_id)
        if existing is None:
            self.bindings.append(SimpleNamespace(editor_key=editor_key, binding_id=command.binding_id))
        self.switch_to(editor_key, command.binding_id)
        return True

    def close_tabs_for(self, binding_id):
        self.close_tabs_for_calls.append(binding_id)
        return 1

    def _refresh_bar(self):
        pass


# ---------------------------------------------------------------------------
# Fake editor registry + helpers
# ---------------------------------------------------------------------------


def _make_editor_cls(registry_key: str, default_slot: str, opens=OpenBehavior.REQUIRED) -> type:
    return type(
        f"_FakeEditor_{registry_key.replace(':', '_')}",
        (),
        {
            "class_identity": SimpleNamespace(
                registry_key=registry_key,
                default_slot=default_slot,
                opens=opens,
                label=registry_key,
                icon="icon",
            )
        },
    )


class _FakeEditorRegistry:
    def __init__(self, classes: dict) -> None:
        self._classes = classes

    def get_by_key(self, registry_key: str):
        return self._classes.get(registry_key)


# ---------------------------------------------------------------------------
# _on_slot_resize
# ---------------------------------------------------------------------------


def test_on_slot_resize_routes_to_named_slot() -> None:
    shell = _shell(session=_FakeSession(), editor_registry=_FakeEditorRegistry({}))
    slot = _FakeSlot("info")
    _install_slot(shell, SlotName.INFO, slot)
    shell._on_slot_resize(SimpleNamespace(args={"slot": "info", "size": 275}))
    assert slot.size_calls == [275]


def test_on_slot_resize_ignores_unknown_slot() -> None:
    shell = _shell(session=_FakeSession(), editor_registry=_FakeEditorRegistry({}))
    shell._on_slot_resize(SimpleNamespace(args={"slot": "mystery", "size": 100}))  # no crash


def test_on_slot_resize_ignores_malformed_args() -> None:
    shell = _shell(session=_FakeSession(), editor_registry=_FakeEditorRegistry({}))
    slot = _FakeSlot("info")
    _install_slot(shell, SlotName.INFO, slot)
    shell._on_slot_resize(SimpleNamespace(args="not a dict"))
    shell._on_slot_resize(SimpleNamespace(args=None))
    shell._on_slot_resize(SimpleNamespace(args={"slot": "info"}))
    assert slot.size_calls == []


# ---------------------------------------------------------------------------
# Reveal handler — point-to-point routing into a slot
# ---------------------------------------------------------------------------


def test_reveal_editor_routes_through_slot() -> None:
    target_key = "right:editor:two"
    cls = _make_editor_cls(target_key, SlotName.CONTEXT, OpenBehavior.REQUIRED)
    registry = _FakeEditorRegistry({target_key: cls})
    shell = _shell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("context", active_key="right:editor:one")
    _install_slot(shell, SlotName.CONTEXT, fake)

    shell._reveal_editor(Reveal(editor=cls))

    assert fake.reveal_calls == [(target_key, None, "")]
    # reveal must not republish anything (recorder lives on the _FakeSession)
    assert cast(Any, shell.session).signals_seen == []


def test_reveal_editor_unhostable_slot_logs_warning(caplog) -> None:
    target_key = "ghost:editor:zzz"
    cls = _make_editor_cls(target_key, "ghost-slot", OpenBehavior.REQUIRED)
    registry = _FakeEditorRegistry({target_key: cls})
    shell = _shell(session=_FakeSession(), editor_registry=registry)
    # No slot registered under "ghost-slot", so the reveal must be dropped.
    fake = _FakeSlot("context", active_key="right:editor:one")
    _install_slot(shell, SlotName.CONTEXT, fake)

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.shell"):
        shell._reveal_editor(Reveal(editor=cls))

    assert fake.reveal_calls == []
    assert any(target_key in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Close handler — fan-out wrapper close across every slot
# ---------------------------------------------------------------------------


def test_close_lifecycle_command_closes_matching_wrappers_in_every_slot() -> None:
    shell = _shell(session=_FakeSession(), editor_registry=_FakeEditorRegistry({}))
    left = _FakeSlot("action")
    main = _FakeSlot("edit")
    bottom = _FakeSlot("info")
    _install_slot(shell, SlotName.ACTION, left)
    _install_slot(shell, SlotName.EDIT, main)
    _install_slot(shell, SlotName.INFO, bottom)

    shell._close_payload(Close(binding_id="/tmp/a.graph"))
    assert left.close_tabs_for_calls == ["/tmp/a.graph"]
    assert main.close_tabs_for_calls == ["/tmp/a.graph"]
    assert bottom.close_tabs_for_calls == ["/tmp/a.graph"]


# ---------------------------------------------------------------------------
# Graph-editor import regression guard (kept from pre-refactor)
# ---------------------------------------------------------------------------


def test_graph_editor_module_imports_without_circular() -> None:
    assert graph_editor_module is not None
