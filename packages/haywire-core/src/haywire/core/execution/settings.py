# haywire/ui/prefs/execution.py
"""Execution behaviour preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.schema import FrameworkSettings

class ExecutionSettings(FrameworkSettings):
    """Global preferences controlling graph execution behaviour."""

    # Auto-execution
    auto_execute: bool = setting(
        True,
        label="Auto Execute",
        description="Automatically execute graph when inputs change",
        category="execution",
        order=10,
    )

    execute_on_connect: bool = setting(
        True,
        label="Execute on Connect",
        description="Execute affected nodes when new connections are made",
        category="execution",
        order=12,
    )
