"""Step vocabulary for the Refresh Libraries flow."""

from __future__ import annotations

#: Fixed for the whole run. `conflicts` is listed even though most refreshes
#: never stop there: the progress bar is drawn from this list on every render,
#: so a list that grew when the resolve found a conflict would add a segment
#: halfway through and move the goalposts under the user. A refresh with
#: nothing to settle steps straight over it instead.
STEPS = ("sources", "fetched", "conflicts", "resolved", "applied")

STEP_TITLES = {
    "sources": "Sources",
    "fetched": "Fetch",
    "conflicts": "Name conflicts",
    "resolved": "Review changes",
    "applied": "Refreshed",
}
