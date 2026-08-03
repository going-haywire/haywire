"""Step vocabulary for the Add Source flow."""

from __future__ import annotations

STEPS = ("input", "probed", "resolved", "added", "refreshed")

STEP_TITLES = {
    "input": "Source",
    "probed": "What it offers",
    "resolved": "Conflicts",
    "added": "Subscribed",
    "refreshed": "Done",
}
