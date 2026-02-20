# haywire/core/settings/builtins/execution.py
"""
Execution behavior settings.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..registry import GlobalSettingsRegistry


CATEGORY = 'execution'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register execution settings."""
    
    # Auto-execution
    registry.define(
        'execution.auto_execute', True,
        label='Auto Execute',
        description='Automatically execute graph when inputs change',
        category=CATEGORY,
        ui_order=10
    )
    registry.define(
        'execution.debounce_ms', 100,
        label='Debounce (ms)',
        description='Delay before auto-execution after changes',
        category=CATEGORY,
        min_value=0,
        max_value=2000,
        ui_order=11
    )
    registry.define(
        'execution.execute_on_connect', True,
        label='Execute on Connect',
        description='Execute affected nodes when new connections are made',
        category=CATEGORY,
        ui_order=12
    )
    
    # Timeouts and limits
    registry.define(
        'execution.timeout_seconds', 60,
        label='Timeout (s)',
        description='Maximum execution time per node',
        category=CATEGORY,
        min_value=1,
        max_value=3600,
        ui_order=20
    )
    registry.define(
        'execution.max_iterations', 1000,
        label='Max Iterations',
        description='Maximum loop iterations (prevents infinite loops)',
        category=CATEGORY,
        min_value=10,
        max_value=100000,
        ui_order=21
    )
    
    # Parallelism
    registry.define(
        'execution.max_parallel', 4,
        label='Max Parallel Nodes',
        description='Maximum nodes to execute in parallel',
        category=CATEGORY,
        min_value=1,
        max_value=32,
        ui_order=30
    )
    registry.define(
        'execution.thread_pool_size', 0,
        label='Thread Pool Size',
        description='Worker thread pool size (0 = auto)',
        category=CATEGORY,
        min_value=0,
        max_value=64,
        ui_order=31
    )
    
    # Caching
    registry.define(
        'execution.cache_results', True,
        label='Cache Results',
        description='Cache node outputs for unchanged inputs',
        category=CATEGORY,
        ui_order=40
    )
    registry.define(
        'execution.cache_max_size_mb', 256,
        label='Cache Size (MB)',
        description='Maximum cache size in megabytes',
        category=CATEGORY,
        min_value=16,
        max_value=4096,
        ui_order=41
    )
    registry.define(
        'execution.cache_ttl_seconds', 0,
        label='Cache TTL (s)',
        description='Cache time-to-live in seconds (0 = no expiry)',
        category=CATEGORY,
        min_value=0,
        max_value=86400,
        ui_order=42
    )
    
    # Error handling
    registry.define(
        'execution.stop_on_error', False,
        label='Stop on Error',
        description='Stop entire execution when a node fails',
        category=CATEGORY,
        ui_order=50
    )
    registry.define(
        'execution.retry_count', 0,
        label='Retry Count',
        description='Number of times to retry failed nodes',
        category=CATEGORY,
        min_value=0,
        max_value=5,
        ui_order=51
    )
    registry.define(
        'execution.retry_delay_ms', 1000,
        label='Retry Delay (ms)',
        description='Delay between retries',
        category=CATEGORY,
        min_value=0,
        max_value=30000,
        ui_order=52
    )