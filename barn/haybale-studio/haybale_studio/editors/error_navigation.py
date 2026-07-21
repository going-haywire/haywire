"""Navigation helpers: error → component definition / involved file / graph instance.

open_component/open_file_in_studio translate a HaywireException's string
locators into direct studio navigation (active_component for the CONTEXT-slot
source viewer; Reveal(CodeEditor) for a file in the MAIN slot). reveal_instance
publishes a session-local RevealGraphInstance signal instead — the actual
resolve-and-select logic lives in GraphEditor (each open tab in this session
self-matches against its own live BaseGraph.graph_id). Session-local, not
cross-session: this is a personal navigation click, so it must only affect
the session that clicked it, never a peer session that happens to have the
same graph open."""

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


def reveal_instance(error: "HaywireException", context: "SessionContext") -> None:
    """Ask every open GraphEditor in THIS session to reveal+select this
    error's instance, if it's theirs.

    Publishes RevealGraphInstance (session-local — see its docstring for
    why) and returns immediately — there is no synchronous way to know
    whether any GraphEditor in this session claimed it (fire-and-forget).
    No-op if the error doesn't carry enough locator fields to reveal
    anything (no user-visible feedback either way; see RevealGraphInstance's
    docstring for the rationale)."""
    if not error.can_reveal_instance():
        return

    from haywire.core.session.signals import RevealGraphInstance

    assert error.graph_id is not None  # can_reveal_instance guarantees it
    context.session.publish(
        RevealGraphInstance(graph_id=error.graph_id, node_id=error.node_id, edge_id=error.edge_id)
    )
