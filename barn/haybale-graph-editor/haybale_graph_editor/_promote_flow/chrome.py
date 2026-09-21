"""Popup entry point and step→panel wiring for the Promote to Macro flow."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable

from haywire.ui.components.stepper import Panel, show_step_flow

from ._state import PromoteFlow, PromoteSource
from .panels import _panel_name, _panel_planned, _panel_promoted

if TYPE_CHECKING:
    from haywire.core.graph.editor import Editor
    from haywire.core.macro.promote import PromotableSubgraph, PromotionTarget


class EditorPromoteSource:
    """Adapts the graph editor and library system to :class:`PromoteSource`.

    Registration and the card swap live in different places — the macro
    registry and the editor's undo stack — so this joins them at the boundary
    rather than widening the protocol to both.
    """

    def __init__(self, editor: "Editor", library_system) -> None:
        self._editor = editor
        self._library_system = library_system

    def register_macro_file(self, path: Path, library_id: str) -> str | None:
        """Register the written file so its key resolves before the card swaps.

        Synchronous on purpose: the watcher's later CREATED event is a no-op
        by content hash, and waiting for it would leave the placement pointing
        at a key that does not resolve yet.
        """
        registry = self._library_system.get_macro_registry()
        identity = self._library_system.get_library_registry().get_library_identity(library_id)
        return registry.register_file(str(path), identity)

    def swap_card_for_placement(self, node_id: str, registry_key: str) -> tuple[str | None, str | None]:
        return self._editor.promote_to_macro(node_id, registry_key)


def show_promote_flow(
    source: PromoteSource,
    definition: "PromotableSubgraph",
    node_id: str,
    targets: list["PromotionTarget"],
    *,
    on_done: Callable[[], None] | None = None,
) -> PromoteFlow:
    """Open the Promote to Macro flow and return its state machine.

    *on_done* fires when the popup closes — the caller resyncs its canvas
    there, since a completed promotion replaced a card.
    """
    flow = PromoteFlow(
        source=source,
        definition=definition,
        node_id=node_id,
        targets=targets,
    )

    panels: dict[str, Panel[PromoteFlow]] = {
        "name": _panel_name,
        "planned": _panel_planned,
        # on_done fires from the popup's close handler, so Done only dismisses.
        "promoted": lambda f, _rerender: _panel_promoted(f, None),
    }

    flow.popup = show_step_flow(
        flow,
        panels,
        title="Promote to Macro",
        width="560px",
        on_done=on_done,
    )
    return flow
