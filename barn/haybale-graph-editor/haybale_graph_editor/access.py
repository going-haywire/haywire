# barn/haybale-graph-editor/haybale_graph_editor/access.py
"""The canvas lock rule: a locked canvas caps a session's effective tier at operate."""

from typing import TYPE_CHECKING, Callable

from haywire.core.access import AccessTier

from .state.edit_state import EditState

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def allows(can_access: Callable[[AccessTier], bool], locked: bool, required: AccessTier) -> bool:
    """Return whether ``required`` is allowed, given the session's real tier and the canvas lock.

    ``can_access`` answers for the session's real tier. A locked canvas also
    refuses anything above operate.
    """
    if not can_access(required):
        return False
    return not locked or AccessTier.OPERATE.satisfies(required)


def can_edit_graph(ctx: "SessionContext") -> bool:
    """Return whether ``ctx`` may edit the graph on screen, lock included."""
    return allows(ctx.can_access, ctx.data[EditState].active_locked, AccessTier.EDIT)
