# haybale_testing/settings/testing.py
"""Library-level settings for the testing library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting, Color
from haywire.core.settings.decorator import settings


@settings(namespace="testing", label="Testing")
class TestingSettings(LibrarySettings):
    """Global defaults for the testing library."""

    default_intensity: float = setting(
        0.5,
        min=0.0,
        max=1.0,
        label="Default Intensity",
        description="Library-wide default intensity used by test nodes",
        category="general",
    )
    default_enabled: bool = setting(
        True,
        label="Default Enabled",
        description="Library-wide boolean default used by test nodes",
        category="general",
    )
    default_mode: str = setting(
        "fast",
        choices=["fast", "balanced", "quality"],
        label="Default Mode",
        description="Library-wide mode choice used by test nodes",
        category="general",
    )
    default_color: Color = setting(
        "#ff0000",
        label="Default Color",
        description="Library-wide color default used by test nodes",
        category="general",
        widget="color",
    )
