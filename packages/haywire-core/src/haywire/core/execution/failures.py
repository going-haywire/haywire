"""Process-wide counts of failed and blocked nodes (ADR 0066).

The VM tests ``failure_counts.flagged`` once per node: while it is zero no node is
failed or blocked, and every poisoning check is skipped.
"""

from __future__ import annotations

import threading

__all__ = ["FailureCounts", "failure_counts"]


class FailureCounts:
    """How many nodes are failed, and failed or blocked, right now; changed under ``lock``."""

    __slots__ = ("failed", "flagged", "lock")

    def __init__(self) -> None:
        self.failed = 0
        self.flagged = 0
        self.lock = threading.Lock()


failure_counts = FailureCounts()
