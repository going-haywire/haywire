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
"""

from __future__ import annotations

import time

from haywire.core.access import AccessTier
from haywire.core.session.handlers import redraw_on
from haywire.core.session.signals import FarmhandActivity
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from nicegui import ui

#: Rows to render. The tracker keeps more; this is what fits without turning a
#: glanceable list into a scroll marathon.
VISIBLE_ROWS = 30


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
        value it shows is read from the tracker at draw time.
        """

    def draw(self, context, container) -> None:
        container.clear()
        with container:
            with ui.column().classes("w-full gap-0 p-2"):
                self._draw_body()

    # -- body -----------------------------------------------------------

    def _draw_body(self) -> None:
        try:
            from haywire_studio.farmhand.activity import activity_tracker
        except ImportError:
            # Core may be embedded without the studio package present.
            hui.empty_state("Activity tracking unavailable", icon="smart_toy")
            return

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
        """One call. Status dot, tool name, principal, timing.

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
            if record.error:
                ui.label(record.error).classes("text-xs hw-text-danger pl-6 break-words")
