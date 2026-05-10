"""HaystackSettings — per-workspace settings for the haystack library."""

from haywire.core.settings.schema import LibrarySettings
from haywire.core.settings import setting
from haywire.core.settings.decorator import settings


@settings(namespace="haystack", label="Haystack")
class HaystackSettings(LibrarySettings):
    """Per-workspace settings for haystack scalars."""

    last_haystack_name = setting[str](
        "",
        label="Last Haystack",
        description="Name of the haystack to auto-load on startup",
        category="haystack",
        order=10,
    )

    new_counter = setting[int](
        1,
        label="New Counter",
        description="Sequence used to name newly created untitled graphs",
        category="haystack",
        order=20,
    )

    autosave = setting[str](
        "off",
        choices=["off", "on_exit", "continuous"],
        label="Autosave",
        description=(
            "When to auto-write the haystack TOML. "
            "'off' = save only on explicit user action. "
            "'on_exit' = also dump on app shutdown. "
            "'continuous' = also dump on every open/save/remove/rename/start/stop. "
            "Untitled (never-saved) graphs are not preserved by autosave; save them "
            "explicitly first."
        ),
        category="haystack",
        order=30,
    )
