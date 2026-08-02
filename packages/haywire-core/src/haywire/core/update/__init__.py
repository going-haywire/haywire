"""Framework self-update: version check, pin rewrite, restart banner.

Updating the framework is NOT a marketplace concern — the marketplace depends
on the framework it would be updating — so this lives in haywire-core and is
surfaced by the app shell.
"""

from haywire.core.update.check import UpdateStatus, check_for_update
from haywire.core.update.confirmed import (
    UPDATE_EXIT_CODE,
    confirm_update,
    exit_code,
    update_confirmed,
)
from haywire.core.update.conflict import ConflictResult, check_pin_conflict, diff_resolutions
from haywire.core.update.pin import (
    LOCKSTEP_DISTS,
    declared_floor,
    rewrite_pins,
    startup_mismatch,
)

__all__ = [
    "LOCKSTEP_DISTS",
    "UPDATE_EXIT_CODE",
    "ConflictResult",
    "UpdateStatus",
    "check_for_update",
    "check_pin_conflict",
    "confirm_update",
    "declared_floor",
    "diff_resolutions",
    "exit_code",
    "rewrite_pins",
    "startup_mismatch",
    "update_confirmed",
]
