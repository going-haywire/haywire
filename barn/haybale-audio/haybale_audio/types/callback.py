"""CALLBACK_AUDIO — the subscription between an audio emitter and an Audio Event node."""

from dataclasses import dataclass

from haywire.barn.builtin.wires import CallbackWire
from haywire.core.types import BaseType, type


@type(
    label="Callback Audio",
    description="Subscription for emitters that deliver audio blocks",
    wire_type=CallbackWire,
    default=None,
    color="#4ab0d9",
)
@dataclass
class CALLBACK_AUDIO(BaseType):
    """Subscription value: the callback name a listener registers under.

    A `BaseType` on `CallbackWire`, independent of the core `CALLBACK` and of every other callback
    type: only an emitter whose pooled inlet is `PooledType[CALLBACK_AUDIO]` connects to an
    Audio Event node.

    The emitter's payload for each block:
    `{"audio": AudioBlock, "timestamp": float, "block_number": int}`.

    Attributes:
        name: Callback event name used for dispatch routing.
    """

    name: str = ""
