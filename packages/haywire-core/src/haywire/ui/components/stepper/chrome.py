"""Popup shell for a step flow: progress bar, error banner, step dispatch.

Everything here is flow-agnostic — it reads only what :class:`StepFlow`
exposes. Per-step body content lives in the caller's own panel functions.
"""

from __future__ import annotations

from typing import Callable, Mapping, Optional, TypeVar

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

#: Renders extra detail inside the error banner, above the manual command.
#: Returning True suppresses the default single-line error label — used when a
#: flow carries structured failures worth one row each.
ErrorDetail = Callable[[FlowT, Callable[[], None]], bool]


def show_step_flow(
    flow: FlowT,
    panels: Mapping[str, Panel[FlowT]],
    *,
    title: str,
    width: str = "620px",
    on_done: Callable[[], None] | None = None,
    error_detail: ErrorDetail[FlowT] | None = None,
) -> Popup:
    """Open *flow* in a popup and return it.

    *panels* maps step name to its body renderer. *on_done* fires when the
    popup closes — a flow's terminal panel typically closes it, so this is
    where a caller refreshes whatever the flow changed.

    The popup stays closable throughout: a flow mutates nothing that needs
    undoing until its final step, so abandoning it early is always safe. The
    step buttons are the intended path, not the only one.
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
    message; it returns True when it has done so.
    """
    if flow.error is None:
        return
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
    ):
        ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
        with ui.column().classes("gap-1 flex-1"):
            handled = error_detail(flow, rerender) if error_detail is not None else False
            if not handled:
                ui.label(flow.error).classes("text-xs hw-text-danger whitespace-pre-line")
            if flow.manual_command:
                hui.code_snippet(flow.manual_command)

    def _retry() -> None:
        flow.retry()
        rerender()

    ui.button("Retry", on_click=_retry).props("flat dense")
