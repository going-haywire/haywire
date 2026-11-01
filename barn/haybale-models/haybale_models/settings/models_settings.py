"""ModelsSettings — library-wide settings for model downloads."""

from haywire.barn.builtin.types import INT
from haywire.core.settings import LibrarySettings, setting, settings


@settings(namespace="models", label="Models", description="Model download behaviour")
class ModelsSettings(LibrarySettings):
    """Settings for the model download queue."""

    max_parallel_downloads = setting[INT](
        2,
        label="Parallel downloads",
        description="How many model files download at the same time",
        min=1,
        max=8,
    )
