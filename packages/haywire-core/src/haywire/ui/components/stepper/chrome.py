"""Popup shell for a step flow: progress bar, error banner, step dispatch.

Everything here is flow-agnostic — it reads only what :class:`StepFlow`
exposes. Per-step body content lives in the caller's own panel functions.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional, TypeVar, Union

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup

from .flow import StepFlow

#: Panels and error-detail renderers are written against a concrete StepFlow
#: subclass, so both aliases are generic in it — a wizard can type its panels
#: as taking its own flow class without casting at the call site.
FlowT = TypeVar("FlowT", bound=StepFlow)

#: A panel renders one step's body. It receives the flow and a re-render
#: callback to invoke after a transition.
Panel = Callable[[FlowT, Callable[[], None]], None]

#: A replacement for the error banner's default "Retry" button: the label to
#: show and the handler to run on click, instead of `flow.retry()`.
ErrorButtonOverride = tuple[str, Callable[[], None]]

#: Renders extra detail inside the error banner, above the manual command.
#: Returns either a bool (True suppresses the default single-line error
#: label — used when a flow carries structured failures worth one row each)
#: or an `ErrorButtonOverride`, which replaces the bottom "Retry" button with
#: the given (label, on_click) pair — used when "Retry" doesn't describe what
#: the button should do (e.g. the share wizard's preconditions step, where
#: the action is "open a fix modal", not "clear the error and try again").
#:
#: The two are independent: returning an override does NOT suppress the error
#: label. A banner that renders only a button tells the user nothing about
#: what went wrong, so suppressing the message is opt-in via `True` and never
#: a side effect of customising the button.
ErrorDetail = Callable[[FlowT, Callable[[], None]], Union[bool, ErrorButtonOverride]]


def show_step_flow(
    flow: FlowT,
    panels: Mapping[str, Panel[FlowT]],
    *,
    title: str,
    width: str = "620px",
    on_done: Callable[[], None] | None = None,
    error_detail: ErrorDetail[FlowT] | None = None,
    auto_start: bool = False,
) -> Popup:
    """Open *flow* in a popup and return it.

    *panels* maps step name to its body renderer. *on_done* fires when the
    popup closes — a flow's terminal panel typically closes it, so this is
    where a caller refreshes whatever the flow changed.

    The popup stays closable throughout: a flow mutates nothing that needs
    undoing until its final step, so abandoning it early is always safe. The
    step buttons are the intended path, not the only one.

    *auto_start* runs the first step's ``advance_from_<step>`` as soon as the
    popup opens, instead of waiting for a click. For a first step that only
    CHECKS — no decision to make, nothing written — that click asks the user to
    confirm an intent they already expressed by opening the flow. Opt-in
    because it is wrong for a first step that presents a choice, and because a
    flow whose first step mutates must never run unprompted.

    The advance is scheduled with ``ui.timer(..., once=True)`` rather than
    awaited here: ``show_step_flow`` is sync (it returns the Popup its caller
    keeps), and the first render must reach the browser before a step that
    takes seconds begins, or the popup appears already-stalled.
    """
    missing = [s for s in flow.STEPS if s not in panels]
    if missing:
        raise ValueError(f"No panel for step(s): {', '.join(missing)}")

    popup = Popup(
        title=title,
        width=width,
        closable=True,
        backdrop_click_close=False,
        escape_close=False,
    )

    with popup:
        body = ui.column().classes("w-full gap-2")

    def _render() -> None:
        body.clear()
        with body:
            render_progress(flow)
            render_warnings(flow)
            render_error(flow, _render, error_detail)
            panels[flow.step](flow, _render)

    flow.on_render = _render
    _render()
    if on_done is not None:
        popup.on_close(on_done)
    popup.open()
    if auto_start:

        async def _start() -> None:
            await flow.advance()
            _render()

        # once=True fires on the next tick, after this render has been flushed.
        ui.timer(0.05, _start, once=True)
    return popup


def render_progress(flow: StepFlow) -> None:
    """A one-line step indicator. Colours come from --hw-* tokens only."""
    steps = list(flow.STEPS)
    index = steps.index(flow.step)
    with ui.row().classes("w-full items-center gap-1"):
        for position, name in enumerate(steps[:-1]):
            done = position < index
            active = position == index
            colour = "var(--hw-positive)" if done else ("var(--hw-accent)" if active else "var(--hw-border)")
            ui.element("div").classes("flex-1 rounded").style(f"height: 3px; background: {colour};").tooltip(
                flow.STEP_TITLES.get(name, name)
            )
    ui.label(flow.STEP_TITLES.get(flow.step, flow.step)).classes("text-sm font-medium")


def render_warnings(flow: StepFlow) -> None:
    for warning in flow.warnings:
        with ui.row().classes("w-full items-start gap-2"):
            ui.icon("warning", size="14px").classes("flex-shrink-0 mt-0.5").style(
                "color: var(--hw-warning);"
            )
            ui.label(warning).classes("text-xs hw-text-muted")


def render_error(
    flow: FlowT,
    rerender: Callable[[], None],
    error_detail: Optional[ErrorDetail[FlowT]] = None,
) -> None:
    """Inline error banner with a Retry button.

    *error_detail* may render structured failure rows in place of the plain
    message (returning True when it has done so), and/or replace the default
    Retry button by returning an `(label, on_click)` pair instead of a bool —
    see `ErrorDetail`'s docstring for when that's the right call. The two are
    independent: a button override alone still shows the error message.
    """
    if flow.error is None:
        return
    button_override: ErrorButtonOverride | None = None
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
    ):
        ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
        with ui.column().classes("gap-1 flex-1"):
            result = error_detail(flow, rerender) if error_detail is not None else False
            if isinstance(result, tuple):
                button_override = result
                handled = False
            else:
                handled = result
            if not handled:
                ui.label(flow.error).classes("text-xs hw-text-danger whitespace-pre-line")
            if flow.manual_command:
                hui.code_snippet(flow.manual_command)

    if button_override is not None:
        label, on_click = button_override
        ui.button(label, on_click=on_click).props("flat dense")
        return

    def _retry() -> None:
        flow.retry()
        rerender()

    ui.button("Retry", on_click=_retry).props("flat dense")
