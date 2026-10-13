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
from haybale_graph_editor.panels._gating import is_macro_placement, is_modified_instance
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

    Only visible on a placement. Its interior is runtime state rebuilt from the
    template, so it cannot be edited in place; this row opens the document that
    can.
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


@panel(
    surface=SelectionMenu,
    label="Update Macro",
    icon=hui.icon.node_source,
    order=40,
)
class UpdateMacroMenuPanel(BasePanel):
    """Send a modified instance's changes back to the macro it came from.

    Only visible on a Group that was detached from a macro. The card becomes a
    placement of that macro again, and the macro opens in its own tab with the
    instance's contents, unsaved. Saving it updates every placement.

    Greyed out when the macro is not installed, cannot be edited in place, or
    has unsaved edits in its tab.
    """

    # Declared because ``SelectionMenu.provides`` is isinstance-checked against
    # the host. Unused: this panel calls HaystackState rather than a verb on
    # the graph editor.
    actions: SelectionActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        return is_modified_instance(ctx)

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        from haywire.core.macro.source import origin_label

        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        node_id = wrapper.node_id
        definition = getattr(wrapper.node, "resolve_definition", lambda: None)()
        origin = getattr(definition, "origin", None)
        if origin is None:
            return
        label = origin_label(definition)
        refusal = _update_refusal(origin.key, label, ctx.app_data.get(HaystackState))

        with layout:
            hui.menu_row(
                "Update Macro…",
                icon=hui.icon.node_source,
                enabled=refusal is None,
                tooltip=refusal
                or (
                    f"Replace this card with a placement of {label}, and open {label} "
                    "with this instance's changes to save"
                ),
                on_click=lambda: _update_macro(ctx, node_id),
            )


def _update_refusal(registry_key: str, label: str, hs: HaystackState | None) -> str | None:
    """Why the macro ``registry_key`` cannot take an instance's changes now, or ``None``."""
    from haywire.core.di.config import get_library_system
    from haywire.core.macro.source import macro_edit_refusal, macro_template

    template = macro_template(registry_key)
    if template is None:
        return f"{label} is not installed."
    try:
        library_system = get_library_system()
    except Exception:
        return "The library system is unavailable"
    refusal = macro_edit_refusal(registry_key, library_system)
    if refusal is not None:
        return refusal
    entry = hs.get_by_path(template.path) if hs is not None else None
    if entry is not None and entry.unsaved:
        return f"{label} has unsaved edits in its macro tab. Save them first."
    return None


def _update_macro(ctx: "SessionContext", node_id: str) -> None:
    """Swap the modified instance on ``node_id`` for a placement, and open its macro with its contents.

    The swap is one undoable step on the host graph. The macro's tab holds the
    instance's contents, unsaved; nothing is written until the user saves it.
    Refused with a notice, before anything changes, below EDIT or when
    ``_update_refusal`` gives a reason.
    """
    from nicegui import ui

    from haybale_graph_editor.access import session_allows
    from haybale_graph_editor.panels.properties.introspect.node_ports import _editor_for
    from haywire.core.access import AccessTier
    from haywire.core.macro.promote import macro_document
    from haywire.core.macro.source import (
        count_placements,
        macro_template,
        modified_instance_origin,
        origin_label,
    )

    from haybale_haystack.graph_entry import EntryKind

    # Opening the macro redraws panels; the notices must not depend on this row's slot.
    client = ui.context.client

    if not session_allows(ctx)(AccessTier.EDIT):
        ui.notify("Updating a macro needs edit access", type="warning")
        return

    editor = _editor_for(ctx)
    wrapper = editor.graph.get_node_wrapper(node_id) if editor is not None else None
    origin = modified_instance_origin(wrapper.node) if wrapper is not None else None
    if editor is None or wrapper is None or origin is None:
        ui.notify("This card is not a modified instance", type="warning")
        return

    hs = ctx.app_data.get(HaystackState)
    if hs is None:
        ui.notify("Graph manager not available", type="negative")
        return

    definition = getattr(wrapper.node, "resolve_definition", lambda: None)()
    if definition is None:
        ui.notify("This card is not a modified instance", type="warning")
        return
    label = origin_label(definition)
    refusal = _update_refusal(origin.key, label, hs)
    template = macro_template(origin.key)
    if refusal is not None or template is None:
        ui.notify(refusal or f"{label} is not installed.", type="warning", multi_line=True)
        return

    document = macro_document(definition)
    placement_id, refusal = editor.promote_to_macro(node_id, origin.key, description="Update Macro")
    if placement_id is None:
        ui.notify(refusal or "Could not update the macro", type="warning", multi_line=True)
        return

    entry = hs.open_macro_with(template.path, document)
    ctx.session.publish(Reveal(editor=GraphEditor, binding_id=entry.binding_id, label=entry.display_name))

    graphs = [graph_entry.graph for graph_entry in hs.entries_of_kind(EntryKind.GRAPH)]
    placements, holding = count_placements(graphs, origin.key)
    with client:
        ui.notify(f"Save {label} to update {placements} placements in {holding} open graphs.", type="info")
        if origin.hash != template.content_hash:
            ui.notify(
                f"{label} changed since this instance was made; saving replaces those changes.",
                type="warning",
                multi_line=True,
            )
