"""Tests for AppShell toolbar styling."""

import logging

import haywire.core.graph.editor as graph_editor_module
from types import SimpleNamespace

from haywire.ui.app.shell import AppShell
from haywire.ui.context_events import ContextChangedEvent, ContextChangeType


class _FakeContainer:
    def __init__(self) -> None:
        self.clear_calls = 0

    def clear(self) -> None:
        self.clear_calls += 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeSession:
    def __init__(self) -> None:
        self.workspace_manager = SimpleNamespace(
            active=SimpleNamespace(
                left=SimpleNamespace(active_tab_key="left:editor:one", visible=True),
                right=SimpleNamespace(active_tab_key="right:editor:one", visible=True),
                main=SimpleNamespace(
                    tabs=[],
                    active_tab_key="main:editor:one",
                    visible=True,
                ),
                bottom=SimpleNamespace(
                    tabs=[],
                    active_tab_key=None,
                    visible=False,
                    size=200,
                ),
            )
        )
        self._editors = {}
        self.notified_events = []

    def set_orchestrator(self, callback) -> None:
        pass

    def notify_context_changed(self, event) -> None:
        self.notified_events.append(event)


def test_toolbar_button_classes_marks_active_buttons() -> None:
    assert graph_editor_module is not None

    classes = AppShell._toolbar_button_classes(is_active=True)

    assert "hw-shell-toolbar-btn" in classes
    assert "hw-shell-toolbar-btn-active" in classes


def test_toolbar_button_classes_leaves_inactive_buttons_unhighlighted() -> None:
    classes = AppShell._toolbar_button_classes(is_active=False)

    assert "hw-shell-toolbar-btn" in classes
    assert "hw-shell-toolbar-btn-active" not in classes


class _FakeSlot:
    """Stand-in for :class:`haywire.ui.app.slot.Slot` used by switch tests."""

    def __init__(self, name: str, active_key: str) -> None:
        self.name = name
        self.active_key = active_key
        self.switch_calls: list[str] = []
        self.visible_calls: list[bool] = []

    def switch_to(self, editor_key: str, payload=None) -> bool:
        self.switch_calls.append((editor_key, payload))
        if editor_key == self.active_key and payload is None:
            return False
        self.active_key = editor_key
        return True

    def set_visible(self, visible: bool) -> None:
        self.visible_calls.append(visible)

    def handle_context_event(self, event) -> None:
        pass


def test_switch_left_slot_delegates_to_managed_slot_and_notifies() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("left", active_key="left:editor:one")
    shell._managed_slots["left"] = fake
    shell._activity_bar = _FakeContainer()

    rendered = []
    shell._render_activity_bar_contents = lambda: rendered.append("activity")

    shell._switch_left_slot("left:editor:two")

    assert fake.switch_calls == [("left:editor:two", None)]
    assert shell.session.workspace_manager.active.left.active_tab_key == "left:editor:two"
    assert shell._activity_bar.clear_calls == 1
    assert rendered == ["activity"]
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_switch_right_slot_delegates_to_managed_slot_and_notifies() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("right", active_key="right:editor:one")
    shell._managed_slots["right"] = fake
    shell._context_bar = _FakeContainer()

    rendered = []
    shell._render_context_bar_contents = lambda: rendered.append("context")

    shell._switch_right_slot("right:editor:two")

    assert fake.switch_calls == [("right:editor:two", None)]
    assert shell.session.workspace_manager.active.right.active_tab_key == "right:editor:two"
    assert shell._context_bar.clear_calls == 1
    assert rendered == ["context"]
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_switch_left_slot_no_op_when_already_active_does_not_notify() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("left", active_key="left:editor:one")
    shell._managed_slots["left"] = fake

    shell._switch_left_slot("left:editor:one")

    assert fake.switch_calls == [("left:editor:one", None)]
    assert shell.session.notified_events == []


def test_switch_main_slot_delegates_to_managed_slot_and_refreshes_bar() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("main", active_key="main:editor:one")
    shell._managed_slots["main"] = fake
    shell._main_bar = _FakeContainer()

    rendered = []
    shell._render_main_bar_contents = lambda: rendered.append("main")

    shell._switch_main_slot("main:editor:two")

    assert fake.switch_calls == [("main:editor:two", None)]
    assert shell.session.workspace_manager.active.main.active_tab_key == "main:editor:two"
    assert shell._main_bar.clear_calls == 1
    assert rendered == ["main"]
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_switch_bottom_slot_delegates_to_managed_slot_and_refreshes_bar() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("bottom", active_key="bottom:editor:one")
    shell._managed_slots["bottom"] = fake
    shell._bottom_bar = _FakeContainer()

    rendered = []
    shell._render_bottom_bar_contents = lambda: rendered.append("bottom")

    shell._switch_bottom_slot("bottom:editor:two")

    assert fake.switch_calls == [("bottom:editor:two", None)]
    assert shell.session.workspace_manager.active.bottom.active_tab_key == "bottom:editor:two"
    assert shell._bottom_bar.clear_calls == 1
    assert rendered == ["bottom"]
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_switch_main_slot_no_op_when_already_active_does_not_notify() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    fake = _FakeSlot("main", active_key="main:editor:one")
    shell._managed_slots["main"] = fake

    shell._switch_main_slot("main:editor:one")

    assert fake.switch_calls == [("main:editor:one", None)]
    assert shell.session.notified_events == []


def test_apply_managed_slot_switch_unknown_slot_returns_false() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)

    assert shell._apply_managed_slot_switch("main", "main:editor:two") is False
    assert shell.session.notified_events == []


def test_refresh_activity_bar_renders_contents_without_rebuilding_wrapper() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell._activity_bar = _FakeContainer()

    rendered = []
    shell._render_activity_bar_contents = lambda: rendered.append("activity")

    shell._refresh_activity_bar()

    assert shell._activity_bar.clear_calls == 1
    assert rendered == ["activity"]


def test_refresh_context_bar_renders_contents_without_rebuilding_wrapper() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell._context_bar = _FakeContainer()

    rendered = []
    shell._render_context_bar_contents = lambda: rendered.append("context")

    shell._refresh_context_bar()

    assert shell._context_bar.clear_calls == 1
    assert rendered == ["context"]


class _FakeEditorRegistry:
    """Minimal stand-in for EditorTypeRegistry used by reveal tests."""

    def __init__(self, classes: dict) -> None:
        self._classes = classes

    def get_by_key(self, registry_key: str):
        return self._classes.get(registry_key)


def _make_editor_cls(registry_key: str, default_slot: str) -> type:
    """Build a throwaway class that looks like a decorated BaseEditor."""
    return type(
        f"_FakeEditor_{registry_key.replace(':', '_')}",
        (),
        {
            "class_identity": SimpleNamespace(
                registry_key=registry_key,
                default_slot=default_slot,
            )
        },
    )


def test_on_context_changed_reveal_editor_switches_slot() -> None:
    """A reveal_editor on an event routes through the managed Slot and
    does NOT fire a nested WORKSPACE_CHANGED event."""
    target_key = "right:editor:two"
    registry = _FakeEditorRegistry({target_key: _make_editor_cls(target_key, "right")})
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("right", active_key="right:editor:one")
    shell._managed_slots["right"] = fake
    shell._context_bar = _FakeContainer()

    rendered = []
    shell._render_context_bar_contents = lambda: rendered.append("context")

    event = ContextChangedEvent(
        change_type=ContextChangeType.ACTIVE_COMPONENT_CHANGED,
        reveal_editor=target_key,
    )
    shell._on_context_changed(event, shell.session.workspace_manager.active)

    assert fake.switch_calls == [(target_key, None)]
    assert shell.session.workspace_manager.active.right.active_tab_key == target_key
    assert rendered == ["context"]
    # Reveal must NOT fire a nested WORKSPACE_CHANGED event.
    assert shell.session.notified_events == []


def test_on_context_changed_reveal_editor_routes_to_main_slot() -> None:
    """reveal_editor works for main slot identically to left/right — proves
    the managed-slot path is uniform across all four slots."""
    target_key = "main:editor:two"
    registry = _FakeEditorRegistry({target_key: _make_editor_cls(target_key, "main")})
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("main", active_key="main:editor:one")
    shell._managed_slots["main"] = fake
    shell._main_bar = _FakeContainer()
    shell._render_main_bar_contents = lambda: None

    event = ContextChangedEvent(
        change_type=ContextChangeType.ACTIVE_GRAPH_CHANGED,
        reveal_editor=target_key,
    )
    shell._on_context_changed(event, shell.session.workspace_manager.active)

    assert fake.switch_calls == [(target_key, None)]
    assert shell.session.workspace_manager.active.main.active_tab_key == target_key
    assert shell.session.notified_events == []


def test_on_context_changed_reveal_editor_routes_to_bottom_slot() -> None:
    target_key = "bottom:editor:two"
    registry = _FakeEditorRegistry({target_key: _make_editor_cls(target_key, "bottom")})
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("bottom", active_key="bottom:editor:one")
    shell._managed_slots["bottom"] = fake
    shell._bottom_bar = _FakeContainer()
    shell._render_bottom_bar_contents = lambda: None

    event = ContextChangedEvent(
        change_type=ContextChangeType.WORKSPACE_CHANGED,
        reveal_editor=target_key,
    )
    shell._on_context_changed(event, shell.session.workspace_manager.active)

    assert fake.switch_calls == [(target_key, None)]
    assert shell.session.workspace_manager.active.bottom.active_tab_key == target_key
    assert shell.session.notified_events == []


class _FakeVisibility:
    """Stand-in for a NiceGUI element with set_visibility + props tracking."""

    def __init__(self, visible: bool = True) -> None:
        self.visible = visible
        self.props_calls: list[str] = []

    def set_visibility(self, visible: bool) -> None:
        self.visible = visible

    def props(self, value: str) -> None:
        self.props_calls.append(value)


def _make_shell_with_bottom_stubs(visible: bool = False):
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell.session.workspace_manager.active.bottom.visible = visible
    shell._bottom_divider = _FakeVisibility(visible=visible)
    shell._bottom_container = _FakeVisibility(visible=visible)
    shell._btn_bottom = _FakeVisibility()
    return shell


def test_toggle_bottom_slot_flips_visible_and_syncs_ui() -> None:
    shell = _make_shell_with_bottom_stubs(visible=False)

    shell._toggle_bottom_slot()

    ws = shell.session.workspace_manager.active
    assert ws.bottom.visible is True
    assert shell._bottom_divider.visible is True
    assert shell._bottom_container.visible is True
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_less"

    shell._toggle_bottom_slot()

    assert ws.bottom.visible is False
    assert shell._bottom_divider.visible is False
    assert shell._bottom_container.visible is False
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_more"


def test_apply_bottom_visibility_syncs_all_three_elements() -> None:
    shell = _make_shell_with_bottom_stubs(visible=False)

    shell._apply_bottom_visibility(True)

    assert shell._bottom_divider.visible is True
    assert shell._bottom_container.visible is True
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_less"

    shell._apply_bottom_visibility(False)

    assert shell._bottom_divider.visible is False
    assert shell._bottom_container.visible is False
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_more"


def test_on_bottom_drag_auto_expand_flips_retracted_to_visible() -> None:
    shell = _make_shell_with_bottom_stubs(visible=False)

    shell._on_bottom_drag_auto_expand()

    ws = shell.session.workspace_manager.active
    assert ws.bottom.visible is True
    assert shell._bottom_container.visible is True
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_less"


def test_on_bottom_drag_auto_expand_noop_when_already_visible() -> None:
    shell = _make_shell_with_bottom_stubs(visible=True)

    shell._on_bottom_drag_auto_expand()

    # No redundant props calls when already in the target state.
    assert shell._btn_bottom.props_calls == []
    assert shell.session.workspace_manager.active.bottom.visible is True


def test_on_bottom_drag_snap_retract_flips_visible_to_retracted() -> None:
    shell = _make_shell_with_bottom_stubs(visible=True)

    shell._on_bottom_drag_snap_retract()

    ws = shell.session.workspace_manager.active
    assert ws.bottom.visible is False
    assert shell._bottom_container.visible is False
    assert shell._btn_bottom.props_calls[-1] == "icon=expand_more"


def test_on_bottom_drag_snap_retract_noop_when_already_retracted() -> None:
    shell = _make_shell_with_bottom_stubs(visible=False)

    shell._on_bottom_drag_snap_retract()

    assert shell._btn_bottom.props_calls == []
    assert shell.session.workspace_manager.active.bottom.visible is False


def test_on_bottom_drag_resize_accepts_numeric_args() -> None:
    shell = _make_shell_with_bottom_stubs(visible=True)

    shell._on_bottom_drag_resize(SimpleNamespace(args=275))
    assert shell.session.workspace_manager.active.bottom.size == 275

    shell._on_bottom_drag_resize(SimpleNamespace(args=312.5))
    assert shell.session.workspace_manager.active.bottom.size == 312


def test_on_bottom_drag_resize_accepts_list_args() -> None:
    shell = _make_shell_with_bottom_stubs(visible=True)

    shell._on_bottom_drag_resize(SimpleNamespace(args=[240]))
    assert shell.session.workspace_manager.active.bottom.size == 240


def test_on_bottom_drag_resize_ignores_unexpected_args() -> None:
    shell = _make_shell_with_bottom_stubs(visible=True)
    original = shell.session.workspace_manager.active.bottom.size

    shell._on_bottom_drag_resize(SimpleNamespace(args="not a number"))
    shell._on_bottom_drag_resize(SimpleNamespace(args=None))
    shell._on_bottom_drag_resize(SimpleNamespace(args=[]))

    assert shell.session.workspace_manager.active.bottom.size == original


def test_on_context_changed_reveal_editor_unknown_logs_warning(caplog) -> None:
    """An unknown reveal_editor is a soft failure: warning logged, no switch,
    the rest of the poll/draw cycle still runs for existing editors."""
    registry = _FakeEditorRegistry({})  # empty — unknown key
    shell = AppShell(session=_FakeSession(), editor_registry=registry)
    fake = _FakeSlot("right", active_key="right:editor:one")
    shell._managed_slots["right"] = fake

    event = ContextChangedEvent(
        change_type=ContextChangeType.ACTIVE_COMPONENT_CHANGED,
        reveal_editor="nonexistent:editor:zzz",
    )
    with caplog.at_level(logging.WARNING, logger="haywire.ui.app.shell"):
        shell._on_context_changed(event, shell.session.workspace_manager.active)

    # Slot untouched.
    assert fake.switch_calls == []
    assert shell.session.workspace_manager.active.right.active_tab_key == "right:editor:one"
    # Warning was logged and mentions the offending key.
    assert any("nonexistent:editor:zzz" in rec.message for rec in caplog.records)
    # No nested event emitted.
    assert shell.session.notified_events == []
