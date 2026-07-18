"""HaystackSettings — per-workspace settings for the haystack library."""

from haywire.core.settings.settings_library import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings
from haywire.barn.builtin.types import INT, STRING


@settings(namespace="haystack", label="Haystack")
class HaystackSettings(LibrarySettings):
    """Per-workspace settings for haystack scalars."""

    last_haystack_name = setting[STRING](
        "",
        label="Last Haystack",
        description="Name of the haystack to auto-load on startup",
        category="haystack",
    )

    new_counter = setting[INT](
        1,
        label="New Counter",
        description="Sequence used to name newly created untitled graphs",
        category="haystack",
    )
