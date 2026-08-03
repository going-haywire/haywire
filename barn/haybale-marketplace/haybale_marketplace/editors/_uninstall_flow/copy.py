"""Step vocabulary for the Uninstall Library flow."""

from __future__ import annotations

STEPS = ("selected", "impact", "confirm", "removed")

STEP_TITLES = {
    "selected": "Library",
    "impact": "What this affects",
    "confirm": "Confirm removal",
    "removed": "Uninstalled",
}
