"""Smoke tests for LibraryOperationProgressModal.finish() terminal-state branching.

These exercise the visibility / label / callback wiring rather than full DOM
rendering. The modal is constructed inside a NiceGUI page context using the
nicegui ``user_simulation`` helper directly (avoiding the user_plugin's
``main_file`` requirement, which is geared at full-app tests).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.ui.modals.install_progress_modal import (
    LibraryOperationProgressModal,
    PostInstallHints,
    library_operation_progress_modal,
)


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
async def test_finish_no_flags_shows_done_button(user: User) -> None:
    """No flags → button label 'Done', no notice, no reload callback."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints())
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    # Spinner is hidden, terminal row is visible, button label is "Done".
    assert modal._spinner_row.visible is False
    assert modal._done_row[0].visible is True
    assert modal._done_row[1].text == "Done"
    # Restart instructions panel is hidden.
    assert modal._restart_instructions.visible is False
    # Reload notice is hidden.
    assert modal._reload_notice.visible is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_needs_refresh_shows_reload_button(user: User) -> None:
    """needs_refresh=True → button 'Reload the page' and the reload notice is visible."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_refresh=True))
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    assert modal._done_row[1].text == "Reload the page"
    assert modal._reload_notice.visible is True
    assert modal._restart_instructions.visible is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_needs_restart_shows_restart_button(user: User) -> None:
    """needs_restart=True → button 'How to restart Studio'; click reveals instructions."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_restart=True))
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    assert modal._done_row[1].text == "How to restart Studio"
    # Instructions panel starts hidden (revealed on click).
    assert modal._restart_instructions.visible is False
    # Refresh notice is hidden — restart subsumes refresh.
    assert modal._reload_notice.visible is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_restart_subsumes_refresh(user: User) -> None:
    """Both flags True → restart UX wins; refresh notice stays hidden."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_refresh=True, needs_restart=True))
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    assert modal._done_row[1].text == "How to restart Studio"
    assert modal._reload_notice.visible is False


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_with_error_shows_close_and_keeps_banner(user: User) -> None:
    """error=<msg> → banner visible, label 'Close', no reload/restart wiring."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(error="Install failed: out of disk")
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    assert modal._error_banner[1].visible is True
    assert modal._error_banner[0].text == "Install failed: out of disk"
    assert modal._done_row[1].text == "Close"


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_with_error_and_restart_shows_both(user: User) -> None:
    """error + needs_restart → banner visible AND restart button (per Q12.A)."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(
            error="Install failed: pip exit 1",
            hints=PostInstallHints(needs_restart=True),
        )
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    assert modal._error_banner[1].visible is True
    assert modal._done_row[1].text == "How to restart Studio"


def _click_listeners(button: ui.button) -> list:
    """Return the click ``EventListener`` objects registered on ``button``.

    NiceGUI stores listeners on ``Element._event_listeners`` keyed by listener
    id; each listener exposes ``.type`` as camelCase (``'click'`` for click).
    Used to regression-test the handler-stacking bug: the old construction-
    time ``on_click=popup.close`` plus a ``finish()``-time ``.on('click', …)``
    would yield TWO click listeners; the fixed version yields exactly ONE.
    """
    return [listener for listener in button._event_listeners.values() if listener.type == "click"]


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_restart_registers_exactly_one_click_handler(user: User) -> None:
    """needs_restart terminal state must register exactly one click handler.

    Regression guard: the old code wired ``on_click=popup.close`` at button
    construction, so adding the restart-instructions handler via ``.on()``
    in ``finish()`` produced TWO listeners. Clicking the button then both
    revealed the instructions AND closed the popup, breaking the UX.
    """
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_restart=True))
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    listeners = _click_listeners(modal._done_row[1])
    assert len(listeners) == 1, (
        f"Expected exactly 1 click listener on the restart button "
        f"(handler stacking would yield 2), got {len(listeners)}."
    )


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_done_registers_exactly_one_click_handler(user: User) -> None:
    """No-flags 'Done' button must register exactly one click handler that
    closes the popup. Regression-guards the implicit-else branch that used
    to rely on the construction-time ``on_click=popup.close``."""
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints())
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    listeners = _click_listeners(modal._done_row[1])
    assert len(listeners) == 1, (
        f"Expected exactly 1 click listener on the Done button, got {len(listeners)}."
    )


@pytest.mark.unit
@pytest.mark.anyio
async def test_finish_is_idempotent(user: User) -> None:
    """Calling finish() twice must not stack handlers or re-toggle state.

    The second call must be a no-op — the first call's button label,
    notice visibility, and click-listener count are preserved.
    """
    captured: dict[str, LibraryOperationProgressModal] = {}

    @ui.page("/")
    def page() -> None:
        modal = library_operation_progress_modal(title="Installing test…")
        modal.finish(hints=PostInstallHints(needs_restart=True))
        # Second call with a different state — must be a no-op.
        modal.finish(hints=PostInstallHints(needs_refresh=True))
        captured["modal"] = modal

    await user.open("/")
    modal = captured["modal"]

    # First call's state preserved: restart label, no reload notice.
    assert modal._done_row[1].text == "How to restart Studio"
    assert modal._reload_notice.visible is False
    # Click handler from the first call was NOT joined by a second one.
    listeners = _click_listeners(modal._done_row[1])
    assert len(listeners) == 1, f"Double finish() must not stack click listeners, got {len(listeners)}."
