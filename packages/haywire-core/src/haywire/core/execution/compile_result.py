from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompileResult:
    """Outcome of assembling a graph for execution.

    Attributes:
        ok:    True if assembly succeeded and the graph is ready to start.
        error: Assembly error message when ``ok`` is False, else None.
    """

    ok: bool
    error: str | None = None
