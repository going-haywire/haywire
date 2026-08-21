"""ActivityEditor — what agent principals have been doing, as a readable list.

Opened from the account menu ("Agent activity"). That entry point is a panel in
this library rather than a click on the TopBar's agent chip, because the chip
lives in ``haywire.ui.app.shell`` and core must not name an editor owned by a
barn library.

Lives in the INFO slot for the same reason the Log and Errors editors do: it is
supplementary output you glance at, not a surface you edit in.

This replaces an earlier attempt to carry the same information in the presence
chip's tooltip. That failed for a concrete reason worth recording: several chips
each own a tooltip, they overlap when more than one principal is connected, and
the text gets clipped mid-word ("...sting_echo"). A tooltip is the wrong
container for a growing list — it cannot scroll, cannot be read at leisure, and
competes with its neighbours for the same screen space.

Reads the process-wide tracker on every draw rather than caching a snapshot,
and redraws on ``FarmhandActivity`` — so a call that starts while the tab is
open appears without the human doing anything.

Each row carries a detail button (settled 2026-08-18, see
``docs/superpowers/plans/2026-08-18-farmhand-activity-expansion.md``) opening
a ``Popup`` with the call's arguments/result. The popup is NiceGUI/Vue-owned
state once opened (its own close affordance, backdrop, Escape) — it survives
a ``FarmhandActivity``-triggered redraw of the row list underneath it because
it isn't part of that redraw's DOM subtree (``Popup`` attaches itself to the
page layout, not this editor's container — see ``Popup.__init__``). So this
editor still holds no state of its own; the earlier design considered here
(tracking open/closed per row token) turned out to be unnecessary once the
popup's own lifecycle was doing that job already.
"""

from __future__ import annotations

import json
import time

from haywire.core.access import AccessTier
from haywire.core.farmhand.activity import activity_tracker
from haywire.core.session.handlers import redraw_on
from haywire.core.signals import FarmhandActivity
from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from nicegui import ui

#: Rows to render. The tracker keeps more; this is what fits without turning a
#: glanceable list into a scroll marathon.
VISIBLE_ROWS = 30

#: Detail popup dimensions — fixed, not "auto": stacked JSON viewers need a
#: stable height to manage their own internal scroll (they support it, same
#: as any svelte-jsoneditor instance), and the tracker's own payload
#: truncation cap already bounds the worst case. Narrower/taller than the
#: original side-by-side layout, to suit Arguments-over-Result instead of
#: Arguments-beside-Result.
_DETAIL_WIDTH = "560px"
_DETAIL_HEIGHT = "640px"

#: ``ui.json_editor`` wraps svelte-jsoneditor, a third-party Svelte component
#: that ships its own light-only default styling and has no dark/light class
#: toggle in this build — the ONLY hook it exposes is the ``--jse-*`` custom
#: property set, applied here as an inline style so it renders in this app's
#: theme instead of its own. Mapped onto ``--hw-console-*`` (not
#: ``--hw-bg-surface``/``--hw-text-body``) because this is a monospace,
#: code-like readout — the same semantic role as ``LogEditor``'s ``ui.log``.
_JSE_THEME_STYLE = (
    "--jse-background-color: var(--hw-console-bg);"
    "--jse-panel-background: var(--hw-console-bg);"
    "--jse-contents-background-color: var(--hw-console-bg);"
    "--jse-text-color: var(--hw-console-text);"
    "--jse-text-color-inverse: var(--hw-console-bg);"
    "--jse-key-color: var(--hw-console-text);"
    "--jse-value-color-string: var(--hw-console-text);"
    "--jse-value-color-number: var(--hw-accent);"
    "--jse-value-color-boolean: var(--hw-accent);"
    "--jse-value-color-null: var(--hw-text-dim);"
    "--jse-value-color-url: var(--hw-accent);"
    "--jse-delimiter-color: var(--hw-text-dim);"
    "--jse-main-border: 1px solid var(--hw-border-strong);"
    "--jse-panel-border: 1px solid var(--hw-border-strong);"
    "--jse-panel-color: var(--hw-console-text);"
    "--jse-panel-color-readonly: var(--hw-text-dim);"
    "--jse-selection-background-color: var(--hw-bg-hover);"
    "--jse-hover-background-color: var(--hw-bg-hover);"
    "--jse-text-readonly: var(--hw-text-dim);"
)


def format_duration(seconds: float) -> str:
    """Human-scaled duration. Sub-second calls are the common case."""
    if seconds < 1.0:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60.0:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def format_age(seconds: float) -> str:
    """How long ago a call finished, relative like the presence chip's own text."""
    if seconds < 1.0:
        return "just now"
    if seconds < 60.0:
        return f"{int(seconds)}s ago"
    if seconds < 3600.0:
        return f"{int(seconds // 60)}m ago"
    return f"{int(seconds // 3600)}h ago"


@editor(
    label="Agent Activity",
    icon="smart_toy",
    default_slot="info",
    opens="on_context",
    description="Farmhand tool calls made by agent principals",
    access=AccessTier.VIEW,
)
class ActivityEditor(BaseEditor):
    """Running and recently-finished Farmhand tool calls, newest first.

    Access is VIEW: knowing what the agents in this studio are doing is exactly
    the kind of thing every collaborator benefits from seeing, and it discloses
    nothing a principal could not already infer from the graph changing under
    them. Same reasoning as the presence row itself.
    """

    @redraw_on(FarmhandActivity)
    def _on_activity(self, context, signal) -> None:
        """A tool call started or finished — repaint.

        The decorator's redraw already re-runs ``draw``; this body is
        deliberately empty because the editor holds no state of its own. Every
        value it shows is read from the tracker at draw time — including any
        open detail popup, which lives outside this redraw's DOM subtree (see
        module docstring).
        """

    def draw(self, context, container) -> None:
        container.clear()
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                self._render_header()
                with ui.column().classes("w-full gap-0 p-2"):
                    self._draw_body()

    # -- header -----------------------------------------------------------

    def _render_header(self) -> None:
        with (
            ui.row()
            .classes("w-full items-center px-3 gap-2 flex-shrink-0 border-b")
            .style("min-height: 32px; background: var(--hw-bg-surface);")
        ):
            ui.space()
            (
                ui.button(icon=hui.icon.clear, on_click=self._clear)
                .props("flat dense size=sm")
                .tooltip("Clear activity history")
            )

    def _clear(self) -> None:
        """Wipe finished-call history only.

        Never touches in-flight calls (stranding one mid-flight would mean it
        could never be seen finishing) or the persisted audit log — a UI
        button that could erase durable audit history would defeat the
        reason that log exists. See ``activity.py``'s ``clear_history``.
        """
        activity_tracker().clear_history()
        self.wrapper.redraw()

    # -- body -----------------------------------------------------------

    def _draw_body(self) -> None:
        tracker = activity_tracker()
        running = tracker.running_calls()
        finished = tracker.recent(VISIBLE_ROWS)

        if not running and not finished:
            hui.empty_state(
                "No agent activity yet",
                icon="smart_toy",
                hint="Farmhand tool calls from connected agents appear here.",
            )
            return

        now = time.monotonic()
        if running:
            hui.section_label(f"Running ({len(running)})")
            for record in running:
                self._draw_row(record, now, running=True)

        if finished:
            hui.section_label(f"Recent ({len(finished)})")
            for record in finished:
                self._draw_row(record, now, running=False)

    def _draw_row(self, record, now: float, *, running: bool) -> None:
        """One call. Status dot, tool name, principal, timing, detail button.

        Failures carry their error text on a second line rather than in a
        tooltip — the whole reason this editor exists is that a tooltip could
        not hold this much text legibly.
        """
        if running:
            dot, timing = "hw-text-info", format_duration(record.elapsed(now))
        elif record.ok:
            dot, timing = "hw-text-success", format_duration(record.elapsed())
        else:
            dot, timing = "hw-text-danger", format_duration(record.elapsed())

        with ui.column().classes("w-full gap-0 px-2 py-1 min-w-0"):
            with ui.row().classes("w-full items-center gap-2 min-w-0"):
                ui.icon("play_arrow" if running else ("check" if record.ok else "close")).classes(
                    f"text-xs {dot}"
                )
                ui.label(record.tool).classes("text-xs font-mono truncate flex-1 hw-text-body")
                ui.label(record.principal or "—").classes("text-xs hw-text-dim flex-shrink-0")
                ui.label(timing).classes("text-xs hw-text-dim flex-shrink-0 w-16 text-right")
                if not running:
                    age = now - (record.finished_at or now)
                    ui.label(format_age(age)).classes("text-xs hw-text-dim flex-shrink-0 w-16 text-right")
                # Icon-only, sized to match the status icon above (text-xs) —
                # never larger, per the design decision. Always present, even
                # while running (a running call still has arguments to show).
                (
                    ui.icon("data_object")
                    .classes("text-xs hw-text-dim flex-shrink-0 cursor-pointer")
                    .tooltip("View arguments/result")
                    .on("click", lambda _, r=record: self._open_detail(r))
                )
            if record.error:
                ui.label(record.error).classes("text-xs hw-text-danger pl-6 break-words")

    # -- detail popup -----------------------------------------------------

    def _open_detail(self, record) -> None:
        """Open the arguments/result popup for one row.

        A fresh ``Popup`` per click, not a toggled one — ``Popup`` already
        has its own close affordance (X / backdrop click / Escape), so there
        is no open/closed state to track here.
        """
        popup = Popup(
            title=record.tool,
            width=_DETAIL_WIDTH,
            height=_DETAIL_HEIGHT,
            closable=True,
            backdrop_click_close=True,
            escape_close=True,
        )
        with popup:
            with ui.column().classes("w-full h-full gap-2"):
                with ui.column().classes("w-full flex-1 gap-1 min-h-0"):
                    hui.section_label("Arguments")
                    _json_viewer(record.arguments)
                with ui.column().classes("w-full flex-1 gap-1 min-h-0"):
                    hui.section_label("Result")
                    _json_viewer(record.result)
        popup.open()


def _json_viewer(text: str | None):
    """One read-only ``ui.json_editor``, themed to match the app and sized to fill.

    ``mode`` defaults to ``"tree"`` — deliberately not ``"text"``: text mode
    expects ``content: {"text": ...}``, a different shape than the
    ``content: {"json": ...}`` used here; passing json-shaped content in text
    mode renders empty. Tree mode also reads better for structured
    arguments/results than a flat text blob would.
    """
    return (
        ui.json_editor({"content": {"json": _safe_loads(text) if text else None}, "readOnly": True})
        .classes("w-full flex-1")
        .style(_JSE_THEME_STYLE)
    )


def _safe_loads(text: str) -> object:
    """Parse a stored (already-serialized, possibly truncated) payload for display.

    Truncation can cut mid-token, leaving invalid JSON — the popup must show
    *something* readable rather than crash the draw. Falls back to the raw
    text itself, which ``json_editor`` still renders as a plain string.
    """
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text
