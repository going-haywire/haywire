# haybale_studio/settings/debug.py
"""Debug and development settings."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace="debug", label="Debug")
class DebugSettings(LibrarySettings):
    """Global settings for debug and development features."""

    # Logging
    verbose_logging: bool = setting(
        False,
        label="Verbose Logging",
        description="Enable detailed logging output",
        category="debug",
        order=10,
    )
    log_level: str = setting(
        "INFO",
        label="Log Level",
        description="Minimum log level to display",
        category="debug",
        order=11,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    log_to_file: bool = setting(
        False,
        label="Log to File",
        description="Write logs to file in addition to console",
        category="debug",
        order=12,
    )

    # Execution visibility
    show_execution_time: bool = setting(
        False,
        label="Show Execution Time",
        description="Display execution time for each node",
        category="debug",
        order=20,
    )
    show_node_ids: bool = setting(
        False, label="Show Node IDs", description="Display internal node IDs", category="debug", order=21
    )
    show_port_ids: bool = setting(
        False, label="Show Port IDs", description="Display internal port IDs", category="debug", order=22
    )

    # Visual debugging
    highlight_dirty_nodes: bool = setting(
        False,
        label="Highlight Dirty Nodes",
        description="Visually indicate nodes that need re-execution",
        category="debug",
        order=30,
    )
    highlight_execution_order: bool = setting(
        False,
        label="Highlight Execution Order",
        description="Show execution order numbers on nodes",
        category="debug",
        order=31,
    )
    show_data_flow: bool = setting(
        False,
        label="Show Data Flow",
        description="Visualise data flowing through connections",
        category="debug",
        order=32,
    )

    # Data inspection
    log_data_flow: bool = setting(
        False,
        label="Log Data Flow",
        description="Log data as it flows through nodes",
        category="debug",
        order=40,
    )
    inspect_on_click: bool = setting(
        False,
        label="Inspect on Click",
        description="Show data inspector when clicking ports",
        category="debug",
        order=41,
    )
    max_inspect_depth: int = setting(
        3,
        label="Max Inspect Depth",
        description="Maximum depth for data inspection",
        category="debug",
        order=42,
        min=1,
        max=10,
    )

    # Performance
    show_fps: bool = setting(
        False, label="Show FPS", description="Display frames per second counter", category="debug", order=50
    )
    show_memory_usage: bool = setting(
        False,
        label="Show Memory Usage",
        description="Display memory usage statistics",
        category="debug",
        order=51,
    )
    profile_execution: bool = setting(
        False,
        label="Profile Execution",
        description="Enable execution profiling",
        category="debug",
        order=52,
    )
