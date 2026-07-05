"""Vector ITypes — PrimitiveType wrappers over the framework Vec_ classes.

VecMeta (length, element_type, component labels) is attached via widget metadata
so the vec editor renders X/Y/Z component fields (wired in Plan 2).
"""

from typing import ClassVar

from haywire.barn.builtin import widget_keys
from haywire.core.settings.types import (
    Vec2f,
    Vec2i,
    Vec3f,
    Vec3i,
    Vec4f,
    Vec4i,
    get_vec_meta,
)
from haywire.core.types import FlowType, PrimitiveType
from haywire.core.types import type as type_decorator


class _VecSerialize:
    """Mixin: to_dict stores a plain list; from_dict rebuilds the Vec_ subclass.

    ``_vec_cls`` is the framework Vec_ list-subclass this IType wraps.
    """

    _vec_cls: ClassVar[type]

    def to_dict(self) -> dict:
        return {"value": list(self._value)}  # type: ignore[attr-defined]

    @classmethod
    def from_dict(cls, data: dict):
        return cls._vec_cls(data.get("value", []))


def _vec_default(vec_cls: type) -> dict:
    meta = get_vec_meta(vec_cls)
    if meta is None:
        raise ValueError(f"No VecMeta registered for {vec_cls!r}")
    zero = 0 if meta.element_type is int else 0.0
    return {"value": [zero] * meta.length}


def _vec_widget_config(vec_cls: type) -> dict:
    """Carry VecMeta (length + component labels) so VecWidget can render N rows.

    ``orientation: "column"`` matches VecWidget's own default layout so the
    panel's row-alignment check top-aligns the label against the multi-row block
    instead of centering it.
    """
    meta = get_vec_meta(vec_cls)
    if meta is None:
        raise ValueError(f"No VecMeta registered for {vec_cls!r}")
    return {
        "properties": {
            "vec_meta": {"length": meta.length, "labels": list(meta.labels)},
            "orientation": "column",
        }
    }


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec2i",
    description="2D integer vector",
    default=_vec_default(Vec2i),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec2i),
)
class VEC2I(_VecSerialize, PrimitiveType[Vec2i]):
    """2D integer vector."""

    _vec_cls = Vec2i


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec3i",
    description="3D integer vector",
    default=_vec_default(Vec3i),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec3i),
)
class VEC3I(_VecSerialize, PrimitiveType[Vec3i]):
    """3D integer vector."""

    _vec_cls = Vec3i


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec4i",
    description="4D integer vector",
    default=_vec_default(Vec4i),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec4i),
)
class VEC4I(_VecSerialize, PrimitiveType[Vec4i]):
    """4D integer vector."""

    _vec_cls = Vec4i


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec2f",
    description="2D float vector",
    default=_vec_default(Vec2f),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec2f),
)
class VEC2F(_VecSerialize, PrimitiveType[Vec2f]):
    """2D float vector."""

    _vec_cls = Vec2f


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec3f",
    description="3D float vector",
    default=_vec_default(Vec3f),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec3f),
)
class VEC3F(_VecSerialize, PrimitiveType[Vec3f]):
    """3D float vector."""

    _vec_cls = Vec3f


@type_decorator(
    flow_type=FlowType.DATA,
    label="Vec4f",
    description="4D float vector",
    default=_vec_default(Vec4f),
    widget_key=widget_keys.VEC_WIDGET,
    widget_config=_vec_widget_config(Vec4f),
)
class VEC4F(_VecSerialize, PrimitiveType[Vec4f]):
    """4D float vector."""

    _vec_cls = Vec4f
