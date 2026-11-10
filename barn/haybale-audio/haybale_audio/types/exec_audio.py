"""EXEC_AUDIO — the execution signal that sequences the nodes of an audio flow."""

from haywire.barn.builtin.types import EXEC
from haywire.barn.builtin.wires import ControlWire
from haywire.core.types import StoreStrategy
from haywire.core.types import type as type_decorator


@type_decorator(
    wire_type=ControlWire,
    label="Audio Execution Signal",
    description="Signal for sequencing the nodes of an audio flow",
    color="#3f96b8",
    default={"value": {}},
    store_strategy=StoreStrategy.NEVER,
)
class EXEC_AUDIO(EXEC):
    """The execution signal between the nodes of an audio flow, everything after an Audio Event.

    It is an `EXEC` that only audio nodes accept. An `EXEC_AUDIO` outlet connects to `EXEC_AUDIO`
    and to `EXEC` inlets; a plain `EXEC` outlet does not connect to an `EXEC_AUDIO` inlet. An audio
    flow can therefore drive a standard control node, and a standard control node cannot drive an
    audio flow. Starting and stopping audio nodes stays with plain `EXEC`.

    A control node driven from an audio flow runs inside the flow's pass, so its time counts against
    the block period.
    """
