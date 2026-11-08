"""AUDIO — one block of audio samples."""

from typing import Any

from haywire.barn.builtin.wires import DataWire
from haywire.core.types import PrimitiveField, PrimitiveType, StoreStrategy
from haywire.core.types import type as type_decorator

from haybale_audio.value import AudioBlock


@type_decorator(
    wire_type=DataWire,
    label="Audio",
    description="A block of audio samples. Never saved with the graph.",
    color="#4ab0d9",
    store_strategy=StoreStrategy.NEVER,
    default={"value": {}},
)
class AUDIO(PrimitiveType[AudioBlock | None]):
    """A block of planar float32 samples; the value is never saved with the graph."""

    def __init__(self, value: Any = None, **kwargs: Any) -> None:
        super().__init__(value, **kwargs)
        self._value = _as_block(self._value)  # the type's default arrives as JSON

    def to_dict(self) -> dict[str, Any]:
        """Return ``{"value": {}}``: samples are not serialized."""
        return {"value": {}}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> None:
        """Return ``None``: a block never round-trips."""
        return None


class AUDIOField(PrimitiveField):
    """DataField for AUDIO: starts empty (``None``)."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self._default = _as_block(self._default)
        self._value = self._default

    def _set_own(self, value: Any) -> None:
        self._value = _as_block(value)


def _as_block(value: Any) -> AudioBlock | None:
    return value if isinstance(value, AudioBlock) else None


AUDIO.field_class = AUDIOField
