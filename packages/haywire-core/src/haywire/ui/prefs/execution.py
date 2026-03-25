# haywire/ui/prefs/execution.py
"""Execution behaviour preference singleton."""

from haywire.core.settings import Settings, setting


class ExecutionSettings(Settings):
    """Global preferences controlling graph execution behaviour."""

    # Auto-execution
    auto_execute: bool = setting(
        True,
        label="Auto Execute",
        description="Automatically execute graph when inputs change",
        category="execution",
        order=10,
    )
    debounce_ms: int = setting(
        100,
        label="Debounce (ms)",
        description="Delay before auto-execution after changes",
        category="execution",
        order=11,
        min=0,
        max=2000,
    )
    execute_on_connect: bool = setting(
        True,
        label="Execute on Connect",
        description="Execute affected nodes when new connections are made",
        category="execution",
        order=12,
    )

    # Timeouts and limits
    timeout_seconds: int = setting(
        60,
        label="Timeout (s)",
        description="Maximum execution time per node",
        category="execution",
        order=20,
        min=1,
        max=3600,
    )
    max_iterations: int = setting(
        1000,
        label="Max Iterations",
        description="Maximum loop iterations (prevents infinite loops)",
        category="execution",
        order=21,
        min=10,
        max=100000,
    )

    # Parallelism
    max_parallel: int = setting(
        4,
        label="Max Parallel Nodes",
        description="Maximum nodes to execute in parallel",
        category="execution",
        order=30,
        min=1,
        max=32,
    )
    thread_pool_size: int = setting(
        0,
        label="Thread Pool Size",
        description="Worker thread pool size (0 = auto)",
        category="execution",
        order=31,
        min=0,
        max=64,
    )

    # Caching
    cache_results: bool = setting(
        True,
        label="Cache Results",
        description="Cache node outputs for unchanged inputs",
        category="execution",
        order=40,
    )
    cache_max_size_mb: int = setting(
        256,
        label="Cache Size (MB)",
        description="Maximum cache size in megabytes",
        category="execution",
        order=41,
        min=16,
        max=4096,
    )
    cache_ttl_seconds: int = setting(
        0,
        label="Cache TTL (s)",
        description="Cache time-to-live in seconds (0 = no expiry)",
        category="execution",
        order=42,
        min=0,
        max=86400,
    )

    # Error handling
    stop_on_error: bool = setting(
        False,
        label="Stop on Error",
        description="Stop entire execution when a node fails",
        category="execution",
        order=50,
    )
    retry_count: int = setting(
        0,
        label="Retry Count",
        description="Number of times to retry failed nodes",
        category="execution",
        order=51,
        min=0,
        max=5,
    )
    retry_delay_ms: int = setting(
        1000,
        label="Retry Delay (ms)",
        description="Delay between retries",
        category="execution",
        order=52,
        min=0,
        max=30000,
    )
