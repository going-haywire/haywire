from haywire.core.settings import setting
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import BOOL


class GraphRunSettings(Settings):
    """Per-entry run policy. Persisted in the haystack TOML ``[graphs.run]`` table."""

    autorestart = setting[BOOL](
        False,
        label="Auto-restart",
        description=(
            "Restart this graph automatically after it is stopped by a "
            "structural change that requires recompilation."
        ),
    )
