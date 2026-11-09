"""The flow meter drawn on a running graph's haystack row.

``FlowMeterView`` shows one bar for the worst Flow. A click opens a strip of one bar per Flow, grouped
by execution group, worst nearest the row's end. Everything the browser needs travels only when a bar
changes colour or step; the details of a Flow are written into its tooltip when the tooltip opens.
"""

from __future__ import annotations

from collections.abc import Callable

from haywire.core.execution.flow_metrics import FlowReading, MeterReading, Severity
from nicegui import ui

#: Fill steps of a bar; a bar is redrawn only when its step or colour changes.
STEPS = 10

_COLOURS = {
    Severity.OK: "var(--hw-success)",
    Severity.WARN: "var(--hw-warning)",
    Severity.ALERT: "var(--hw-danger)",
}

_BAR_STYLE = "width: 5px; height: 14px; flex: none; border-radius: 1px; overflow: hidden;"
_BAR_STYLE += " background: var(--hw-border); display: flex; align-items: flex-end;"


def fill_step(load: float) -> int:
    """Return the number of filled steps, 0 to ``STEPS``, for a load from 0 to 1."""
    return max(0, min(STEPS, round(load * STEPS)))


def bar_signature(flow: FlowReading) -> tuple[Severity, int]:
    """Return what a bar shows; two readings with the same signature draw the same bar."""
    return flow.severity, fill_step(max(flow.load, flow.group_load))


def strip_signature(reading: MeterReading) -> tuple:
    """Return what the whole strip shows: its Flows in order, each with its group and bar."""
    return tuple((f.flow_id, f.group_id, bar_signature(f)) for f in reading.flows)


def describe(flow: FlowReading, name: str) -> str:
    """Return the tooltip text for ``flow``, which is shown as ``name``."""
    mode = "drops by design" if flow.drop_mode else "blocks when full"
    lines = [
        f"{name} ({mode})",
        f"load {flow.load:.0%}, runner {flow.group_load:.0%}",
        f"{flow.frame_rate:.1f} frames/s",
    ]
    if flow.drop_mode:
        lines.append(f"dropped {flow.drop_rate:.0%} of triggers ({flow.dropped_total} in total)")
    else:
        lines.append(f"queue {flow.queue_depth}/{flow.queue_max}")
        lines.append(f"dropped {flow.dropped_total}" + (" (just now)" if flow.recently_dropped else ""))
    return "\n".join(lines)


class FlowMeterView:
    """The meter elements of one row; call ``update`` with each new reading.

    ``name_of`` maps a Flow's entry node id to the name shown in tooltips.
    """

    def __init__(self, name_of: Callable[[str], str]) -> None:
        self._name_of = name_of
        self._reading: MeterReading | None = None
        self._expanded = False
        self._bar_signature: tuple[Severity, int] | None = None
        self._strip_signature: tuple | None = None
        self._bar_fill: ui.element | None = None
        self._strip: ui.element | None = None
        self._tips: dict[str, ui.tooltip] = {}

    def build(self) -> None:
        """Draw the collapsed bar and the (empty) strip into the current container."""
        self._strip = ui.row().classes("items-center gap-0 no-wrap")
        self._strip.style("flex: 0 1000 auto; min-width: 0; overflow: hidden; flex-direction: row-reverse;")
        self._strip.set_visibility(False)
        with (
            ui.element("div").style(_BAR_STYLE + " cursor: pointer;").props("data-hw-mark=flow-meter") as bar
        ):
            self._bar_fill = ui.element("div").style("width: 100%; height: 0%;")
            self._tip = ui.tooltip("")
            self._tip.on("before-show", self._write_worst_tip)
        bar.on("click.stop", self._toggle)

    def update(self, reading: MeterReading) -> None:
        """Take a new reading; elements are touched only where the picture changed."""
        self._reading = reading
        worst = reading.worst
        signature = bar_signature(worst) if worst is not None else None
        if signature != self._bar_signature and self._bar_fill is not None:
            self._bar_signature = signature
            severity, step = signature or (Severity.OK, 0)
            self._bar_fill.style(
                f"width: 100%; height: {step * 100 // STEPS}%; background: {_COLOURS[severity]};"
            )
        if self._expanded:
            self._draw_strip()

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._strip is not None:
            self._strip.set_visibility(self._expanded)
        if self._expanded:
            self._strip_signature = None
            self._draw_strip()

    def _draw_strip(self) -> None:
        reading = self._reading
        if reading is None or self._strip is None:
            return
        signature = strip_signature(reading)
        if signature == self._strip_signature:
            return
        self._strip_signature = signature
        self._strip.clear()
        self._tips = {}
        previous_group = None
        with self._strip:
            for flow in reading.flows:
                gap = "margin-right: 5px;" if previous_group not in (None, flow.group_id) else ""
                previous_group = flow.group_id
                severity, step = bar_signature(flow)
                with ui.element("div").style(_BAR_STYLE + gap).props("data-hw-mark=flow-bar"):
                    ui.element("div").style(
                        f"width: 100%; height: {step * 100 // STEPS}%; background: {_COLOURS[severity]};"
                    )
                    tip = ui.tooltip("")
                    tip.on("before-show", lambda _e, fid=flow.flow_id: self._write_tip(fid))
                    self._tips[flow.flow_id] = tip

    def _write_tip(self, flow_id: str) -> None:
        """Fill a bar's tooltip from the latest reading, once, when it opens."""
        flow = (
            next((f for f in self._reading.flows if f.flow_id == flow_id), None) if self._reading else None
        )
        tip = self._tips.get(flow_id)
        if flow is not None and tip is not None:
            tip.set_text(describe(flow, self._name_of(flow.entry_node_id)))

    def _write_worst_tip(self, _event: object = None) -> None:
        worst = self._reading.worst if self._reading else None
        if worst is not None:
            self._tip.set_text(describe(worst, self._name_of(worst.entry_node_id)))
