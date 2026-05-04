# haybale_testing/settings/testing.py
"""Library-level settings for the testing library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import field, Color, Vec2i, Vec3f
from haywire.core.settings.decorator import settings


@settings(namespace="testing", label="Testing")
class TestingSettings(LibrarySettings):
    """Global defaults for the testing library."""

    default_intensity = field[float](
        0.5,
        min=0.0,
        max=1.0,
        label="Default Intensity",
        description="Library-wide default intensity used by test nodes",
        category="root",
    )
    default_count = field[int](
        7,
        min=0,
        max=100,
        label="Default Count",
        description="Library-wide integer default used by test nodes",
        category="root",
    )
    default_label = field[str](
        "default label",
        label="Default Label",
        description="Library-wide string default used by test nodes",
        category="root",
    )
    default_enabled = field[bool](
        True,
        label="Default Enabled",
        description="Library-wide boolean default used by test nodes",
        category="root",
    )
    default_mode = field[str](
        "fast",
        choices=["fast", "balanced", "quality"],
        label="Default Mode",
        description="Library-wide mode choice used by test nodes",
        category="root",
    )
    default_color = field[Color](
        "#ff0000",
        label="Default Color",
        description="Library-wide color default used by test nodes",
        category="root",
        widget="color",
    )
    default_offset = field[Vec2i](
        [0, 0],
        label="Default Offset",
        description="Library-wide 2D integer offset used by test nodes",
        category="root",
    )
    default_position = field[Vec3f](
        [0.0, 0.0, 0.0],
        label="Default Position",
        description="Library-wide 3D float position used by test nodes",
        category="root",
    )
