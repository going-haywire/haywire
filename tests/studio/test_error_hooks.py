"""Unit tests for the studio's error safety net and last-resort hooks."""

import asyncio
import logging
import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from nicegui import app

from haywire.core.errors import Refusal
from haywire.core.errors.ledger import ErrorLedger, get_error_ledger, set_error_ledger
from haywire_studio import error_hooks as mod
from haywire_studio.error_hooks import ErrorHooks

pytestmark = pytest.mark.unit


@pytest.fixture
def ledger():
    previous = get_error_ledger()
    fresh = ErrorLedger(max_entries=10)
    set_error_ledger(fresh)
    yield fresh
    set_error_ledger(previous)


@pytest.fixture
def notify(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(mod.ui, "notify", mock)
    return mock


@pytest.fixture
def global_hooks():
    saved = (threading.excepthook, sys.excepthook, list(app._exception_handlers))
    yield
    threading.excepthook, sys.excepthook = saved[0], saved[1]
    app._exception_handlers[:] = saved[2]


class _Client:
    id = "c1"

    def __init__(self, fail_on_enter=False):
        self.entered = 0
        self._fail = fail_on_enter

    def __enter__(self):
        if self._fail:
            raise RuntimeError("client deleted")
        self.entered += 1
        return self

    def __exit__(self, *exc):
        return False


def _in_client(monkeypatch, client):
    monkeypatch.setattr(mod, "context", SimpleNamespace(slot_stack=[object()], client=client))


def _hooks():
    session = SimpleNamespace(session_id="s1", context=SimpleNamespace(principal="ann"))
    return ErrorHooks(lambda cid: session if cid == "c1" else None)  # type: ignore[arg-type,return-value]


def test_a_ui_failure_is_recorded_with_session_context_and_toasted(ledger, notify, monkeypatch):
    client = _Client()
    _in_client(monkeypatch, client)
    _hooks().on_ui_exception(RuntimeError("boom"))
    entries = ledger.query().entries
    assert len(entries) == 1
    assert entries[0].operation == "UI handler"
    assert entries[0].error_context["principal"] == "ann"
    assert entries[0].error_context["session_id"] == "s1"
    notify.assert_called_once_with("Something went wrong — see Errors", type="negative")
    assert client.entered == 1


def test_a_leaked_refusal_is_toasted_and_not_recorded(ledger, notify, monkeypatch):
    _in_client(monkeypatch, _Client())
    _hooks().on_ui_exception(Refusal("Node is gone"))
    assert ledger.query().total == 0
    notify.assert_called_once_with("Node is gone", type="warning", multi_line=True)


def test_a_failure_without_a_client_is_recorded_and_not_toasted(ledger, notify, monkeypatch):
    monkeypatch.setattr(mod, "context", SimpleNamespace(slot_stack=[], client=None))
    _hooks().on_ui_exception(RuntimeError("boom"))
    assert ledger.query().total == 1
    notify.assert_not_called()


def test_a_leaked_refusal_without_a_client_is_logged_not_recorded(ledger, notify, monkeypatch, caplog):
    monkeypatch.setattr(mod, "context", SimpleNamespace(slot_stack=[], client=None))
    with caplog.at_level(logging.INFO, logger=mod.__name__):
        _hooks().on_ui_exception(Refusal("Node is gone"))
    assert ledger.query().total == 0
    notify.assert_not_called()
    assert any(r.levelno == logging.INFO and "Node is gone" in r.getMessage() for r in caplog.records)


def test_a_toast_into_a_deleted_client_does_not_raise(ledger, notify, monkeypatch):
    _in_client(monkeypatch, _Client(fail_on_enter=True))
    _hooks().on_ui_exception(RuntimeError("boom"))
    assert ledger.query().total == 1


def test_install_chains_and_uninstall_restores_the_previous_hooks(ledger, global_hooks):
    thread_prev, sys_prev = MagicMock(), MagicMock()
    threading.excepthook, sys.excepthook = thread_prev, sys_prev
    hooks = _hooks()
    hooks.install()
    assert threading.excepthook is not thread_prev
    assert sys.excepthook is not sys_prev
    assert hooks.on_ui_exception in app._exception_handlers

    exc = RuntimeError("x")
    sys.excepthook(RuntimeError, exc, None)
    sys_prev.assert_called_once_with(RuntimeError, exc, None)
    assert [e.operation for e in ledger.query().entries] == ["Uncaught"]

    hooks.uninstall()
    assert threading.excepthook is thread_prev
    assert sys.excepthook is sys_prev
    assert hooks.on_ui_exception not in app._exception_handlers


def test_a_thread_failure_is_recorded(ledger, global_hooks):
    threading.excepthook = MagicMock()
    hooks = _hooks()
    hooks.install()
    thread = threading.Thread(target=lambda: 1 / 0)
    thread.start()
    thread.join()
    entries = ledger.query().entries
    assert [e.operation for e in entries] == ["Thread"]
    hooks.uninstall()


def test_an_asyncio_loop_failure_is_recorded(ledger, global_hooks):
    previous = MagicMock()

    async def scenario():
        loop = asyncio.get_running_loop()
        loop.set_exception_handler(previous)
        hooks = _hooks()
        hooks.install()
        ctx = {"exception": RuntimeError("x"), "message": "x"}
        handler = loop.get_exception_handler()
        assert handler is not None
        handler(loop, ctx)
        hooks.uninstall()
        assert loop.get_exception_handler() is previous
        return ctx

    ctx = asyncio.run(scenario())
    assert [e.operation for e in ledger.query().entries] == ["Asyncio"]
    previous.assert_called_once()
    assert previous.call_args.args[1] is ctx


def test_an_asyncio_context_without_an_exception_is_passed_through_unrecorded(ledger):
    loop = MagicMock()
    hooks = _hooks()
    hooks.on_loop_exception(loop, {"message": "only a message"})
    assert ledger.query().total == 0
    loop.default_exception_handler.assert_called_once()
