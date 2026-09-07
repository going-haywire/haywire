"""Navigation helpers: component / file / graph instance → the studio surface showing it.

Every helper here publishes an editor-agnostic signal and stops. It names no
editor class and writes no session state: the editor that answers claims the
signal with ``@reveal_on`` and sets its own context in the hook, which runs
before the reveal. That is deliberate — these helpers predate ``@reveal_on``
and used to set ``active_component``/``active_file`` themselves and then
``Reveal`` a named editor, which meant the claim rule existed twice (here and
in the editor) and could disagree. Notably it did: this module opened any path
in the CodeEditor, while ``CodeEditor._on_reveal_source`` vetoes extensions it
cannot edit.

- open_component / open_component_source → ``RevealComponentSource``, answered
  by ComponentSourceEditor (CONTEXT slot).
- open_component_docs → ``RevealComponentDocs``, answered by ComponentDocsEditor.
- open_file_in_studio → ``RevealSource``, answered by CodeEditor (MAIN slot),
  which vetoes a file it cannot edit.
- reveal_instance → ``RevealGraphInstance``; the resolve-and-select logic lives
  in GraphEditor (each open tab in this session self-matches against its own
  live BaseGraph.graph_id).

A reveal — rather than only a context write — is what makes a collapsed slot
pop open (``IconSlot._expands_on_reveal``) instead of silently updating content
the user is not looking at.

All of these are session-local: a personal navigation click must only affect
the session that clicked it, never a peer session that happens to have the same
graph or component open. All are fire-and-forget — nothing reports back whether
an editor claimed the signal, and with no editor installed to answer, nothing
happening is a working configuration rather than an error."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.core.session.context import SessionContext


def open_component(error: "HaywireException", context: "SessionContext") -> bool:
    """Point the CONTEXT-slot component source viewer at this error's component
    and force it into view.

    The HaywireException-keyed form of :func:`open_component_source`; see it for
    the routing. Returns False if the error has no registry_key."""
    if not error.can_open_component():
        return False

    assert error.registry_key is not None  # can_open_component guarantees it
    open_component_source(error.registry_key, context)
    return True


def open_component_docs(registry_key: str, context: "SessionContext") -> None:
    """Bring the CONTEXT-slot docs editor to ``registry_key`` and into view.

    The docs counterpart to :func:`open_component_source`. Both take a registry
    key rather than a HaywireException because they serve plain navigation (a
    component row in the library overview), not error triage.
    """
    from haywire.core.signals import RevealComponentDocs

    context.session.publish(RevealComponentDocs(registry_key=registry_key))


def open_component_source(registry_key: str, context: "SessionContext") -> None:
    """Bring the CONTEXT-slot source viewer to ``registry_key`` and into view.

    The key-taking form of :func:`open_component`, which does the same for a
    HaywireException's ``registry_key``.
    """
    from haywire.core.signals import RevealComponentSource

    context.session.publish(RevealComponentSource(registry_key=registry_key))


def open_file_in_studio(filepath: str, line_number: "int | None", context: "SessionContext") -> None:
    """Open a file in the studio's MAIN-slot CodeEditor.

    Publishes ``RevealSource``, so CodeEditor's hook decides whether the path is
    one it can edit — a file it vetoes opens nothing rather than landing in
    CodeMirror. ``line_number`` is accepted for a future goto; the CodeEditor
    binds by path today."""
    from haywire.core.signals import RevealSource

    path = Path(filepath)
    context.session.publish(RevealSource(binding_id=str(path), label=path.name))


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

    from haywire.core.signals import RevealGraphInstance

    assert error.graph_id is not None  # can_reveal_instance guarantees it
    context.session.publish(
        RevealGraphInstance(graph_id=error.graph_id, node_id=error.node_id, edge_id=error.edge_id)
    )
