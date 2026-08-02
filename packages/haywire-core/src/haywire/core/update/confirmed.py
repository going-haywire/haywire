"""The update-confirmed flag — one source for the banner and the exit code.

They are not the same mechanism: the banner is for the human at the terminal,
the exit code is for a future supervisor. But they must never disagree, so a
single flag produces both. An exit WITHOUT an update — cancel, crash, ordinary
quit — therefore cannot print "Haywire updated", and making the banner
conditional under a supervisor later becomes one check rather than reconciling
two states.

The banner is registered via ``atexit``, not ``app.on_shutdown``: atexit
handlers run during interpreter shutdown, AFTER uvicorn's own shutdown
logging, so the banner is genuinely the last thing on screen. That ordering
does not cost the exit code — ``SystemExit`` has already propagated by then
and the code still arrives intact.
"""

from __future__ import annotations

import atexit

# Sentinel a supervisor reads to tell "restart me" from "user quit"; today
# every exit looks identical from outside. Mirrors Home Assistant's
# RESTART_EXIT_CODE = 100. Nothing in this plan reads it — it is the seam that
# makes a supervisor additive rather than an entry-point refactor.
UPDATE_EXIT_CODE = 100

_confirmed: tuple[str, str] | None = None
_register = atexit.register


def banner_text(from_version: str, to_version: str) -> str:
    """The terminal banner printed after uvicorn's own shutdown lines."""
    rule = "─" * 45
    return (
        f"\n{rule}\n"
        f" Haywire updated:  {from_version} → {to_version}  (pinned)\n"
        f" Restart to load it:   uv run haywire\n"
        f"{rule}\n"
    )


def confirm_update(from_version: str, to_version: str) -> None:
    """Record that the user confirmed an update. Idempotent.

    Registering twice would print the banner twice — atexit handlers are
    additive and never deduplicated.
    """
    global _confirmed
    if _confirmed is not None:
        return
    _confirmed = (from_version, to_version)
    _register(lambda: print(banner_text(from_version, to_version)))


def update_confirmed() -> tuple[str, str] | None:
    """``(from, to)`` when an update was confirmed, else None."""
    return _confirmed


def exit_code() -> int:
    """The process exit code implied by the flag."""
    return UPDATE_EXIT_CODE if _confirmed is not None else 0


def reset_for_tests() -> None:
    """Clear the flag. Tests only — the flag is one-way in a real run."""
    global _confirmed, _register
    _confirmed = None
    _register = atexit.register
