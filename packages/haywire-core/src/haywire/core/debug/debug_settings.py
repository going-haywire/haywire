# haywire/ui/prefs/debug.py
"""Debug and development preference singleton."""

from haywire.core.namespaces import CATEGORY_LOG_LEVEL, NAMESPACE_DEBUG
from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "ERROR"]
_GROUP_CHOICES = {"": "inherit", "DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}

GLOBAL_BASELINE_LOG_LEVEL_KEY = "log_level"


class DebugSettings(FrameworkSettings, namespace=NAMESPACE_DEBUG):
    """Global preferences for debug features."""

    # Logging — global baseline -> if key changes, apply it to GLOBAL_BASELINE_LOG_LEVEL_KEY
    log_level = setting[str](
        "INFO",
        label="Global Log Level",
        description="Minimum log level for the haywire root logger",
        category=CATEGORY_LOG_LEVEL,
        order=10,
        choices=_LEVEL_CHOICES,
    )

    # Per-subsystem overrides ("" = inherit from log_level)
    log_execution = setting[str](
        "",
        label="Execution",
        description="Log level for haywire.core.execution ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=20,
        choices=_GROUP_CHOICES,
    )
    log_assembly = setting[str](
        "",
        label="Assembly",
        description="Log level for haywire.core.assembly ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=30,
        choices=_GROUP_CHOICES,
    )
    log_graph = setting[str](
        "",
        label="Graph",
        description="Log level for haywire.core.graph ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=40,
        choices=_GROUP_CHOICES,
    )
    log_node = setting[str](
        "",
        label="Node",
        description="Log level for haywire.core.node ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=50,
        choices=_GROUP_CHOICES,
    )
    log_settings = setting[str](
        "",
        label="Settings",
        description="Log level for haywire.core.settings ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=60,
        choices=_GROUP_CHOICES,
    )
    log_library = setting[str](
        "",
        label="Library",
        description="Log level for haywire.core.library ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=70,
        choices=_GROUP_CHOICES,
    )
    log_registry = setting[str](
        "",
        label="Registry",
        description="Log level for haywire.core.registry ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=80,
        choices=_GROUP_CHOICES,
    )
    log_ui = setting[str](
        "",
        label="UI",
        description="Log level for haywire.ui ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        order=90,
        choices=_GROUP_CHOICES,
    )

    log_to_file = setting[bool](
        False,
        label="Log to File",
        description="Write logs to file in addition to console",
        category=CATEGORY_LOG_LEVEL,
        order=100,
    )
