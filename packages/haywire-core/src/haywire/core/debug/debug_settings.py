# haywire/ui/prefs/debug.py
"""Debug and development preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "ERROR"]
_GROUP_CHOICES = ["", "DEBUG", "INFO", "WARNING", "ERROR"]


class DebugSettings(FrameworkSettings, namespace="debug"):
    """Global preferences for debug features."""

    # Logging — global baseline
    log_level: str = setting(
        "INFO",
        label="Log Level",
        description="Minimum log level for the haywire root logger",
        category="debug",
        order=11,
        choices=_LEVEL_CHOICES,
    )

    # Per-subsystem overrides ("" = inherit from log_level)
    log_execution: str = setting(
        "",
        label="Execution",
        description="Log level for haywire.core.execution ('' = inherit)",
        category="debug",
        order=12,
        choices=_GROUP_CHOICES,
    )
    log_assembly: str = setting(
        "",
        label="Assembly",
        description="Log level for haywire.core.assembly ('' = inherit)",
        category="debug",
        order=13,
        choices=_GROUP_CHOICES,
    )
    log_graph: str = setting(
        "",
        label="Graph",
        description="Log level for haywire.core.graph ('' = inherit)",
        category="debug",
        order=14,
        choices=_GROUP_CHOICES,
    )
    log_settings: str = setting(
        "",
        label="Settings",
        description="Log level for haywire.core.settings ('' = inherit)",
        category="debug",
        order=15,
        choices=_GROUP_CHOICES,
    )
    log_library: str = setting(
        "",
        label="Library",
        description="Log level for haywire.core.library ('' = inherit)",
        category="debug",
        order=16,
        choices=_GROUP_CHOICES,
    )
    log_ui: str = setting(
        "",
        label="UI",
        description="Log level for haywire.ui ('' = inherit)",
        category="debug",
        order=17,
        choices=_GROUP_CHOICES,
    )

    log_to_file: bool = setting(
        False,
        label="Log to File",
        description="Write logs to file in addition to console",
        category="debug",
        order=18,
    )
