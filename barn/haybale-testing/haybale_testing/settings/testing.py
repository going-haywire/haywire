# haybale_testing/settings/testing.py
"""Library-level settings for the testing library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting, Color, Vec2i, Vec3f
from haywire.core.settings.decorator import settings


# --8<-- [start:testing_settings]
@settings(namespace="testing", label="Testing")
class TestingSettings(LibrarySettings):
    """Global defaults for the testing library."""

    default_intensity = setting[float](
        0.5,
        min=0.0,
        max=1.0,
        label="Default Intensity",
        description="Library-wide default intensity used by test nodes",
        category="root",
    )
    default_count = setting[int](
        7,
        min=0,
        max=100,
        label="Default Count",
        description="Library-wide integer default used by test nodes",
        category="root",
    )
    default_label = setting[str](
        "default label",
        label="Default Label",
        description="Library-wide string default used by test nodes",
        category="root",
    )
    default_enabled = setting[bool](
        True,
        label="Default Enabled",
        description="Library-wide boolean default used by test nodes",
        category="root",
    )
    default_mode = setting[str](
        "fast",
        choices=["fast", "balanced", "quality"],
        label="Default Mode",
        description="Library-wide mode choice used by test nodes",
        category="root",
    )
    default_color = setting[Color](
        "#ff0000",
        label="Default Color",
        description="Library-wide color default used by test nodes",
        category="root",
        widget="color",
    )
    default_offset = setting[Vec2i](
        Vec2i([0, 0]),
        label="Default Offset",
        description="Library-wide 2D integer offset used by test nodes",
        category="root",
    )
    default_position = setting[Vec3f](
        Vec3f([0.0, 0.0, 0.0]),
        label="Default Position",
        description="Library-wide 3D float position used by test nodes",
        category="root",
    )


# --8<-- [end:testing_settings]
