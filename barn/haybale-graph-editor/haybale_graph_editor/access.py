# barn/haybale-graph-editor/haybale_graph_editor/access.py
"""The canvas lock rule, and the level mode it gives a session.

A locked canvas caps a session's level mode at operate. ``level_mode``
turns a session's real tier and the lock into the mode it works a level in,
which the level's ``EditRoute`` checks at every write.
"""

from typing import TYPE_CHECKING, Callable

from haywire.core.access import AccessTier, LevelMode

from .state.graph_app_state import route_for

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def level_mode(can_access: Callable[[AccessTier], bool], locked: bool) -> LevelMode:
    """Return the mode a session works a level in: ``EDIT``, ``OPERATE`` or ``VIEW``.

    ``can_access`` answers for the session's real tier; a lock caps the mode at ``OPERATE``.
    """
    if can_access(AccessTier.EDIT) and not locked:
        return LevelMode.EDIT
    if can_access(AccessTier.OPERATE):
        return LevelMode.OPERATE
    return LevelMode.VIEW


def can_edit_graph(ctx: "SessionContext") -> bool:
    """Return whether ``ctx`` may edit the graph on screen, lock included.

    ``False`` while no level is on screen.
    """
    route = route_for(ctx)
    return route is not None and route.allows(LevelMode.EDIT)
