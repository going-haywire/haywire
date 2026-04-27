"""Tests for AppShell — post-refactor surface area.

After the bus split (signal + lifecycle channels), AppShell owns:
  - Theme CSS build + `apply_workbench_theme`
  - Signal-channel orchestrator callback (`_on_signal`) fanning signals to slots
  - Lifecycle-channel orchestrator callback (`_on_lifecycle`) routing
    ``Reveal`` to ``_reveal_editor`` and ``Close`` to ``_close_payload``
  - Slot construction via `_build_managed_slot`
  - `_on_slot_resize` dispatching to `slot.set_size`

Bar rendering, tab-state mutations, visibility toggling, and hot-reload are
tested in test_icon_slot.py / test_tab_slot.py / test_slot.py.
"""

import logging
from types import SimpleNamespace

import haywire.core.graph.editor as graph_editor_module
from haywire.ui.app.shell import AppShell
from haywire.ui.context_signals import Close, Reveal
from haywire.ui.editor.identity import OpenBehavior


class _FakeSession:
    def __init__(self) -> None:
        self.workspace_manager = SimpleNamespace(
            snapshot={
                "left": {"active_key": "left:editor:one", "visible": True, "size": 300, "editors": []},
                "right": {"active_key": "right:editor:one", "visible": True, "size": 300, "editors": []},
                "main": {"active_key": "main:editor:one", "editors": []},
                "bottom": {"active_key": None, "visible": False, "size": 200, "editors": []},
            }
        )
        self._editors = {}
        self.signals_seen: list = []

    def set_signal_orchestrator(self, _callback) -> None:
        pass

    def set_lifecycle_orchestrator(self, _callback) -> None:
        pass

    def signal(self, s) -> None:
        self.signals_seen.append(s)


class _FakeSlot:
    """Stand-in for IconSlot/TabSlot used by orchestrator + dispatch tests."""

    def __init__(self, name: str, active_key: str | None = None) -> None:
        self.name = name
        self.active_key = active_key
        self.visible = True
        self.bindings: list = []
        self.switch_calls: list = []
        self.size_calls: list[int] = []
        self.open_tab_calls: list = []
        self.close_tab_calls: list = []
        self.repayload_calls: list = []
        self.close_tabs_for_payload_calls: list = []

    def switch_to(self, editor_key: str, payload=None) -> bool:
        self.switch_calls.append((editor_key, payload))
        if editor_key == self.active_key and payload is None:
            return False
        self.active_key = editor_key
        return True

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_size(self, size_px: int) -> None:
        self.size_calls.append(size_px)

    def handle_signal(self, signal) -> None:
        pass

    def find_binding(self, editor_key, payload=None):
        for b in self.bindings:
            if b.editor_key == editor_key and getattr(b, "payload", None) == payload:
                return b
        return None

    def open_tab(self, cls, editor_key, payload, label):
        self.open_tab_calls.append((editor_key, payload, label))
        self.bindings.append(SimpleNamespace(editor_key=editor_key, payload=payload))
        self.active_key = editor_key
        return True

    def close_tab(self, editor_key, payload):
        self.close_tab_calls.append((editor_key, payload))
        return True

    def repayload_tab(self, editor_key, old_payload, new_payload, new_label=None):
        self.repayload_calls.append((editor_key, old_payload, new_payload, new_label))
        return True

    def close_tabs_for_payload(self, payload):
        self.close_tabs_for_payload_calls.append(payload)
        return 1

    def _refresh_bar(self):
        pass


class _FakeTabSlot(_FakeSlot):
    """Subclass marker so isinstance(slot, TabSlot) checks in shell match."""


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
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    slot = _FakeSlot("bottom")
    shell._managed_slots["bottom"] = slot
    shell._on_slot_resize(SimpleNamespace(args={"slot": "bottom", "size": 275}))
    assert slot.size_calls == [275]


def test_on_slot_resize_ignores_unknown_slot() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell._on_slot_resize(SimpleNamespace(args={"slot": "mystery", "size": 100}))  # no crash


def test_on_slot_resize_ignores_malformed_args() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    slot = _FakeSlot("bottom")
    shell._managed_slots["bottom"] = slot
    shell._on_slot_resize(SimpleNamespace(args="not a dict"))
    shell._on_slot_resize(SimpleNamespace(args=None))
    shell._on_slot_resize(SimpleNamespace(args={"slot": "bottom"}))
    assert slot.size_calls == []


# ---------------------------------------------------------------------------
# _on_lifecycle — Reveal + Close dispatch
# ---------------------------------------------------------------------------


def test_reveal_editor_routes_through_icon_slot() -> None:
    target_key = "right:editor:two"
    cls = _make_editor_cls(target_key, "right", OpenBehavior.REQUIRED)
    registry = _FakeEditorRegistry({target_key: cls})
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("right", active_key="right:editor:one")
    shell._managed_slots["right"] = fake

    shell._on_lifecycle(Reveal(editor=cls))

    assert fake.switch_calls == [(target_key, None)]
    assert shell.session.signals_seen == []  # reveal must not broadcast a signal


def test_reveal_editor_unknown_logs_warning(caplog) -> None:
    nonexistent_key = "nonexistent:editor:zzz"
    cls = _make_editor_cls(nonexistent_key, "right", OpenBehavior.REQUIRED)
    registry = _FakeEditorRegistry({})  # cls intentionally NOT registered
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("right", active_key="right:editor:one")
    shell._managed_slots["right"] = fake

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.shell"):
        shell._on_lifecycle(Reveal(editor=cls))

    assert fake.switch_calls == []
    assert any(nonexistent_key in rec.message for rec in caplog.records)


def test_reveal_editor_on_payload_without_payload_logs_and_skips(caplog) -> None:
    from haywire.ui.app.tab_slot import TabSlot

    editor_key = "main:editor:Doc"
    cls = _make_editor_cls(editor_key, "main", OpenBehavior.ON_PAYLOAD)
    registry = _FakeEditorRegistry({editor_key: cls})
    shell = AppShell(session=_FakeSession(), editor_registry=registry)

    class _FakeTab(TabSlot, _FakeSlot):
        """Subclass of the real TabSlot so isinstance checks match, with fake deep state."""

        # Shadow every read-only property Slot defines so _FakeSlot.__init__ can set plain
        # instance attributes without hitting Python's data-descriptor setter guard.
        active_key = None  # type: ignore[assignment]
        active_binding = None  # type: ignore[assignment]
        active_binding_id = None  # type: ignore[assignment]
        visible = None  # type: ignore[assignment]
        bindings = None  # type: ignore[assignment]

        def __init__(self, name):
            _FakeSlot.__init__(self, name)

    fake_tab = _FakeTab("main")
    shell._managed_slots["main"] = fake_tab

    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.shell"):
        shell._reveal_editor(editor_key, payload=None)

    assert fake_tab.open_tab_calls == []
    assert any("on_payload" in rec.message and "payload" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# Close lifecycle command — fan-out tab close across every TabSlot
# ---------------------------------------------------------------------------


def _make_fake_tab_slot(name: str) -> "_FakeSlot":
    """Return an instance that IS-A TabSlot (for isinstance checks) with fake behavior.

    All methods are delegated to _FakeSlot so the real TabSlot implementation
    (which requires a fully initialised Slot.__init__ state) is never called.
    isinstance(result, TabSlot) is True because TabSlot is in the MRO.
    """
    from haywire.ui.app.tab_slot import TabSlot

    class _FakeTab(TabSlot, _FakeSlot):
        # Shadow every read-only property Slot defines so _FakeSlot.__init__ can set plain
        # instance attributes without hitting Python's data-descriptor setter guard.
        active_key = None  # type: ignore[assignment]
        active_binding = None  # type: ignore[assignment]
        active_binding_id = None  # type: ignore[assignment]
        visible = None  # type: ignore[assignment]
        bindings = None  # type: ignore[assignment]

        def __init__(self, slot_name):
            _FakeSlot.__init__(self, slot_name)

        # Explicitly route to _FakeSlot implementations so TabSlot's real logic
        # (which requires Slot.__init__ state) is never invoked.
        def close_tab(self, editor_key, payload):
            return _FakeSlot.close_tab(self, editor_key, payload)

        def repayload_tab(self, editor_key, old_payload, new_payload, new_label=None):
            return _FakeSlot.repayload_tab(self, editor_key, old_payload, new_payload, new_label)

        def close_tabs_for_payload(self, payload):
            return _FakeSlot.close_tabs_for_payload(self, payload)

    return _FakeTab(name)


def test_close_lifecycle_command_closes_matching_tabs_in_every_tab_slot() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    main = _make_fake_tab_slot("main")
    bottom = _make_fake_tab_slot("bottom")
    shell._managed_slots["main"] = main
    shell._managed_slots["bottom"] = bottom

    shell._on_lifecycle(Close(payload="/tmp/a.graph"))
    assert main.close_tabs_for_payload_calls == ["/tmp/a.graph"]
    assert bottom.close_tabs_for_payload_calls == ["/tmp/a.graph"]


# ---------------------------------------------------------------------------
# Graph-editor import regression guard (kept from pre-refactor)
# ---------------------------------------------------------------------------


def test_graph_editor_module_imports_without_circular() -> None:
    assert graph_editor_module is not None
