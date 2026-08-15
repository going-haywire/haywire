"""Push-based revocation (ADR 0027).

A websocket is one ASGI scope, checked once at the handshake, so the gate
cannot revoke a socket it has already admitted. Removing a principal therefore
walks the live sessions and tears down theirs.

Demotion deliberately has no counterpart here: ``ctx.can_edit()`` reads live
authority, so a demoted principal's next action is already refused and the
affordances stop rendering on the next redraw. Evicting them would throw
someone out mid-work for a change that did not need it.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def evict_principal(session_manager, name: str) -> int:
    """Tear down every live session belonging to ``name``. Returns how many were evicted.

    Per-session failures are logged and skipped — one wedged session must not
    leave the rest of a removed principal's sessions alive.
    """
    victims = [
        session_id
        for session_id, session in list(session_manager.active_sessions.items())
        if getattr(session.context, "principal", None) == name
    ]

    evicted = 0
    for session_id in victims:
        try:
            session_manager.remove_session(session_id)
            evicted += 1
        except Exception:
            logger.warning(
                "Failed to evict session %s for principal %r", session_id[:8], name, exc_info=True
            )

    if evicted:
        logger.info("Evicted %d session(s) for removed principal %r", evicted, name)
    return evicted


def evict_all(session_manager) -> int:
    """Tear down every live session — the "log everyone out" half of a secret rotation."""
    evicted = 0
    for session_id in list(session_manager.active_sessions.keys()):
        try:
            session_manager.remove_session(session_id)
            evicted += 1
        except Exception:
            logger.warning("Failed to evict session %s", session_id[:8], exc_info=True)
    return evicted
