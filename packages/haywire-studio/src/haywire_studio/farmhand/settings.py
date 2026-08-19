"""ActivitySettings — history size and audit-log destination for Farmhand activity tracking.

Settled 2026-08-18, see
``docs/superpowers/plans/2026-08-18-farmhand-activity-expansion.md``.

``FrameworkSettings`` (not ``LibrarySettings``): this schema configures
``haywire_studio.farmhand.activity``, which lives in haywire-studio proper,
not a barn library — the docstring on ``FrameworkSettings`` scopes it to
exactly this case ("For use by haywire-core and haywire-studio internals
only").
"""

from __future__ import annotations

from haywire.barn.builtin.types import INT, STRING
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class ActivitySettings(FrameworkSettings, namespace="farmhand.activity"):
    """Per-project preferences for the Farmhand activity tracker."""

    history_size = setting[INT](
        50,
        label="Activity History Size",
        description="How many finished Farmhand tool calls the in-memory tracker remembers.",
        category="farmhand",
        min=1,
    )

    log_path = setting[STRING](
        "",
        label="Activity Log Path",
        description=(
            "Relative path (from the project root) for an append-only audit log of every "
            "Farmhand tool call. Empty disables logging — logging is off by default."
        ),
        category="farmhand",
    )
