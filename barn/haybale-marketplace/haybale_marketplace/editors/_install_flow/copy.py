"""Step vocabulary for the Install / Update Library flow."""

from __future__ import annotations

STEPS = ("selected", "checked", "installing", "done")

STEP_TITLES = {
    "selected": "Library",
    "checked": "Resolve",
    "installing": "Install",
    "done": "Installed",
}
