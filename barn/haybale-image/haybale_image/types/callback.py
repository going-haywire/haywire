"""CALLBACK_IMAGE — the subscription between an image emitter and an Image Event node."""

from dataclasses import dataclass

from haywire.barn.builtin.wires import CallbackWire
from haywire.core.types import BaseType, type


@type(
    label="Callback Image",
    description="Subscription for emitters that deliver single images",
    wire_type=CallbackWire,
    default=None,
    color="#3f8fd2",
)
@dataclass
class CALLBACK_IMAGE(BaseType):
    """Subscription value: the callback name a listener registers under.

    A `BaseType` on `CallbackWire`, deliberately not a subclass of the core `CALLBACK`
    (or of any other callback type): only an emitter whose pooled inlet is
    `PooledType[CALLBACK_IMAGE]` connects to an Image Event node.

    The emitter's payload for each image:
    `{"image": ImageValue, "timestamp": float, "frame_number": int}`.

    Attributes:
        name: Callback event name used for dispatch routing.
    """

    name: str = ""
