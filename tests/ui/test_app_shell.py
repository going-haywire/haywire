"""Tests for AppShell toolbar styling."""

import haywire.core.graph.editor as graph_editor_module
from types import SimpleNamespace

from haywire.ui.app.shell import AppShell
from haywire.ui.context_events import ContextChangeType


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
                left=SimpleNamespace(editor_key="left:editor:one", visible=True),
                right=SimpleNamespace(editor_key="right:editor:one", visible=True),
                left_bar_active="left:editor:one",
                right_bar_active="right:editor:one",
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


def test_switch_left_area_refreshes_toolbar_and_column() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell._left_column = _FakeContainer()
    shell._activity_bar = _FakeContainer()

    rendered = []
    shell._render_area = lambda slot, editor_key: rendered.append((slot, editor_key))
    shell._render_activity_bar_contents = lambda: rendered.append(("activity", None))

    shell._switch_left_area("left:editor:two")

    assert shell.session.workspace_manager.active.left_bar_active == "left:editor:two"
    assert shell._left_column.clear_calls == 1
    assert shell._activity_bar.clear_calls == 1
    assert ("left", "left:editor:two") in rendered
    assert ("activity", None) in rendered
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


def test_switch_right_area_refreshes_toolbar_and_column() -> None:
    shell = AppShell(session=_FakeSession(), editor_registry=None)
    shell._right_column = _FakeContainer()
    shell._context_bar = _FakeContainer()

    rendered = []
    shell._render_area = lambda slot, editor_key: rendered.append((slot, editor_key))
    shell._render_context_bar_contents = lambda: rendered.append(("context", None))

    shell._switch_right_area("right:editor:two")

    assert shell.session.workspace_manager.active.right_bar_active == "right:editor:two"
    assert shell._right_column.clear_calls == 1
    assert shell._context_bar.clear_calls == 1
    assert ("right", "right:editor:two") in rendered
    assert ("context", None) in rendered
    assert shell.session.notified_events[-1].change_type == ContextChangeType.WORKSPACE_CHANGED


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
