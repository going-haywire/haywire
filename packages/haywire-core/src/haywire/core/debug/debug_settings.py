# haywire/ui/prefs/debug.py
"""Debug and development preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "ERROR"]
_GROUP_CHOICES = {"": "inherit", "DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}


class DebugSettings(FrameworkSettings, namespace="debug"):
    """Global preferences for debug features."""

    # Logging — global baseline
    log_level: str = setting(
        "INFO",
        label="Log Level",
        description="Minimum log level for the haywire root logger",
        category="debug",
        order=10,
        choices=_LEVEL_CHOICES,
    )

    # Per-subsystem overrides ("" = inherit from log_level)
    log_execution: str = setting(
        "",
        label="Execution",
        description="Log level for haywire.core.execution ('' = inherit)",
        category="debug",
        order=20,
        choices=_GROUP_CHOICES,
    )
    log_assembly: str = setting(
        "",
        label="Assembly",
        description="Log level for haywire.core.assembly ('' = inherit)",
        category="debug",
        order=30,
        choices=_GROUP_CHOICES,
    )
    log_graph: str = setting(
        "",
        label="Graph",
        description="Log level for haywire.core.graph ('' = inherit)",
        category="debug",
        order=40,
        choices=_GROUP_CHOICES,
    )
    log_node: str = setting(
        "",
        label="Node",
        description="Log level for haywire.core.node ('' = inherit)",
        category="debug",
        order=50,
        choices=_GROUP_CHOICES,
    )
    log_settings: str = setting(
        "",
        label="Settings",
        description="Log level for haywire.core.settings ('' = inherit)",
        category="debug",
        order=60,
        choices=_GROUP_CHOICES,
    )
    log_library: str = setting(
        "",
        label="Library",
        description="Log level for haywire.core.library ('' = inherit)",
        category="debug",
        order=70,
        choices=_GROUP_CHOICES,
    )
    log_registry: str = setting(
        "",
        label="Registry",
        description="Log level for haywire.core.registry ('' = inherit)",
        category="debug",
        order=80,
        choices=_GROUP_CHOICES,
    )
    log_ui: str = setting(
        "",
        label="UI",
        description="Log level for haywire.ui ('' = inherit)",
        category="debug",
        order=90,
        choices=_GROUP_CHOICES,
    )

    log_to_file: bool = setting(
        False,
        label="Log to File",
        description="Write logs to file in addition to console",
        category="debug",
        order=100,
    )
