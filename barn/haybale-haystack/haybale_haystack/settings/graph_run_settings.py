from haywire.core.settings import setting
from haywire.core.settings.settings import Settings


class GraphRunSettings(Settings):
    """Per-entry run policy. Persisted in the haystack TOML ``[graphs.run]`` table."""

    autorestart = setting[bool](
        False,
        label="Auto-restart",
        description=(
            "Restart this graph automatically after it is stopped by a "
            "structural change that requires recompilation."
        ),
    )
