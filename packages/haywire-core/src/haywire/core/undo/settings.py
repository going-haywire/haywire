# haywire/core/undo/settings.py
"""User-facing slice of the undo system's configuration."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings


class UndoSettings(FrameworkSettings, namespace="undo"):
    """What a user may tune about undo history.

    Deliberately thin. :class:`~haywire.core.undo.config.UndoConfig` carries
    ~20 fields, but nearly all of them (merge windows, compression thresholds,
    performance metrics) are internal tuning that would be noise in a settings
    panel. This class exposes only the one a user has a real opinion about;
    ``UndoConfig`` stays the internal knob-set and reads this at construction.

    Applies when a graph editor is *created*: ``HistoryManager`` reads
    ``max_actions`` from the config it was built with and has no resize path,
    so editors already open keep the limit they started with.
    """

    max_actions = setting[INT](
        100,
        label="Undo Limit",
        description=(
            "Maximum number of undo steps kept per graph editor. "
            "Applies to editors opened after the change; already-open graphs keep their limit."
        ),
        category="undo",
        min=10,
        max=1000,
    )
