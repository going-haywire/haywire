# barn/haybale-graph-editor/haybale_graph_editor/access.py
"""The canvas lock rule, and the level mode it gives a session.

A locked canvas caps a session's level mode at operate. ``level_mode``
turns a session's real tier and the lock into the mode it works a level in,
which the level's ``EditRoute`` checks at every write.
"""

from typing import Callable

from haywire.core.access import AccessTier, LevelMode


def level_mode(can_access: Callable[[AccessTier], bool], locked: bool) -> LevelMode:
    """Return the mode a session works a level in: ``EDIT``, ``OPERATE`` or ``VIEW``.

    ``can_access`` answers for the session's real tier; a lock caps the mode at ``OPERATE``.
    """
    if can_access(AccessTier.EDIT) and not locked:
        return LevelMode.EDIT
    if can_access(AccessTier.OPERATE):
        return LevelMode.OPERATE
    return LevelMode.VIEW
