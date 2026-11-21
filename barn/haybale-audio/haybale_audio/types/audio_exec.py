"""AUDIO_EXEC — the execution signal that sequences the nodes of an audio flow."""

from haywire.api import EXEC, ControlWire, StoreStrategy, type as type_decorator


@type_decorator(
    wire_type=ControlWire,
    label="Audio Execution Signal",
    description="Signal for sequencing the nodes of an audio flow",
    color="#3f96b8",
    default={"value": {}},
    store_strategy=StoreStrategy.NEVER,
)
class AUDIO_EXEC(EXEC):
    """The execution signal between the nodes of an audio flow, everything after an Audio Event.

    It is an `EXEC` that only audio nodes accept. An `AUDIO_EXEC` outlet connects to `AUDIO_EXEC`
    and to `EXEC` inlets; a plain `EXEC` outlet does not connect to an `AUDIO_EXEC` inlet. An audio
    flow can therefore drive a standard control node, and a standard control node cannot drive an
    audio flow. Starting and stopping audio nodes stays with plain `EXEC`.

    A control node driven from an audio flow runs inside the flow's pass, so its time counts against
    the block period.
    """
