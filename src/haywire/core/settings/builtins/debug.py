# haywire/core/settings/builtins/debug.py
"""
Debug and development settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'debug'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register debug settings."""
    
    # Logging
    registry.define(
        'debug.verbose_logging', False,
        label='Verbose Logging',
        description='Enable detailed logging output',
        category=CATEGORY,
        ui_order=10
    )
    registry.define(
        'debug.log_level', 'INFO',
        label='Log Level',
        description='Minimum log level to display',
        category=CATEGORY,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        ui_order=11
    )
    registry.define(
        'debug.log_to_file', False,
        label='Log to File',
        description='Write logs to file in addition to console',
        category=CATEGORY,
        ui_order=12
    )
    
    # Execution visibility
    registry.define(
        'debug.show_execution_time', False,
        label='Show Execution Time',
        description='Display execution time for each node',
        category=CATEGORY,
        ui_order=20
    )
    registry.define(
        'debug.show_node_ids', False,
        label='Show Node IDs',
        description='Display internal node IDs',
        category=CATEGORY,
        ui_order=21
    )
    registry.define(
        'debug.show_port_ids', False,
        label='Show Port IDs',
        description='Display internal port IDs',
        category=CATEGORY,
        ui_order=22
    )
    
    # Visual debugging
    registry.define(
        'debug.highlight_dirty_nodes', False,
        label='Highlight Dirty Nodes',
        description='Visually indicate nodes that need re-execution',
        category=CATEGORY,
        ui_order=30
    )
    registry.define(
        'debug.highlight_execution_order', False,
        label='Highlight Execution Order',
        description='Show execution order numbers on nodes',
        category=CATEGORY,
        ui_order=31
    )
    registry.define(
        'debug.show_data_flow', False,
        label='Show Data Flow',
        description='Visualize data flowing through connections',
        category=CATEGORY,
        ui_order=32
    )
    
    # Data inspection
    registry.define(
        'debug.log_data_flow', False,
        label='Log Data Flow',
        description='Log data as it flows through nodes',
        category=CATEGORY,
        ui_order=40
    )
    registry.define(
        'debug.inspect_on_click', False,
        label='Inspect on Click',
        description='Show data inspector when clicking ports',
        category=CATEGORY,
        ui_order=41
    )
    registry.define(
        'debug.max_inspect_depth', 3,
        label='Max Inspect Depth',
        description='Maximum depth for data inspection',
        category=CATEGORY,
        min_value=1,
        max_value=10,
        ui_order=42
    )
    
    # Performance
    registry.define(
        'debug.show_fps', False,
        label='Show FPS',
        description='Display frames per second counter',
        category=CATEGORY,
        ui_order=50
    )
    registry.define(
        'debug.show_memory_usage', False,
        label='Show Memory Usage',
        description='Display memory usage statistics',
        category=CATEGORY,
        ui_order=51
    )
    registry.define(
        'debug.profile_execution', False,
        label='Profile Execution',
        description='Enable execution profiling',
        category=CATEGORY,
        ui_order=52
    )