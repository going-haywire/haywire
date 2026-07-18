# haywire/ui/prefs/execution.py
"""Execution behaviour preference singleton."""

from haywire.core.settings import setting
from haywire.core.settings.settings_framework import FrameworkSettings
from haywire.barn.builtin.types import BOOL


# TODO: Setup Execution Settings
class ExecutionSettings(FrameworkSettings):
    """Global preferences controlling graph execution behaviour."""

    # Auto-execution
    auto_execute = setting[BOOL](
        True,
        label="Auto Execute",
        description="Automatically execute graph when inputs change",
        category="execution",
    )

    execute_on_connect = setting[BOOL](
        True,
        label="Execute on Connect",
        description="Execute affected nodes when new connections are made",
        category="execution",
    )
