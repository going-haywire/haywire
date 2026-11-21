"""Settings shared by the loop nodes that record failed iterations (For Each File, Loop Array)."""

from haywire.api import STRING, NodeSettings, Promotable, MenuWidget, setting

__all__ = ["ON_ERROR", "LoopErrors"]

#: Values of the On Error setting.
ON_ERROR = ("continue", "stop")


class LoopErrors(NodeSettings):
    """What a loop does after a failed iteration.

    On Error is in the properties and can be promoted to a row on the card or an inlet.
    """

    on_error = setting[STRING](
        "continue",
        label="On Error",
        description="After a failed iteration: continue with the next one, or stop",
        widget=MenuWidget.config(properties={"options": list(ON_ERROR)}),
        promotable=Promotable.INLET | Promotable.CONFIG,
    )
