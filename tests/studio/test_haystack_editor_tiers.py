"""HaystackEditor actions need the principal's real tier: view selects, operate runs, edit does the rest."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haybale_haystack.editors import haystack_editor as haystack_editor_module
from haybale_graph_editor.state.edit_state import EditState
from haybale_haystack.editors.haystack_editor import HaystackEditor
from haywire.core.access import AccessTier, access_resolver, set_access_resolver
from haywire.core.session.context import SessionContext
from haywire.ui.editor.wrapper import EditorWrapper

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _restore_resolver():
    previous = access_resolver()
    yield
    set_access_resolver(previous)


def _setup(tier: AccessTier, monkeypatch: pytest.MonkeyPatch) -> tuple[HaystackEditor, Any, Any, MagicMock]:
    set_access_resolver(lambda name: tier)
    haystack = MagicMock()
    haystack.save_graph = MagicMock(return_value=True)
    entry = SimpleNamespace(path=Path("/tmp/a.haywire"), unsaved=True, graph=object())
    haystack.get_by_id = MagicMock(return_value=entry)
    context = SessionContext(session_id="s1", app=MagicMock())
    context.principal = "someone"
    app_data = MagicMock()
    app_data.__getitem__.return_value = haystack
    context.app_data = app_data  # type: ignore[assignment]
    dialog = MagicMock()
    monkeypatch.setattr(haystack_editor_module, "open_graph_save_as_dialog", dialog)
    monkeypatch.setattr(haystack_editor_module.ui, "notify", MagicMock())
    monkeypatch.setattr(haystack_editor_module.ui, "context", SimpleNamespace(client=MagicMock()))
    editor = HaystackEditor(cast(EditorWrapper, object()))
    return editor, context, haystack, dialog


@pytest.mark.parametrize("tier", [AccessTier.VIEW, AccessTier.OPERATE])
def test_save_refused_below_edit(tier, monkeypatch):
    editor, context, haystack, dialog = _setup(tier, monkeypatch)
    editor._on_entry_save("id", context)
    editor._on_entry_save_as("id", context)
    haystack.save_graph.assert_not_called()
    dialog.assert_not_called()
    assert haystack_editor_module.ui.notify.call_count == 2  # type: ignore[attr-defined]


def _haystack_header_setup(tier: AccessTier, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, Any, Any, Any]:
    """An editor with a loaded haystack named ``hs1``, and the modal Save As opens, mocked."""
    editor, context, haystack, _dialog = _setup(tier, monkeypatch)
    monkeypatch.setattr(editor, "_get_active_haystack_name", lambda ctx: "hs1")
    haystack.is_haystack_dirty = True
    context.data[EditState].active_graph_path = None
    modal = MagicMock()
    monkeypatch.setattr(haystack_editor_module, "rename_modal", modal)
    return editor, context, haystack, modal


@pytest.mark.parametrize("tier", [AccessTier.VIEW, AccessTier.OPERATE])
def test_haystack_save_refused_below_edit(tier, monkeypatch):
    editor, context, haystack, modal = _haystack_header_setup(tier, monkeypatch)
    editor._on_save_haystack_in_place(context)
    editor._on_save_haystack(context)
    haystack.save_haystack.assert_not_called()
    modal.assert_not_called()
    assert haystack_editor_module.ui.notify.call_count == 2  # type: ignore[attr-defined]


def test_haystack_save_allowed_for_edit(monkeypatch):
    editor, context, haystack, modal = _haystack_header_setup(AccessTier.EDIT, monkeypatch)
    editor._on_save_haystack_in_place(context)
    haystack.save_haystack.assert_called_once_with("hs1", active_path=None)
    editor._on_save_haystack(context)
    modal.assert_called_once()


def _noop_page() -> None:  # registration target for a headless Client
    pass


def _render(fn) -> list[Any]:
    """Run ``fn`` inside a headless client and return every element it created."""
    from nicegui import Client, ui

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            fn()
    return list(client.elements.values())


def _icon_buttons(elements: list[Any], icon: str) -> list[Any]:
    from nicegui import ui

    return [el for el in elements if isinstance(el, ui.button) and el.props.get("icon") == icon]


def _entry(*, executing: bool = False) -> SimpleNamespace:
    from haybale_haystack.graph_entry import EntryKind

    return SimpleNamespace(
        binding_id="id",
        path=Path("/tmp/a.haywire"),
        unsaved=True,
        graph=object(),
        is_executing=executing,
        kind=EntryKind.GRAPH,
        display_name="a",
    )


@pytest.mark.parametrize(
    ("tier", "shown"), [(AccessTier.VIEW, False), (AccessTier.OPERATE, False), (AccessTier.EDIT, True)]
)
def test_haystack_controls_are_hidden_below_edit(tier, shown, monkeypatch):
    editor, context, haystack, _modal = _haystack_header_setup(tier, monkeypatch)
    entry = _entry()
    haystack.entries_of_kind = MagicMock(side_effect=lambda kind: [entry] if kind.is_executable() else [])
    editor._list_container = None

    def _draw() -> None:
        from nicegui import ui

        editor._render_header(context)
        editor._list_container = ui.column()
        editor._render_list(context)

    elements = _render(_draw)

    assert bool(_icon_buttons(elements, "save")) is shown  # header and entry Save icons
    assert bool(_icon_buttons(elements, "more_vert")) is shown  # header and entry menus
    assert bool(_icon_buttons(elements, "add")) is shown  # the add bar
    assert any("bg-amber-400" in el._classes for el in elements)  # the unsaved dot stays


@pytest.mark.parametrize(("tier", "runs"), [(AccessTier.VIEW, False), (AccessTier.OPERATE, True)])
def test_operate_draws_start_stop_and_no_entry_menu(tier, runs, monkeypatch):
    from haywire.ui import elements as hui

    editor, context, _haystack, _modal = _haystack_header_setup(tier, monkeypatch)
    elements = _render(lambda: editor._render_entry(cast(Any, _entry(executing=True)), context))

    assert bool(_icon_buttons(elements, hui.icon.execution_stop)) is runs
    assert _icon_buttons(elements, "more_vert") == []


@pytest.mark.parametrize("tier", [AccessTier.VIEW, AccessTier.OPERATE])
def test_each_edit_handler_refuses_below_edit(tier, monkeypatch):
    editor, context, haystack, modal = _haystack_header_setup(tier, monkeypatch)
    confirm, pick = MagicMock(), MagicMock()
    monkeypatch.setattr(haystack_editor_module, "confirm_modal", confirm)
    monkeypatch.setattr(haystack_editor_module, "pick_modal", pick)
    haystack.get_by_id = MagicMock(return_value=_entry())

    editor._on_entry_rename("id", context)
    editor._on_entry_delete("id", context)
    editor._on_new(context)
    editor._on_open_graph(context)
    editor._on_load_haystack(context)
    editor._on_rename_haystack(context)

    for name in (
        "create_new",
        "remove_entry",
        "open_graph",
        "load_haystack",
        "rename_haystack",
        "rename_graph",
    ):
        getattr(haystack, name).assert_not_called()
    confirm.assert_not_called()
    pick.assert_not_called()
    modal.assert_not_called()
    assert haystack_editor_module.ui.notify.call_count == 6  # type: ignore[attr-defined]


@pytest.mark.parametrize(("tier", "runs"), [(AccessTier.VIEW, False), (AccessTier.OPERATE, True)])
def test_start_and_stop_need_operate(tier, runs, monkeypatch):
    editor, context, haystack, _dialog = _setup(tier, monkeypatch)
    haystack.get_by_id = MagicMock(return_value=_entry())
    haystack.start_execution = MagicMock(return_value=SimpleNamespace(ok=True, error=None))
    monkeypatch.setattr(editor, "_notify_data_mutated", lambda ctx: None)

    editor._on_start_execution("id", context)
    editor._on_stop_execution("id", context)

    assert haystack.start_execution.called is runs
    assert haystack.stop_execution.called is runs


def test_save_allowed_for_edit(monkeypatch):
    editor, context, haystack, dialog = _setup(AccessTier.EDIT, monkeypatch)
    editor._on_entry_save("id", context)
    haystack.save_graph.assert_called_once()

    editor._on_entry_save_as("id", context)
    dialog.assert_called_once()
    save_fn = dialog.call_args.kwargs["save_fn"]
    save_fn(Path("/tmp/b.haywire"))
    assert haystack.save_graph.call_count == 2
