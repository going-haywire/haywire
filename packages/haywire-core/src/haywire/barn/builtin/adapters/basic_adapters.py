"""Basic type conversion adapters"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterable
from numbers import Integral
from typing import Any, override

from haywire.barn.builtin.types import (
    BOOL,
    CHOICES,
    FLOAT,
    INT,
    MAT3,
    MAT4,
    STRING,
    VEC2F,
    VEC2I,
    VEC3F,
    VEC3I,
    VEC4F,
    VEC4I,
)
from haywire.core.adapter.base import BaseAdapter, adapter
from haywire.core.settings.types import Mat3, Mat4, Vec2f, Vec2i, Vec3f, Vec3i, Vec4f, Vec4i


@adapter(description="Convert integer to float", converts_from=INT, converts_to=FLOAT)
class IntToFloatAdapter(BaseAdapter):
    @override
    def convert(self, value: int) -> float:
        return float(value)

    def get_test_value(self) -> int:
        return int(random.randrange(0, 100))


@adapter(description="Convert float to integer", converts_from=FLOAT, converts_to=INT)
class FloatToIntAdapter(BaseAdapter):
    @override
    def convert(self, value: float) -> int:
        return int(value)

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100) * 1.0)


@adapter(description="Convert float to text", converts_from=FLOAT, converts_to=STRING)
class FloatToStringAdapter(BaseAdapter):
    """Convert a float to its shortest text that reads back as the same number, `0.5`."""

    @override
    def convert(self, value: float) -> str:
        return str(value)

    def get_test_value(self) -> float:
        return float(random.randrange(0, 100))


@adapter(description="Convert bool to integer", converts_from=BOOL, converts_to=INT)
class BoolToIntAdapter(BaseAdapter):
    """Convert bool to integer"""

    @override
    def convert(self, value: bool) -> int:
        return int(value)

    def get_test_value(self) -> bool:
        return random.choice([True, False])


@adapter(description="String into a choices slot", converts_from=STRING, converts_to=CHOICES)
class StringToChoicesAdapter(BaseAdapter):
    """STRING -> CHOICES needs an explicit adapter.

    CHOICES is the descendant,
    so (per adapter-canon.md) an ancestor-to-descendant conversion is never a
    free passthrough — not every string is a valid choice. The reverse
    direction (CHOICES -> STRING) needs no adapter at all: CHOICES(STRING)
    already gets a free passthrough via AdapterFactory's
    issubclass(source_type, sink_type) check.
    """

    @override
    def convert(self, value: str) -> str:
        return value

    def get_test_value(self) -> str:
        return "fast"


def _int_text(entry: Any) -> str:
    """Return an integer component as text, ``-1``."""
    return str(int(entry))


def _float_text(entry: Any) -> str:
    """Return a float component as its shortest round-trip text, ``0.5``, ``1.0``.

    An integer arriving in a float vector still reads as a float (``1.0``). A numpy float
    keeps its own shortest form: ``float32(0.3)`` reads ``0.3``, not ``0.30000001192092896``.
    """
    if isinstance(entry, Integral):
        return str(float(entry))
    return str(entry)


def _vector_text(value: Iterable[Any], entry_text: Callable[[Any], str]) -> str:
    """Return a vector as its components in storage order, in parentheses: ``(0.5, -0.25)``."""
    return "(" + ", ".join(entry_text(entry) for entry in value) + ")"


def _matrix_text(value: Iterable[Iterable[Any]]) -> str:
    """Return a matrix on one line, a bracket per row: ``[[1.0, 0.0], [0.0, 1.0]]``."""
    return "[" + ", ".join("[" + ", ".join(_float_text(e) for e in row) + "]" for row in value) + "]"


def _random_ints(length: int) -> list[int]:
    """Return ``length`` random integers, negatives included."""
    return [random.randrange(-100, 100) for _ in range(length)]


def _random_floats(length: int) -> list[float]:
    """Return ``length`` random quarter-step floats, which print exactly."""
    return [random.randrange(-400, 400) / 4 for _ in range(length)]


@adapter(description="Convert a 2D integer vector to text, (x, y)", converts_from=VEC2I, converts_to=STRING)
class Vec2iToStringAdapter(BaseAdapter):
    """Convert a 2D integer vector to text in parentheses, `(1, -1)`."""

    @override
    def convert(self, value: Vec2i) -> str:
        return _vector_text(value, _int_text)

    def get_test_value(self) -> Vec2i:
        return Vec2i(_random_ints(2))


@adapter(
    description="Convert a 3D integer vector to text, (x, y, z)", converts_from=VEC3I, converts_to=STRING
)
class Vec3iToStringAdapter(BaseAdapter):
    """Convert a 3D integer vector to text in parentheses, `(1, -1, 0)`."""

    @override
    def convert(self, value: Vec3i) -> str:
        return _vector_text(value, _int_text)

    def get_test_value(self) -> Vec3i:
        return Vec3i(_random_ints(3))


@adapter(
    description="Convert a 4D integer vector to text, (w, x, y, z)", converts_from=VEC4I, converts_to=STRING
)
class Vec4iToStringAdapter(BaseAdapter):
    """Convert a 4D integer vector to text in parentheses, W first, `(1, 0, -1, 2)`."""

    @override
    def convert(self, value: Vec4i) -> str:
        return _vector_text(value, _int_text)

    def get_test_value(self) -> Vec4i:
        return Vec4i(_random_ints(4))


@adapter(description="Convert a 2D float vector to text, (x, y)", converts_from=VEC2F, converts_to=STRING)
class Vec2fToStringAdapter(BaseAdapter):
    """Convert a 2D float vector to text in parentheses, `(0.5, -0.25)`."""

    @override
    def convert(self, value: Vec2f) -> str:
        return _vector_text(value, _float_text)

    def get_test_value(self) -> Vec2f:
        return Vec2f(_random_floats(2))


@adapter(description="Convert a 3D float vector to text, (x, y, z)", converts_from=VEC3F, converts_to=STRING)
class Vec3fToStringAdapter(BaseAdapter):
    """Convert a 3D float vector to text in parentheses, `(0.5, -0.25, 1.0)`."""

    @override
    def convert(self, value: Vec3f) -> str:
        return _vector_text(value, _float_text)

    def get_test_value(self) -> Vec3f:
        return Vec3f(_random_floats(3))


@adapter(
    description="Convert a 4D float vector to text, (w, x, y, z)", converts_from=VEC4F, converts_to=STRING
)
class Vec4fToStringAdapter(BaseAdapter):
    """Convert a 4D float vector to text in parentheses, W first, `(1.0, 0.0, 0.5, -0.25)`."""

    @override
    def convert(self, value: Vec4f) -> str:
        return _vector_text(value, _float_text)

    def get_test_value(self) -> Vec4f:
        return Vec4f(_random_floats(4))


@adapter(
    description="Convert a 3x3 matrix to text, one bracket per row", converts_from=MAT3, converts_to=STRING
)
class Mat3ToStringAdapter(BaseAdapter):
    """Convert a 3x3 matrix to text on one line, rows first, `[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], ...]`."""

    @override
    def convert(self, value: Mat3) -> str:
        return _matrix_text(value)

    def get_test_value(self) -> Mat3:
        return Mat3([_random_floats(3) for _ in range(3)])


@adapter(
    description="Convert a 4x4 matrix to text, one bracket per row", converts_from=MAT4, converts_to=STRING
)
class Mat4ToStringAdapter(BaseAdapter):
    """Convert a 4x4 matrix to text on one line, rows first, `[[1.0, 0.0, 0.0, 0.0], ...]`."""

    @override
    def convert(self, value: Mat4) -> str:
        return _matrix_text(value)

    def get_test_value(self) -> Mat4:
        return Mat4([_random_floats(4) for _ in range(4)])
