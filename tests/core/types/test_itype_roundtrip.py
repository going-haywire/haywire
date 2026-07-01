# tests/core/types/test_itype_roundtrip.py
"""IType to_dict/from_dict must round-trip the actual value (P3 prerequisite).

The base PrimitiveType.from_dict stub returns the type default; COLOR and the
VEC* types relied on it and silently dropped their value. The JSON settings
cutover routes tier reads through from_dict, so these must round-trip.
"""

import haywire.core.graph.editor  # noqa: F401  (circular-import guard, per CLAUDE.md)

import pytest

from haywire.barn.builtin.types import COLOR, VEC2I, VEC3I, VEC4I, VEC2F, VEC3F, VEC4F
from haywire.core.settings.types import Vec2i, Vec3i, Vec4i, Vec2f, Vec3f, Vec4f


def test_color_roundtrips_value():
    assert COLOR.from_dict(COLOR("#abcdef").to_dict()) == "#abcdef"


@pytest.mark.parametrize(
    "itype, raw",
    [
        (VEC2I, Vec2i([1, 2])),
        (VEC3I, Vec3i([1, 2, 3])),
        (VEC4I, Vec4i([1, 2, 3, 4])),
        (VEC2F, Vec2f([1.5, 2.5])),
        (VEC3F, Vec3f([1.5, 2.5, 3.5])),
        (VEC4F, Vec4f([1.5, 2.5, 3.5, 4.5])),
    ],
)
def test_vec_roundtrips_value(itype, raw):
    restored = itype.from_dict(itype(raw).to_dict())
    assert list(restored) == list(raw)
