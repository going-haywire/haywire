"""Navigation helpers: error → component definition / involved file.

These translate a HaywireException's string locators into studio navigation
(active_component for the CONTEXT-slot source viewer; Reveal(CodeEditor) for
a file in the MAIN slot). Instance navigation (graph reveal + select) lives in
the same package but is a separate helper (see reveal_instance)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.core.session.context import SessionContext


def open_component(error: "HaywireException", context: "SessionContext") -> bool:
    """Point the CONTEXT-slot component source viewer at this error's component.

    Sets ``active_component = registry_key`` (the ComponentSourceEditor follows
    it). Returns False if the error has no registry_key."""
    if not error.can_open_component():
        return False
    context.active_component = error.registry_key
    return True


def open_file_in_studio(filepath: str, line_number: "int | None", context: "SessionContext") -> None:
    """Open a file in the studio's MAIN-slot CodeEditor.

    Mirrors ComponentSourceEditor._open_in_code_editor: set active_file, then
    Reveal the CodeEditor bound to the path. line_number is accepted for a
    future goto; the CodeEditor binds by path today."""
    from haybale_studio.editors.code_editor import CodeEditor
    from haywire.core.session.signals import Reveal

    path = Path(filepath)
    context.active_file = path
    context.session.publish(Reveal(editor=CodeEditor, binding_id=str(path), label=path.name))


def reveal_instance(error: "HaywireException", context: "SessionContext") -> bool:
    """Reveal the graph the error occurred in and select the offending instance.

    Node errors select ``active_node``; edge/adapter errors select
    ``active_edge``. Everything is re-resolved live from the current graph
    state — nothing is held from error-time — so a hot-reloaded / closed graph
    degrades to a no-op returning False (caller greys the menu item)."""
    if not error.can_reveal_instance():
        return False

    from haywire.core.session.signals import Reveal, SelectionMoved
    from haybale_haystack.state.haystack_state import HaystackState
    from haybale_graph_editor.state.edit_state import EditState
    from haybale_graph_editor.editors.graph_editor import GraphEditor

    assert error.graph_id is not None  # can_reveal_instance guarantees it
    entry = context.app_data[HaystackState].get_by_id(error.graph_id)
    if entry is None:
        return False  # graph closed / hot-reloaded away

    graph = entry.graph
    edit_state = context.data[EditState]

    if error.node_id is not None:
        node_wrapper = graph.get_node_wrapper(error.node_id)
        if node_wrapper is None:
            return False  # node gone
        edit_state.active_node = node_wrapper
    elif error.edge_id is not None:
        edge_wrapper = graph.edge_wrappers.get(error.edge_id)
        if edge_wrapper is None:
            return False  # edge gone
        edit_state.active_edge = edge_wrapper
    else:
        return False  # unreachable given can_reveal_instance()

    context.session.publish(Reveal(editor=GraphEditor, binding_id=error.graph_id, label=entry.display_name))
    context.session.publish(SelectionMoved())
    return True
