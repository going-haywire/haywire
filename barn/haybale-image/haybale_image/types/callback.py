"""IMAGE_CALLBACK — the subscription between an image emitter and an Image Event node."""

from __future__ import annotations

from dataclasses import dataclass

from haywire.api import BaseType, CallbackWire, type


@type(
    label="Image Callback",
    description="Subscription for emitters that deliver single images",
    wire_type=CallbackWire,
    default=None,
    color="#3f8fd2",
)
@dataclass
class IMAGE_CALLBACK(BaseType):
    """Subscription value: the callback name a listener registers under.

    A `BaseType` on `CallbackWire`, deliberately not a subclass of the core `CALLBACK`
    (or of any other callback type): only an emitter whose pooled inlet is
    `POOLED[IMAGE_CALLBACK]` connects to an Image Event node.

    The emitter's payload for each image:
    `{"image": ImageValue, "timestamp": float, "frame_number": int}`.

    Attributes:
        name: Callback event name used for dispatch routing.
    """

    name: str = ""
