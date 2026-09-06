"""Graph-load progress modal — a blocking overlay while a large graph mounts.

Opening a big graph takes seconds (roughly 12 ms per widget-heavy node), and
the canvas fills in progressively because the load yields between nodes so the
server keeps serving other sessions. That progressive fill is exactly why this
modal has to BLOCK: for most of the load the canvas holds a partial graph —
some nodes mounted, the rest missing, and no edges at all, since those are
emitted in one batch at the very end. Dragging a node, drawing an edge, or
opening a context menu against that half-built state acts on a graph the user
can see is incomplete, and against Python-side registries (``node_panels``,
``edge_states``) still being written.

"Fully drawn" includes the edges, which is a client-side fact rather than a
Python one: the edge batch is one fire-and-forget websocket message, so the
loader explicitly waits for the browser to confirm it drew before this overlay
comes down (see ``VisualLayerHandlers._await_client_drawn``). Releasing on the
Python loop alone handed back a canvas with every node and zero edges.

The block is structural rather than policed: :class:`Popup` renders a
full-viewport backdrop (``inset: 0``, ``z-index: 5000``) above every canvas
layer (the canvas tops out at 1002), and with ``backdrop_click_close=False``
that backdrop swallows clicks rather than passing them through. Keyboard and
wheel are covered the same way — the overlay handles ``@wheel.self``, so
scroll-zoom over the backdrop does not reach the canvas.

Deliberately NOT reusing ``LibraryOperationProgressModal``: that handle's
terminal states are library semantics (``PostInstallHints``, reload/restart
affordances) and its ``finish()`` always waits for a click. A graph load has no
post-action and should get out of the way the moment it is done.
"""

from __future__ import annotations

import logging

from nicegui import ui

from haywire.ui.components.popup.popup import Popup

logger = logging.getLogger(__name__)


class GraphLoadModal:
    """Handle for the blocking load overlay. Create via :func:`graph_load_modal`."""

    def __init__(self, popup: Popup, label: "ui.label", bar: "ui.linear_progress", total: int):
        self._popup = popup
        self._label = label
        self._bar = bar
        self._total = max(total, 1)
        self._closed = False

    def advance(self, mounted: int, total: int | None = None) -> None:
        """Report progress: ``mounted`` of ``total`` nodes are on the canvas.

        ``total`` is accepted so this can be passed straight as the loader's
        ``on_progress(mounted, total)`` callback; it overrides the count given
        at construction, which matters if nodes were added between opening the
        overlay and starting the mount.
        """
        if self._closed:
            return
        if total:
            self._total = total
        self._label.set_text(f"Mounting nodes… {mounted} / {self._total}")
        self._bar.set_value(min(mounted / self._total, 1.0))

    def set_phase(self, text: str) -> None:
        """Replace the readout with a phase message and show an indeterminate bar.

        Used when the load leaves per-node mounting for a step with no useful
        numerator — the edge batch, which is one message drawn client-side.
        """
        if self._closed:
            return
        self._label.set_text(text)
        self._bar.props("indeterminate")

    def close(self) -> None:
        """Dismiss the overlay, handing interaction back to the canvas.

        Idempotent: the load's success path and its cancellation/failure path
        both call this, and the editor may already have torn the popup down.
        """
        if self._closed:
            return
        self._closed = True
        try:
            self._popup.close()
            self._popup.delete()
        except Exception as exc:  # dead client, or slot already gone
            logger.debug(f"GraphLoadModal: close raised (client gone?): {exc}")


def graph_load_modal(*, graph_name: str, total_nodes: int) -> GraphLoadModal:
    """Open the blocking load overlay and return its handle.

    Args:
        graph_name: Shown in the title, so a user with several tabs open knows
            which graph is loading.
        total_nodes: Denominator for the progress readout.
    """
    popup = Popup(
        title=f"Opening {graph_name}…",
        width="380px",
        closable=False,
        backdrop_click_close=False,
        escape_close=False,
    )

    with popup:
        with ui.column().classes("w-full gap-2 p-1"):
            label = ui.label(f"Mounting nodes… 0 / {total_nodes}").classes("text-xs hw-text-muted")
            bar = ui.linear_progress(value=0.0, show_value=False).props("rounded").classes("w-full")
            ui.label("The canvas is locked until the graph is fully drawn.").classes("text-xs hw-text-dim")

    popup.open()
    return GraphLoadModal(popup=popup, label=label, bar=bar, total=total_nodes)
