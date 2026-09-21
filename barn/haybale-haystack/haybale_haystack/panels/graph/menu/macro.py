"""EditMacroMenuPanel — "Edit Macro…" on a macro placement's context menu.

A panel on **haybale-graph-editor's** ``SelectionMenu``, hosted here because
opening a document is this library's act: it adds the macro to the in-memory
registry (as an :class:`EntryKind.MACRO` entry) and reveals a GraphEditor tab
over it. The same split ``OpenInHaystackMenuPanel`` makes on haybale-studio's
``FileMenu``.

Promotion is the other half of the macro story and lives in graph-editor
instead, because it only mutates the graph being edited.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haybale_graph_editor.editors.graph_editor import GraphEditor
from haybale_graph_editor.panels._gating import is_macro_placement
from haybale_graph_editor.state.edit_state import EditState
from haybale_graph_editor.surfaces import SelectionActions, SelectionMenu
from haywire.core.signals import Reveal
from haywire.ui import elements as hui
from haywire.ui.panel import BasePanel
from haywire.ui.panel.decorator import panel
from haywire.ui.panel.layout import PanelLayout

from haybale_haystack.state.haystack_state import HaystackState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


@panel(
    surface=SelectionMenu,
    label="Edit Macro",
    icon=hui.icon.node_source,
    order=37,
)
class EditMacroMenuPanel(BasePanel):
    """Open the document behind a macro placement, in its own editor tab.

    Only visible on a placement. Descending into one is refused — its interior
    is runtime state rebuilt from the template, so there is nothing there to
    edit in place — and this row is what the gesture resolves to instead.
    """

    # Declared because ``SelectionMenu.provides`` is isinstance-checked against
    # the host. Unused: this panel calls HaystackState rather than a verb on
    # the graph editor.
    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_macro_placement(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        registry_key = wrapper.registry_key

        with layout:
            hui.menu_row(
                "Edit Macro…",
                icon=hui.icon.node_source,
                tooltip="Open this macro's own document in an editor",
                on_click=lambda: _open_macro(ctx, registry_key),
            )


def _open_macro(ctx: "SessionContext", registry_key: str) -> None:
    """Open the macro behind ``registry_key`` and reveal its tab.

    Refused with the reason when the library's files are not the ones on disk:
    a read-only install cannot be edited in place, and saying so beats opening
    an editor whose Save would go nowhere.
    """
    from nicegui import ui

    from haywire.core.di.config import get_library_system
    from haywire.core.macro.source import macro_edit_refusal, macro_source_path

    try:
        library_system = get_library_system()
    except Exception:
        ui.notify("The library system is unavailable", type="negative")
        return

    refusal = macro_edit_refusal(registry_key, library_system)
    if refusal is not None:
        ui.notify(refusal, type="warning", multi_line=True)
        return

    path = macro_source_path(registry_key)
    if path is None or not path.exists():
        ui.notify(f"The document for '{registry_key}' could not be found", type="warning")
        return

    hs = ctx.app_data.get(HaystackState)
    if hs is None:
        ui.notify("Graph manager not available", type="negative")
        return

    entry = hs.open_macro(path)
    ctx.session.publish(Reveal(editor=GraphEditor, binding_id=entry.binding_id, label=entry.display_name))
