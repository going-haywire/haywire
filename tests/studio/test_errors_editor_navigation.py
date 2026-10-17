"""ErrorsEditor navigation entry points."""

from unittest.mock import MagicMock

import pytest

from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.unit


def test_open_component_action_delegates_to_helper(monkeypatch):
    import haybale_studio.editors.errors_editor as mod

    called = {}

    def fake_open_component(error, context):
        called["error"] = error
        called["context"] = context
        return True

    monkeypatch.setattr(mod, "open_component", fake_open_component)

    editor = mod.ErrorsEditor.__new__(mod.ErrorsEditor)
    editor._context = MagicMock()
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    err.ledger_seq = 7
    editor._entries_by_seq = {7: err}

    editor._open_component(7)

    assert called["error"] is err
    assert called["context"] is editor._context


def test_open_file_action_delegates_to_helper(monkeypatch):
    import haybale_studio.editors.errors_editor as mod

    called = {}

    def fake_open_file_in_studio(filepath, line_number, context):
        called["filepath"] = filepath
        called["line_number"] = line_number
        called["context"] = context

    monkeypatch.setattr(mod, "open_file_in_studio", fake_open_file_in_studio)

    editor = mod.ErrorsEditor.__new__(mod.ErrorsEditor)
    editor._context = MagicMock()
    err = HaywireException.create("x")
    err.enrich(filename="/tmp/thing.py", line_number=12)
    err.ledger_seq = 5
    editor._entries_by_seq = {5: err}

    editor._open_file(5)

    assert called["filepath"] == "/tmp/thing.py"
    assert called["line_number"] == 12
    assert called["context"] is editor._context


def test_reveal_instance_action_delegates_to_helper(monkeypatch):
    import haybale_studio.editors.errors_editor as mod

    called = {}

    def fake_reveal(error, context):
        called["error"] = error
        return True

    monkeypatch.setattr(mod, "reveal_instance", fake_reveal)

    editor = mod.ErrorsEditor.__new__(mod.ErrorsEditor)
    editor._context = MagicMock()
    err = HaywireException.create("x")
    err.enrich(graph_id="/tmp/g.haywire", node_id="n1")
    err.ledger_seq = 3
    editor._entries_by_seq = {3: err}

    editor._reveal_instance(3)

    assert called["error"] is err


def _noop_page() -> None:
    pass


@pytest.mark.parametrize(("can_edit", "offered"), [(False, False), (True, True)])
def test_open_file_and_component_are_offered_only_for_edit(can_edit, offered):
    """Both open an editor that needs edit; below it the entries would do nothing."""
    from typing import Any, cast

    from nicegui import Client, ui

    import haybale_studio.editors.errors_editor as mod

    editor = mod.ErrorsEditor.__new__(mod.ErrorsEditor)
    editor._context = MagicMock()
    editor._context.can_edit.return_value = can_edit
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    err.enrich(filename="/tmp/thing.py", line_number=12)
    err.ledger_seq = 9

    client = Client(cast(Any, _noop_page), request=None)
    with client:
        with ui.column():
            editor._build_row_menu(err)
    texts = {
        child.text
        for el in client.elements.values()
        if isinstance(el, ui.menu_item)
        for child in el.descendants()
        if hasattr(child, "text")
    } | {getattr(el, "text", None) for el in client.elements.values() if isinstance(el, ui.menu_item)}

    assert ("Open file" in texts) is offered
    assert ("Open component" in texts) is offered
    assert "Show details" in texts


@pytest.mark.parametrize(("can_edit", "offered"), [(False, False), (True, True)])
def test_the_details_popup_offers_open_in_studio_only_for_edit(can_edit, offered, monkeypatch):
    import haybale_studio.editors.errors_editor as mod

    captured: dict[str, object] = {}
    monkeypatch.setattr(mod, "Popup", MagicMock())
    monkeypatch.setattr(
        mod,
        "render_error_details",
        lambda _e, _c, on_open_in_studio=None: captured.update(cb=on_open_in_studio),
    )
    monkeypatch.setattr(mod.ui, "column", MagicMock())
    monkeypatch.setattr(mod.ui, "row", MagicMock())
    monkeypatch.setattr(mod.ui, "button", MagicMock())

    editor = mod.ErrorsEditor.__new__(mod.ErrorsEditor)
    editor._context = MagicMock()
    editor._context.can_edit.return_value = can_edit
    err = HaywireException.create("x")
    err.ledger_seq = 4
    editor._entries_by_seq = {4: err}

    editor._show_details(4)

    assert (captured["cb"] is not None) is offered
