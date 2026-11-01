"""MODEL_REF: a reference to a model, by catalog entry or by file."""

from typing import Any

from haywire.barn.builtin.wires import DataWire
from haywire.core.types import PrimitiveField, PrimitiveType
from haywire.core.types import type as type_decorator
from haywire.core.types.port import DataPort

from haybale_models.value import ModelRef


@type_decorator(
    wire_type=DataWire,
    label="Model",
    description=(
        "A model, named by a catalog entry or by a file (url and sha256). "
        "Resolve Model turns it into a path on disk."
    ),
    color="#b07ad9",
    default={"value": {}},
    widget_key="haybale-models:widget:ModelRefWidget",
    widget_config={"properties": {"filter": {}, "prefer": []}},
)
class MODEL_REF(PrimitiveType[ModelRef]):
    """A model, named by a catalog entry or by a file.

    The port's `filter` narrows the picker by catalog field; `prefer` is an ordered
    list of tag sets used to pick a variant.
    """

    def to_dict(self) -> dict:
        return {"value": self._value.to_dict()}

    @classmethod
    def from_dict(cls, data: dict) -> ModelRef:
        return ModelRef.from_dict(data.get("value", {}))

    @classmethod
    def _configure_port(cls, port: DataPort, **context: Any) -> None:
        """Fill in the type's own widget properties (`filter`, `prefer`) the port's config leaves out."""
        own = cls.class_identity.widget_config.get("properties", {})
        if not own:
            return
        properties = dict(port.widget_config.get("properties", {}))
        for key, value in own.items():
            properties.setdefault(key, value)
        port.widget_config = {**port.widget_config, "properties": properties}


class MODEL_REFField(PrimitiveField):
    """DataField for MODEL_REF: stores a ``ModelRef``, building one from a dict it is given.

    Accepts the bare dict and the serialized form ``{"value": {...}}``, for the
    type's default and for every write.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        self._default = _as_model_ref(self._default)
        self._value = self._default

    def _set_own(self, value: Any) -> None:
        self._value = _as_model_ref(value)


def _as_model_ref(value: Any) -> Any:
    if isinstance(value, dict):
        inner = value.get("value")
        return ModelRef.from_dict(inner if isinstance(inner, dict) else value)
    return value


MODEL_REF.field_class = MODEL_REFField
