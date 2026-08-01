"""Coroutine wrappers that re-render after an advance step, one plain / one busy-button."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from ._state import ShareWizard


def _advance(wizard: ShareWizard, rerender: Callable[[], None], coro_factory):
    """Wrap an advance call so the panel re-renders afterwards.

    Returns the coroutine rather than scheduling it: NiceGUI wraps a returned
    Awaitable with the parent slot before scheduling, which is what keeps
    ui.notify() and element creation working. Scheduling it ourselves would
    hand the work a task with an empty slot stack.
    See .insights/feedback_nicegui_async.md.
    """

    async def _run():
        await coro_factory()
        rerender()

    return _run()


def _busy_advance(
    wizard: ShareWizard,
    rerender: Callable[[], None],
    button: ui.button,
    coro_factory,
):
    """Put *button* in a loading state for the duration of the step.

    These steps take seconds (a network round-trip, a multi-library scan), so
    without this the UI looks dead while the thread works. Returned, not
    scheduled — see :func:`_advance` for why.
    """

    async def _run():
        button.props("loading")
        try:
            await coro_factory()
        finally:
            # The panel is about to be rebuilt, but the button survives when a
            # step fails and re-renders in place.
            button.props(remove="loading")
        rerender()

    return _run()
