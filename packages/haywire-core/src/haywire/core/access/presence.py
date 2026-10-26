"""Who is currently connected (ADR 0027).

Two different liveness signals, deliberately not pretended to be the same:

* **Users** hold an open websocket, so ``SessionManager.active_sessions`` is
  authoritative. Multiple browser tabs collapse into one entry with a count.
* **Agents** transact over request-shaped MCP traffic with no persistent
  socket, so the time of their last admitted request is the only signal
  available. Whatever admits that request reports it through
  ``record_agent_seen``. MCP's ``ping`` is an *optional* protocol message, so
  an agent that never pings would look offline — which is why the UI shows
  "last seen 40s ago" rather than a green dot. A relative timestamp cannot be
  wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from haywire.core.access.resolver import resolve_tier
from haywire.core.access.tier import AccessTier
from haywire.core.farmhand.activity import activity_tracker
from haywire.core.signals import AgentDisconnected

#: An agent quieter than this drops out of the presence row.
AGENT_IDLE_TIMEOUT_SECONDS = 300.0

#: Agent name → monotonic timestamp of its most recent admitted request.
_AGENTS_SEEN: dict[str, float] = {}

#: Agents currently inside the idle window, so a departure publishes once
#: rather than on every presence read. Module-level to survive hot-reload.
_present_agents: set[str] = set()


def record_agent_seen(name: str) -> None:
    """Stamp agent ``name`` as seen now. Call once per admitted agent request."""
    _AGENTS_SEEN[name] = time.monotonic()


def agents_seen() -> dict[str, float]:
    """Agent name → monotonic timestamp of its most recent admitted request.

    The live dict: tests may clear or seed it directly.
    """
    return _AGENTS_SEEN


def _note_departure(name: str) -> None:
    """Publish :class:`AgentDisconnected` the first time ``name`` ages out.

    Aging out is the only available departure signal — MCP has no close event.
    Best-effort: presence is a read path, so a broadcast failure must not stop
    it returning rows.
    """
    if name not in _present_agents:
        return
    _present_agents.discard(name)
    try:
        from haywire.core.di.context import get_signal_dispatcher

        get_signal_dispatcher().broadcast(AgentDisconnected(principal=name))
    except Exception:  # pragma: no cover - defensive; no dispatcher in unit tests
        pass


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


def collect_presence(session_manager) -> list[PresenceEntry]:
    """Every principal currently present, users first.

    Tiers come from ``resolve_tier``. An agent drops out once it has been idle
    longer than ``AGENT_IDLE_TIMEOUT_SECONDS``, publishing ``AgentDisconnected``
    once.
    """
    counts: dict[str, int] = {}
    for session in session_manager.active_sessions.values():
        name = getattr(session.context, "principal", None)
        if name:
            counts[name] = counts.get(name, 0) + 1

    users = [
        PresenceEntry(name=name, kind="user", tier=resolve_tier(name), sessions=count)
        for name, count in sorted(counts.items())
    ]

    now = time.monotonic()
    agents = []
    for name, stamp in sorted(_AGENTS_SEEN.items()):
        idle = now - stamp
        if idle > AGENT_IDLE_TIMEOUT_SECONDS:
            _note_departure(name)
            continue
        _present_agents.add(name)
        tracker = activity_tracker()
        running = tracker.current(name)
        finished = tracker.last(name)
        agents.append(
            PresenceEntry(
                name=name,
                kind="agent",
                tier=resolve_tier(name),
                last_seen_seconds=idle,
                running_tool=running.tool if running is not None else "",
                last_tool=finished.tool if finished is not None else "",
                last_ok=finished.ok if finished is not None else True,
            )
        )

    return users + agents
