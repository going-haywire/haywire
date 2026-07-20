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
