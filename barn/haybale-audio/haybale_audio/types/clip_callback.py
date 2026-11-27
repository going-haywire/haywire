"""CLIP_CALLBACK — the subscription between a clip emitter and a Clip Event node."""

from __future__ import annotations

from dataclasses import dataclass

from haywire.api import BaseType, CallbackWire, type


@type(
    label="Clip Callback",
    description="Subscription for emitters that deliver whole audio clips",
    wire_type=CallbackWire,
    default=None,
    color="#2f7fb0",
)
@dataclass
class CLIP_CALLBACK(BaseType):
    """Subscription value: the callback name a Clip Event registers under.

    Independent of `AUDIO_CALLBACK`: a clip emitter (Clip Segmenter) connects only to Clip Event
    nodes, and an audio emitter only to Audio Event nodes.

    The emitter's payload for each clip:
    `{"clip": AudioBlock, "timestamp": float, "clip_number": int}`.

    Attributes:
        name: Callback event name used for dispatch routing.
    """

    name: str = ""
