"""History size and audit-log destination for the Farmhand activity tracker.

The ``farmhand.activity`` namespace is the literal nesting path in a project's
``.haywire/settings.json``, so renaming it orphans every value a user has
already set, silently reverting them to defaults.
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
