# haywire/ui/prefs/execution.py
"""Execution behaviour preference singleton."""

from haywire.core.settings import field
from haywire.core.settings.schema import FrameworkSettings


# TODO: Setup Execution Settings
class ExecutionSettings(FrameworkSettings):
    """Global preferences controlling graph execution behaviour."""

    # Auto-execution
    auto_execute = field[bool](
        True,
        label="Auto Execute",
        description="Automatically execute graph when inputs change",
        category="execution",
        order=10,
    )

    execute_on_connect = field[bool](
        True,
        label="Execute on Connect",
        description="Execute affected nodes when new connections are made",
        category="execution",
        order=12,
    )
