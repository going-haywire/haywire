"""HistoryEditor — the undo history of the active graph's file, read-only."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from nicegui import ui

from haywire.core.access import AccessTier
from haywire.core.graph.base import BaseGraph
from haywire.core.session.handlers import redraw_on
from haywire.core.signals import ActiveGraphMoved, GraphHistoryChanged
from haywire.core.undo.origin import HistoryEntry, HistoryMove
from haywire.ui import elements as hui
from haywire.ui.editor.base import BaseEditor
from haywire.ui.editor.decorator import editor
from haywire.ui.editor.identity import SlotName
from haywire.ui.editor.wrapper import EditorWrapper

from haybale_graph_editor.protocols import GraphContainer
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.state.graph_app_state import GraphAppState

if TYPE_CHECKING:
    from nicegui.element import Element

    from haywire.core.session.context import SessionContext


def _clock(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if timestamp else ""


def graph_path(root: BaseGraph, graph: Any) -> Optional[list[str]]:
    """Return the Subgraph labels from ``root`` down to ``graph``; ``[]`` at ``root``, ``None`` outside."""
    if graph is root:
        return []
    for definition in root.subgraphs.values():
        below = graph_path(definition, graph)
        if below is not None:
            return [definition.label, *below]
    return None


def file_container(context: "SessionContext") -> Optional[GraphContainer]:
    """Return the container of the file holding the session's active graph, or ``None``.

    An interior's file is the one holding its outermost host, so a Group or macro
    interior resolves to the document it belongs to.
    """
    graph = context.data[EditState].active_graph
    if graph is None:
        return None
    return context.app_data[GraphAppState].get_by_graph(graph.root_graph)


@editor(
    label="History",
    icon=hui.icon.history,
    default_slot=SlotName.CONTEXT,
    description="The undo history of the active graph's file: every step, who recorded it, and where.",
    order=70,
    requires=AccessTier.EDIT,
)
class HistoryEditor(BaseEditor):
    """Lists the undo history of the file the active graph belongs to, newest step on top.

    The list covers the whole file: a step inside a Group or macro interior shows
    the interior's path. Each step names who recorded it — a session (principal and
    a short session id) or a Farmhand call. Steps past the undo marker are dimmed:
    Redo would apply them again. The marker names who last moved it. Steps still
    waiting in the grouping window are tagged `pending`; a closing fence shows as
    a divider. Click a row to see its details; click a group to see its steps.

    The list is read-only: it does not undo or redo.
    """

    def __init__(self, wrapper: EditorWrapper) -> None:
        super().__init__(wrapper)
        # Row keys whose details are open, kept across redraws.
        self._open: set[str] = set()

    @redraw_on(ActiveGraphMoved, GraphHistoryChanged)
    def _on_history(self, ctx: "SessionContext", signal: object) -> None:
        pass

    def draw(self, context: "SessionContext", container: "Element") -> None:
        document = file_container(context)
        with container:
            with ui.column().classes("w-full h-full gap-0"):
                with hui.slot_header(
                    f"History · {document.display_name}" if document else "History", icon=hui.icon.history
                ):
                    pass
                if document is None:
                    hui.empty_state("Open a graph to see its undo history.", icon=hui.icon.history)
                    return
                history = document.editor.history_manager
                rows = history.snapshot()
                if not rows:
                    hui.empty_state("Nothing to undo yet.", icon=hui.icon.history)
                    return
                root = document.editor.graph
                with ui.scroll_area().classes("flex-1 w-full"):
                    with ui.column().classes("w-full gap-0 py-1"):
                        self._draw_rows(rows, root, history.last_move())

    def _draw_rows(self, rows: list[HistoryEntry], root: BaseGraph, move: Optional[HistoryMove]) -> None:
        """Draw ``rows`` newest first, with the undo marker between the redo branch and the rest."""
        marked = False
        for index in reversed(range(len(rows))):
            row = rows[index]
            if not marked and not row.undone and row.kind != "fence":
                self._draw_marker(move)
                marked = True
            self._draw_row(row, root, key=str(index))
        if not marked:
            self._draw_marker(move)

    @staticmethod
    def _draw_marker(move: Optional[HistoryMove]) -> None:
        with ui.row().classes("w-full items-center no-wrap gap-2 px-2 py-1"):
            ui.icon(hui.icon.undo, size="14px").style("color: var(--hw-accent)")
            text = "Now"
            if move is not None:
                who = move.origin.label if move.origin is not None else "unknown"
                text = f"Now · last {move.direction} by {who} at {_clock(move.timestamp)}"
            ui.label(text).classes("text-xs truncate").style("color: var(--hw-accent)")

    def _draw_row(self, row: HistoryEntry, root: BaseGraph, *, key: str, depth: int = 0) -> None:
        if row.kind == "fence":
            with ui.row().classes("w-full items-center no-wrap gap-2 px-2"):
                hui.separator().classes("flex-1")
                hui.hint("fence")
            return

        is_open = key in self._open
        line = ui.row().classes(
            "w-full items-center no-wrap gap-2 px-2 py-1 cursor-pointer hw-list-item-hover"
        )
        if row.undone:
            line.classes("opacity-50")
        if depth:
            line.style(f"padding-left: calc(var(--hw-inset) * {depth + 1})")
        line.on("click", lambda _e=None, k=key: self._toggle(k))
        with line:
            if row.kind == "group":
                ui.icon(hui.icon.fold_open if is_open else hui.icon.fold_closed, size="14px").classes(
                    "hw-text-dim"
                )
            with ui.column().classes("flex-1 gap-0 min-w-0"):
                ui.label(row.description).classes("text-sm hw-text-body truncate")
                hui.hint(self._sublabel(row, root)).classes("truncate")
            if row.pending:
                hui.tag("pending")

        if not is_open:
            return
        if row.kind == "group":
            for index, child in enumerate(row.children):
                self._draw_row(child, root, key=f"{key}.{index}", depth=depth + 1)
        else:
            with ui.column().classes("w-full gap-0 px-2 pb-1"):
                hui.info_row("Type", row.action_type)
                hui.info_row("By", row.origin.label if row.origin is not None else "unknown")
                if row.origin is not None:
                    hui.info_row("Via", row.origin.via)
                hui.info_row("Graph", self._graph_label(row, root))
                hui.info_row("Time", _clock(row.timestamp))
                if row.merge_key is not None:
                    hui.info_row("Merging", repr(row.merge_key[0]))

    def _toggle(self, key: str) -> None:
        self._open.symmetric_difference_update({key})
        self.wrapper.redraw()

    @classmethod
    def _sublabel(cls, row: HistoryEntry, root: BaseGraph) -> str:
        who = row.origin.label if row.origin is not None else "unknown"
        return " · ".join(part for part in (who, cls._graph_label(row, root), _clock(row.timestamp)) if part)

    @staticmethod
    def _graph_label(row: HistoryEntry, root: BaseGraph) -> str:
        """Return the step's interior path; ``""`` for the file's top level, a note for a gone interior."""
        if row.graph is None:
            return ""
        path = graph_path(root, row.graph)
        if path is None:
            return "(removed interior)"
        return " › ".join(path)
