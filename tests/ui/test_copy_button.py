"""_copy_button reports success and failure rather than failing silently."""

import inspect

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"


def test_handler_is_async_so_it_can_await_the_result():
    """A fire-and-forget handler cannot know whether the copy worked."""
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._copy_button)
    assert "async def" in source


def test_handler_notifies_on_both_outcomes():
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._perform_copy)
    assert source.count("ui.notify") >= 2


def test_failure_message_names_the_cause():
    """A user on a LAN studio should learn WHY, not just that it failed."""
    from haywire.ui.elements import elements

    source = inspect.getsource(elements._copy_button)
    assert "HTTPS" in source or "secure" in source.lower()


@pytest.mark.anyio
async def test_copy_handler_notifies_success(monkeypatch):
    from haywire.ui.elements import elements

    notified = []
    monkeypatch.setattr(elements.ui, "notify", lambda message, **kw: notified.append((message, kw)))

    async def _fake_run_javascript(script, **kwargs):
        return True

    monkeypatch.setattr(elements.ui, "run_javascript", _fake_run_javascript)

    await elements._perform_copy("secret")

    assert notified
    assert "Copied" in notified[0][0]


@pytest.mark.anyio
async def test_copy_handler_notifies_failure(monkeypatch):
    from haywire.ui.elements import elements

    notified = []
    monkeypatch.setattr(elements.ui, "notify", lambda message, **kw: notified.append((message, kw)))

    async def _fake_run_javascript(script, **kwargs):
        return False

    monkeypatch.setattr(elements.ui, "run_javascript", _fake_run_javascript)

    await elements._perform_copy("secret")

    assert notified
    assert notified[0][1].get("type") == "negative"


@pytest.mark.anyio
async def test_copy_handler_notifies_failure_when_javascript_raises(monkeypatch):
    """The likeliest real-world failure: run_javascript times out on a slow LAN link."""
    from haywire.ui.elements import elements

    notified = []
    monkeypatch.setattr(elements.ui, "notify", lambda message, **kw: notified.append((message, kw)))

    async def _boom(script, **kwargs):
        raise TimeoutError("JavaScript did not respond within 1.0 s")

    monkeypatch.setattr(elements.ui, "run_javascript", _boom)

    await elements._perform_copy("secret")

    assert notified
    assert notified[0][1].get("type") == "negative"
