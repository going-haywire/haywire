"""ActivitySettings — history size and audit-log destination for Farmhand activity tracking.

Settled 2026-08-18, see
``docs/superpowers/plans/2026-08-18-farmhand-activity-expansion.md``.

``FrameworkSettings`` (not ``LibrarySettings``): this schema configures
``haywire.core.farmhand.activity``, framework internals rather than a barn
library — the docstring on ``FrameworkSettings`` scopes it to exactly this
case ("For use by haywire-core and haywire-studio internals only").

The ``farmhand.activity`` namespace is the literal nesting path in a project's
``.haywire/settings.json`` (``_setting_key = f"{namespace}.{name}"``), so it is
deliberately unchanged by the move from haywire-studio into haywire-core: a
rename would not error, it would silently orphan every value a user had already
set and revert them to defaults. It also remains correctly *named* — Farmhand's
contribution seam lives in ``haywire.core.farmhand`` too; only the MCP host that
serves the tools is studio-side.
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
