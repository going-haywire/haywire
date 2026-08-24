# haywire/ui/prefs/debug.py
"""Debug and development preference singleton."""

from haywire.core.namespaces import CATEGORY_LOG_LEVEL, CATEGORY_LOG_OUTPUT, NAMESPACE_DEBUG
from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL, CHOICES, INT

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "ERROR"]
_GROUP_CHOICES = {"": "inherit", "DEBUG": "DEBUG", "INFO": "INFO", "WARNING": "WARNING", "ERROR": "ERROR"}

GLOBAL_BASELINE_LOG_LEVEL_KEY = "log_level"

#: Field name of :attr:`DebugSettings.log_scrollback_lines`. The studio wires it
#: into the process-wide ``StdoutTee`` at startup, and the Log editor reads it
#: on every draw — both by this name, so the string is written once.
LOG_SCROLLBACK_LINES_KEY = "log_scrollback_lines"

# --8<-- [start:debug-settings-choices-example]


class DebugSettings(FrameworkSettings, namespace=NAMESPACE_DEBUG):
    """Global preferences for debug features."""

    # One value drives all three retention caps in the log path: the stdout
    # backlog replayed into a freshly-opened panel (StdoutTee.max_history), the
    # Log editor's Copy/Clear mirror, and the lines kept in the DOM. They must
    # stay equal or Copy stops matching what is on screen.
    log_scrollback_lines = setting[INT](
        500,
        label="Log Scrollback Lines",
        description="Lines the Log panel retains before dropping the oldest",
        category=CATEGORY_LOG_OUTPUT,
        min=50,
        max=10000,
    )

    # Logging — global baseline -> if key changes, apply it to GLOBAL_BASELINE_LOG_LEVEL_KEY
    log_level = setting[CHOICES](
        "INFO",
        label="Global Log Level",
        description="Minimum log level for the haywire root logger",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _LEVEL_CHOICES},
    )
    # --8<-- [end:debug-settings-choices-example]

    # Per-subsystem overrides ("" = inherit from log_level)
    log_execution = setting[CHOICES](
        "",
        label="Execution",
        description="Log level for haywire.core.execution ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_assembly = setting[CHOICES](
        "",
        label="Assembly",
        description="Log level for haywire.core.assembly ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_graph = setting[CHOICES](
        "",
        label="Graph",
        description="Log level for haywire.core.graph ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_node = setting[CHOICES](
        "",
        label="Node",
        description="Log level for haywire.core.node ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_settings = setting[CHOICES](
        "",
        label="Settings",
        description="Log level for haywire.core.settings ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_library = setting[CHOICES](
        "",
        label="Library",
        description="Log level for haywire.core.library ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_registry = setting[CHOICES](
        "",
        label="Registry",
        description="Log level for haywire.core.registry ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_ui = setting[CHOICES](
        "",
        label="UI",
        description="Log level for haywire.ui ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )
    log_mcp = setting[CHOICES](
        "",
        label="MCP",
        description="Log level for the mcp SDK (Farmhand transport) ('' = inherit)",
        category=CATEGORY_LOG_LEVEL,
        widget_config={"options": _GROUP_CHOICES},
    )

    log_to_file = setting[BOOL](
        False,
        label="Log to File",
        description="Write logs to file in addition to console",
        category=CATEGORY_LOG_LEVEL,
    )

