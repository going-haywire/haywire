"""Tests for the shared restart affordance.

The affordance's whole point is that quitting is offered, never forced, so
these check that the button exists, that it quits only when clicked, and that
it routes through the graceful ``app.shutdown()`` path rather than anything
abrupt.
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui.modals.restart_affordance import restart_affordance

# The package re-exports the function under the module's own name, rebinding
# the attribute on the package, so `haywire.ui.modals.restart_affordance`
# resolves to the FUNCTION, not the module. import_module goes to sys.modules
# and gets the module itself, which is what monkeypatch needs.
restart_module = importlib.import_module("haywire.ui.modals.restart_affordance")


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on the asyncio backend."""
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    """Provide a NiceGUI ``User`` simulator without requiring a main_file."""
    async with user_simulation() as u:
        yield u


@pytest.mark.unit
@pytest.mark.anyio
async def test_renders_restart_button(user: User) -> None:
    """The affordance renders a button labelled 'Restart Studio'."""
    captured: dict[str, ui.button] = {}

    @ui.page("/")
    def page() -> None:
        captured["button"] = restart_affordance()

    await user.open("/")

    assert captured["button"].text == "Restart Studio"


@pytest.mark.anyio
@pytest.mark.unit
async def test_does_not_shut_down_on_render(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Merely rendering the affordance must never quit the app."""
    calls: list[int] = []
    monkeypatch.setattr(restart_module.app, "shutdown", lambda: calls.append(1))

    @ui.page("/")
    def page() -> None:
        restart_affordance()

    await user.open("/")

    assert calls == []


@pytest.mark.unit
@pytest.mark.anyio
async def test_click_triggers_graceful_shutdown(user: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Clicking routes through ``app.shutdown()`` — the graceful path that lets
    lifespan handlers run, matching the framework update dialog."""
    calls: list[int] = []
    monkeypatch.setattr(restart_module.app, "shutdown", lambda: calls.append(1))

    @ui.page("/")
    def page() -> None:
        restart_affordance()

    await user.open("/")
    user.find("Restart Studio").click()

    assert calls == [1]


@pytest.mark.unit
@pytest.mark.anyio
async def test_custom_reason_is_rendered(user: User) -> None:
    """A caller-supplied reason replaces the generic leading sentence."""

    @ui.page("/")
    def page() -> None:
        restart_affordance(reason="Publishing bumped every barn library's version.")

    await user.open("/")

    await user.should_see("Publishing bumped every barn library's version.")


@pytest.mark.unit
@pytest.mark.anyio
async def test_warns_about_unsaved_work(user: User) -> None:
    """The static unsaved-work warning matches the update dialog's."""

    @ui.page("/")
    def page() -> None:
        restart_affordance()

    await user.open("/")

    await user.should_see("Unsaved work will be lost.")


@pytest.mark.unit
@pytest.mark.anyio
async def test_states_the_relaunch_command(user: User) -> None:
    """Shutdown does not relaunch, so the manual command must be visible."""

    @ui.page("/")
    def page() -> None:
        restart_affordance()

    await user.open("/")

    await user.should_see("uv run haywire")
