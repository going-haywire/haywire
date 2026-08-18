"""Who is currently connected (ADR 0027).

Two different liveness signals, deliberately not pretended to be the same:

* **Users** hold an open websocket, so ``SessionManager.active_sessions`` is
  authoritative. Multiple browser tabs collapse into one entry with a count.
* **Agents** transact over request-shaped MCP traffic with no persistent
  socket, so the gate's ``last_seen`` stamp is the only signal available.
  MCP's ``ping`` is an *optional* protocol message, so an agent that never
  pings would look offline — which is why the UI shows "last seen 40s ago"
  rather than a green dot. A relative timestamp cannot be wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from haywire.core.access import AccessTier

from haywire_studio.auth.gate import last_seen
from haywire_studio.auth.live import RosterCache
from haywire_studio.farmhand.activity import activity_tracker

#: An agent quieter than this drops out of the presence row.
AGENT_IDLE_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class PresenceEntry:
    """One connected principal, ready to render."""

    name: str
    kind: str
    tier: AccessTier
    sessions: int = 0
    last_seen_seconds: float = 0.0

    #: Tool this agent is running right now, or "" when idle. Always "" for a
    #: user — a browser principal's actions are already visible on screen.
    running_tool: str = ""
    #: Tool this agent finished most recently, or "". Kept separate from
    #: ``running_tool`` so a fast call still leaves something readable behind.
    last_tool: str = ""
    #: Whether that most recent finished call succeeded.
    last_ok: bool = True


def collect_presence(session_manager, cache: RosterCache) -> list[PresenceEntry]:
    """Every principal currently present, users first."""
    roster = cache.roster()

    counts: dict[str, int] = {}
    for session in session_manager.active_sessions.values():
        name = getattr(session.context, "principal", None)
        if name:
            counts[name] = counts.get(name, 0) + 1

    users = [
        PresenceEntry(
            name=name,
            kind="user",
            tier=principal.tier if (principal := roster.find(name)) else AccessTier.VIEW,
            sessions=count,
        )
        for name, count in sorted(counts.items())
    ]

    now = time.monotonic()
    agents = []
    for name, stamp in sorted(last_seen().items()):
        principal = roster.find(name)
        if principal is None or not principal.is_agent:
            continue
        idle = now - stamp
        if idle > AGENT_IDLE_TIMEOUT_SECONDS:
            continue
        tracker = activity_tracker()
        running = tracker.current(name)
        finished = tracker.last(name)
        agents.append(
            PresenceEntry(
                name=name,
                kind="agent",
                tier=principal.tier,
                last_seen_seconds=idle,
                running_tool=running.tool if running is not None else "",
                last_tool=finished.tool if finished is not None else "",
                last_ok=finished.ok if finished is not None else True,
            )
        )

    return users + agents
