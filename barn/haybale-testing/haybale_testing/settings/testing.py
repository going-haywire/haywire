# haybale_testing/settings/testing.py
"""Library-level settings for the testing library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import field, Color, Vec2i, Vec3f
from haywire.core.settings.decorator import settings


@settings(namespace="testing", label="Testing")
class TestingSettings(LibrarySettings):
    """Global defaults for the testing library."""

    default_intensity: float = field(
        0.5,
        min=0.0,
        max=1.0,
        label="Default Intensity",
        description="Library-wide default intensity used by test nodes",
        category="general",
    )
    default_count: int = field(
        7,
        min=0,
        max=100,
        label="Default Count",
        description="Library-wide integer default used by test nodes",
        category="general",
    )
    default_label: str = field(
        "default label",
        label="Default Label",
        description="Library-wide string default used by test nodes",
        category="general",
    )
    default_enabled: bool = field(
        True,
        label="Default Enabled",
        description="Library-wide boolean default used by test nodes",
        category="general",
    )
    default_mode: str = field(
        "fast",
        choices=["fast", "balanced", "quality"],
        label="Default Mode",
        description="Library-wide mode choice used by test nodes",
        category="general",
    )
    default_color: Color = field(
        "#ff0000",
        label="Default Color",
        description="Library-wide color default used by test nodes",
        category="general",
        widget="color",
    )
    default_offset: Vec2i = field(
        [0, 0],
        label="Default Offset",
        description="Library-wide 2D integer offset used by test nodes",
        category="general",
    )
    default_position: Vec3f = field(
        [0.0, 0.0, 0.0],
        label="Default Position",
        description="Library-wide 3D float position used by test nodes",
        category="general",
    )
