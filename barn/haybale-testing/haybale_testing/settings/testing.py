# haybale_testing/settings/testing.py
"""Library-level settings for the testing library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace='testing', label='Testing')
class TestingSettings(LibrarySettings):
    """Global defaults for the testing library."""

    default_intensity: float = setting(
        0.5,
        min=0.0,
        max=1.0,
        label='Default Intensity',
        description='Library-wide default intensity used by test nodes',
        category='general',
    )
