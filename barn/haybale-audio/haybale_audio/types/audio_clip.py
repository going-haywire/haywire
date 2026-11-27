"""AUDIO_CLIP — a whole audio clip, such as one utterance, passed as one value."""

from __future__ import annotations

from typing import Any

from haybale_audio.value import AudioBlock
from haywire.api import DataWire, PrimitiveField, PrimitiveType, StoreStrategy
from haywire.api import type as type_decorator


@type_decorator(
    wire_type=DataWire,
    label="Audio Clip",
    description="A whole audio clip, such as one utterance, as one block. Never saved with the graph.",
    color="#2f7fb0",
    store_strategy=StoreStrategy.NEVER,
    default={"value": {}},
)
class AUDIO_CLIP(PrimitiveType[AudioBlock | None]):
    """A whole clip as one `AudioBlock`; the value is never saved with the graph.

    The value is the same as `AUDIO`'s, but the two ports never connect: a clip travels on control
    flow (Collect Clip's Done, Clip Event's Clip Ready), a block on an audio flow. The nodes between
    them are Collect Clip and Clip Segmenter (blocks to clips) and Clip Player (a clip to blocks).
    """

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        super().__init__(value, **kwargs)
        self._value = _as_clip(self._value)  # the type's default arrives as JSON

    def to_dict(self) -> dict[str, Any]:
        """Return ``{"value": {}}``: samples are not serialized."""
        return {"value": {}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> None:
        """Return ``None``: a clip never round-trips."""
        return None


class AUDIO_CLIPField(PrimitiveField):
    """DataField for AUDIO_CLIP: starts empty (``None``)."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self._default = _as_clip(self._default)
        self._value = self._default

    def _set_own(self, value: Any) -> None:
        self._value = _as_clip(value)


def _as_clip(value: Any) -> AudioBlock | None:
    return value if isinstance(value, AudioBlock) else None


AUDIO_CLIP.field_class = AUDIO_CLIPField
