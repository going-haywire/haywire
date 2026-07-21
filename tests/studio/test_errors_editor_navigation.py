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
