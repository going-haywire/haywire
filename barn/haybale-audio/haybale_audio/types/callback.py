"""AUDIO_CALLBACK — the subscription between an audio emitter and an Audio Event node."""

from dataclasses import dataclass

from haywire.api import BaseType, CallbackWire, type


@type(
    label="Audio Callback",
    description="Subscription for emitters that deliver audio blocks",
    wire_type=CallbackWire,
    default=None,
    color="#4ab0d9",
)
@dataclass
class AUDIO_CALLBACK(BaseType):
    """Subscription value: the callback name a listener registers under.

    A `BaseType` on `CallbackWire`, independent of the core `CALLBACK` and of every other callback
    type: only an emitter whose pooled inlet is `POOLED[AUDIO_CALLBACK]` connects to an
    Audio Event node.

    The emitter's payload for each block:
    `{"audio": AudioBlock, "timestamp": float, "block_number": int}`.

    Attributes:
        name: Callback event name used for dispatch routing.
    """

    name: str = ""
