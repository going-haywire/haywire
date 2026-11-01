"""Graph notices on the haystack row: icon with count, popup lines, action gating, per-editor dismiss."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext
from haywire.core.undo.no_op_history_manager import NoOpHistoryManager
from haywire.ui.editor.wrapper import EditorWrapper
from nicegui import Client, ui

from haybale_graph_editor.notices import GraphNotice
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState
from haybale_haystack.editors import haystack_editor as haystack_editor_module
from haybale_haystack.editors.haystack_editor import HaystackEditor
from haybale_haystack.graph_entry import EntryKind
from haybale_haystack.state.haystack_state import HaystackState

pytestmark = pytest.mark.unit


@dataclass
class _Editor:
    graph: object = None
    history_manager: Any = field(default_factory=NoOpHistoryManager)


@dataclass
class _Container:
    binding_id: str
    editor: Any = field(default_factory=_Editor)


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _noop_page() -> None:
    pass


@pytest.fixture
def setup(monkeypatch):
    from nicegui import core

    monkeypatch.setattr(core, "loop", None)  # no signal emission needed
    set_access_resolver(lambda name: AccessTier.ADMIN)
    gas = GraphAppState()
    gas.register(cast(Any, _Container("id")))
    entry = SimpleNamespace(
        binding_id="id",
        path=Path("/tmp/a.haywire"),
        unsaved=False,
        graph=object(),
        is_executing=False,
        kind=EntryKind.GRAPH,
        display_name="a",
    )
    hs = MagicMock()
    hs.entries_of_kind = MagicMock(side_effect=lambda kind: [entry] if kind.is_executable() else [])
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"
    app_data = MagicMock()
    app_data.__getitem__.side_effect = lambda key: {HaystackState: hs, GraphAppState: gas}[key]
    context.app_data = app_data  # type: ignore[assignment]
    context.data[EditState].active_graph = None
    editor = HaystackEditor(cast(EditorWrapper, object()))
    return editor, context, gas


def _render(editor: HaystackEditor, context: SessionContext) -> list[Any]:
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            editor._list_container = ui.column()
            editor._render_list(context)
    return list(client.elements.values())


def _marked(elements: list[Any], mark: str) -> list[Any]:
    return [el for el in elements if el.props.get("data-hw-mark") == mark]


def _notice_icon(button: Any) -> Any:
    """Return the q-icon inside the notice button."""
    (icon,) = button.default_slot.children
    return icon


def test_row_shows_notice_icon_tinted_without_count(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "Needs 2 models (10 MB)"))
    gas.post_notice("id", GraphNotice("t:b", "Other"))
    elements = _render(editor, context)
    (button,) = _marked(elements, "graph-notice")
    icon = _notice_icon(button)
    assert icon.props["name"] == "error_outline"
    assert not [el for el in elements if isinstance(el, ui.badge)]
    assert "hw-use-props-color" in icon.classes
    assert "hw-text-warning" in icon.classes
    tips = [el for el in elements if isinstance(el, ui.tooltip)]
    assert any(t.text == "Needs 2 models (10 MB)\nOther" for t in tips)


def test_no_icon_without_notices(setup):
    editor, context, _gas = setup
    assert _marked(_render(editor, context), "graph-notice") == []


def test_action_hidden_below_requires(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "x", "Show", lambda c: None, AccessTier.ADMIN))
    set_access_resolver(lambda name: AccessTier.VIEW)
    elements = _render(editor, context)
    assert _marked(elements, "graph-notice-action") == []
    assert any(isinstance(el, ui.label) and el.text == "x" for el in elements)


def test_action_runs_with_session_context(setup, monkeypatch):
    editor, context, gas = setup
    action = MagicMock()
    gas.post_notice("id", GraphNotice("t:a", "x", "Show", action, AccessTier.ADMIN))
    elements = _render(editor, context)
    (btn,) = _marked(elements, "graph-notice-action")
    assert btn.text == "Show"
    popup = editor._notice_popups[0]
    monkeypatch.setattr(type(popup), "close", lambda self: None)
    monkeypatch.setattr(haystack_editor_module.ui, "context", SimpleNamespace(client=MagicMock()))
    editor._run_notice_action(gas.notices("id")[0], popup, context)
    action.assert_called_once_with(context)


def _render_keep(editor: HaystackEditor, context: SessionContext) -> Client:
    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            editor._list_container = ui.column()
            editor._render_list(context)
    return client


def _dismiss_buttons(client: Client) -> list[Any]:
    return [el for el in client.elements.values() if el.props.get("icon") == "close"]


def test_dismiss_button_hides_for_this_editor_only(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "x", dismissable=True))
    other = HaystackEditor(cast(EditorWrapper, object()))
    client = _render_keep(editor, context)
    assert len(_marked(list(client.elements.values()), "graph-notice")) == 1
    (btn,) = _dismiss_buttons(client)
    event = {"listener_id": next(iter(btn._event_listeners)), "args": []}
    for listener in list(btn._event_listeners.values()):
        if listener.type == "click":
            event["listener_id"] = listener.id
    btn._handle_event(event)
    assert ("id", "t:a") in editor._dismissed_notices
    assert _marked(list(client.elements.values()), "graph-notice") == []
    assert len(_marked(_render(other, context), "graph-notice")) == 1
    assert [n.key for n in gas.notices("id")] == ["t:a"]


def test_popup_lists_notice_text(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "First line"))
    gas.post_notice("id", GraphNotice("t:b", "Second line"))
    elements = _render(editor, context)
    texts = {el.text for el in elements if isinstance(el, ui.label)}
    assert {"First line", "Second line"} <= texts


def test_dismiss_button_only_when_dismissable(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "sticky"))
    assert _dismiss_buttons(_render_keep(editor, context)) == []
    gas.post_notice("id", GraphNotice("t:b", "loose", dismissable=True))
    assert len(_dismiss_buttons(_render_keep(editor, context))) == 1


def test_row_shows_shared_notice_icon(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "a", icon="model_training"))
    gas.post_notice("id", GraphNotice("t:b", "b", icon="model_training"))
    (button,) = _marked(_render(editor, context), "graph-notice")
    icon = _notice_icon(button)
    assert icon.props["name"] == "model_training"
    assert "hw-use-props-color" in icon.classes
    assert "hw-text-warning" in icon.classes


def test_row_uses_generic_icon_when_icons_differ(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "a", icon="model_training"))
    gas.post_notice("id", GraphNotice("t:b", "b"))
    (button,) = _marked(_render(editor, context), "graph-notice")
    assert _notice_icon(button).props["name"] == "error_outline"


def test_popup_line_carries_icon_in_warning_colour(setup):
    editor, context, gas = setup
    gas.post_notice("id", GraphNotice("t:a", "a", icon="model_training"))
    gas.post_notice("id", GraphNotice("t:b", "b"))
    elements = _render(editor, context)
    lines = _marked(elements, "graph-notice-line-icon")
    assert [el.props["name"] for el in lines] == ["model_training", "error_outline"]
    assert all("hw-text-warning" in el.classes for el in lines)
    assert all("hw-use-props-color" in el.classes for el in lines)
