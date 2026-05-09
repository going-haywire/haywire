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


class Vec2i(list):
    pass


class Vec3i(list):
    pass


class Vec4i(list):
    pass


class Vec2f(list):
    pass


class Vec3f(list):
    pass


class Vec4f(list):
    pass


_VEC_META[Vec2i] = VecMeta(length=2, element_type=int, labels=("X", "Y"))
_VEC_META[Vec3i] = VecMeta(length=3, element_type=int, labels=("X", "Y", "Z"))
_VEC_META[Vec4i] = VecMeta(length=4, element_type=int, labels=("W", "X", "Y", "Z"))
_VEC_META[Vec2f] = VecMeta(length=2, element_type=float, labels=("X", "Y"))
_VEC_META[Vec3f] = VecMeta(length=3, element_type=float, labels=("X", "Y", "Z"))
_VEC_META[Vec4f] = VecMeta(length=4, element_type=float, labels=("W", "X", "Y", "Z"))


def get_vec_meta(type_: type) -> "VecMeta | None":
    """Return VecMeta if type_ is a vector type, else None."""
    return _VEC_META.get(type_)
