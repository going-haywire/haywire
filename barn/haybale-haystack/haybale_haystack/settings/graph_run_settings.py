from haywire.core.settings import setting
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import BOOL, CHOICES


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

    on_exception_bail = setting[CHOICES](
        "branch",
        label="On exception, bail",
        description=(
            "How far a run gives up when a node raises: 'branch' ends the current branch "
            "(a loop goes on with its next item), 'frame' ends the current frame, 'run' stops "
            "the graph. The failing node is retried at its next evaluation either way."
        ),
        widget_config={"options": ["branch", "frame", "run"]},
    )
