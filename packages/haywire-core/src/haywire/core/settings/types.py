# haywire/core/settings/types.py
"""
Type aliases for descriptor annotations — purely for IDE hinting.
At runtime these are just str.
"""

from typing import NamedTuple

Color = str  # hex or rgba string, implies color-picker widget
Icon = str  # material icon name, implies icon-picker widget

# Vector type aliases — stored as list[int] or list[float]
# Each carries component labels and element type as metadata via VecMeta.


class VecMeta(NamedTuple):
    length: int
    element_type: type
    labels: tuple


_VEC_META: dict = {}


def _make_vec(length: int, element_type: type, labels: tuple) -> type:
    """Create a list subtype that carries vector metadata."""
    cls = type(f"_Vec{length}{'i' if element_type is int else 'f'}", (list,), {})
    _VEC_META[cls] = VecMeta(length=length, element_type=element_type, labels=labels)
    return cls


Vec2i = _make_vec(2, int, ("X", "Y"))
Vec3i = _make_vec(3, int, ("X", "Y", "Z"))
Vec4i = _make_vec(4, int, ("W", "X", "Y", "Z"))
Vec2f = _make_vec(2, float, ("X", "Y"))
Vec3f = _make_vec(3, float, ("X", "Y", "Z"))
Vec4f = _make_vec(4, float, ("W", "X", "Y", "Z"))


def get_vec_meta(type_: type) -> "VecMeta | None":
    """Return VecMeta if type_ is a vector type, else None."""
    return _VEC_META.get(type_)
