"""Step vocabulary for the Refresh Libraries flow."""

from __future__ import annotations

STEPS = ("sources", "fetched", "resolved", "applied")

STEP_TITLES = {
    "sources": "Sources",
    "fetched": "Fetch",
    "resolved": "Review changes",
    "applied": "Refreshed",
}
