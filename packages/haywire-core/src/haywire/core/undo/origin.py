"""Who recorded an undo step, and the read-only rows a history lists itself as.

``StepOrigin`` travels from a session's edit route (or a Farmhand call) through the
``Editor`` into the history, which keeps it beside the step. ``HistoryEntry`` and
``HistoryMove`` are what ``IHistoryManager.snapshot()`` and ``last_move()`` return.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

#: How a step reached the history: a session's canvas and panels, a Farmhand tool call, or the framework.
StepVia = Literal["canvas", "farmhand", "system"]


@dataclass(frozen=True)
class StepOrigin:
    """Who recorded an undo step: a principal, through one session or a Farmhand call.

    Attributes:
        principal: The signed-in principal, or ``None`` when authentication is off.
        session: A short id telling apart two sessions of one principal (two browser
            tabs), or ``None`` when there is no session, as for a Farmhand call.
        via: How the step reached the history.

    Example::

        origin = StepOrigin(principal="alice", session="3f2a", via="canvas")
        origin.label  # "alice · 3f2a"
        StepOrigin(principal=None, session=None, via="farmhand").label  # "Farmhand"
    """

    principal: Optional[str]
    session: Optional[str]
    via: StepVia

    @classmethod
    def of_session(cls, principal: Optional[str], session_id: str) -> "StepOrigin":
        """Return the origin of a browser session's canvas and panel edits.

        Args:
            principal: The session's signed-in principal, or ``None`` when authentication is off.
            session_id: The session's full id; its first four characters become ``session``.
        """
        return cls(principal, session_id[:4] or None, "canvas")

    @property
    def label(self) -> str:
        """Return a short display text: principal and session, or ``via`` when both are unknown."""
        parts = [part for part in (self.principal, self.session) if part]
        if self.via == "farmhand":
            parts.insert(0, "Farmhand")
        return " · ".join(parts) if parts else self.via.capitalize()


@dataclass(frozen=True)
class HistoryEntry:
    """One row of a history snapshot: a step, a group of steps, or a fence.

    Attributes:
        kind: ``"step"``, ``"group"`` or ``"fence"``.
        description: The step's description; for a group, its own or ``"Group of N actions"``.
        origin: Who recorded it, or ``None`` when unknown. A group carries its first known
            child origin; a fence carries none.
        timestamp: ``time.time()`` when it was recorded.
        graph: The graph the step mutates (a ``BaseGraph``, possibly a Subgraph), or ``None``
            when the step does not say.
        undone: The step is past the undo marker, so Redo would apply it again.
        pending: The step is still inside the grouping window and not yet in the history
            proper; the next fence, undo or step after the window flushes it.
        action_type: The action's class name; ``"ActionGroup"`` for a group, ``""`` for a fence.
        merge_key: A value step's merge key while it can still be amended, else ``None``.
        children: A group's steps, oldest first; empty otherwise.
    """

    kind: Literal["step", "group", "fence"]
    description: str
    origin: Optional[StepOrigin]
    timestamp: float
    graph: Any = None
    undone: bool = False
    pending: bool = False
    action_type: str = ""
    merge_key: Any = None
    children: tuple["HistoryEntry", ...] = ()


@dataclass(frozen=True)
class HistoryMove:
    """The latest undo or redo on a history: which, by whom, and when (``time.time()``)."""

    direction: Literal["undo", "redo"]
    origin: Optional[StepOrigin]
    timestamp: float
