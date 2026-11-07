"""Transform matrix types, beside the vectors: square, of floats, row by row."""

from typing import Any, ClassVar

from haywire.barn.builtin import widget_keys
from haywire.core.settings.types import Mat3, Mat4
from haywire.core.types import PrimitiveType
from haywire.core.types import type as type_decorator
from haywire.core.types.fields import DataField, PrimitiveField
from ..wires import DataWire


def _identity(size: int) -> list[list[float]]:
    return [[1.0 if row == col else 0.0 for col in range(size)] for row in range(size)]


def _rows(value: Any, size: int) -> list[list[float]]:
    """Return ``value`` as ``size`` rows of ``size`` floats; numpy arrays and integers are fine.

    Raises:
        TypeError: An entry is not a real number.
        ValueError: The shape is not ``size`` by ``size``.
    """
    rows = list(value)
    if len(rows) != size or any(len(row) != size for row in rows):
        raise ValueError(f"expected {size} rows of {size} numbers")
    return [[float(entry) for entry in row] for row in rows]


class MatrixField(PrimitiveField):
    """A field of a matrix type, holding its own copy of the default rows."""

    def __post_init__(self) -> None:
        super().__post_init__()
        self.reset()

    def reset(self) -> None:
        """Reset to a fresh copy of the default rows, so an edit in place cannot reach other fields."""
        super().reset()
        self._value = [list(row) for row in self._default or ()]


class _MatSerialize:
    """Mixin: to_dict stores nested lists; from_dict rebuilds the matrix class."""

    _mat_cls: ClassVar[Any]
    field_class: type[DataField[Any]] | None = MatrixField

    def to_dict(self) -> dict:
        return {"value": _rows(self._value, self._mat_cls.size)}  # type: ignore[attr-defined]

    @classmethod
    def from_dict(cls, data: dict) -> Any:
        return cls._mat_cls(_rows(data.get("value", _identity(cls._mat_cls.size)), cls._mat_cls.size))


@type_decorator(
    wire_type=DataWire,
    label="Matrix 3x3",
    description="3x3 matrix: a 2D transform, a homography, a camera matrix or a 3D rotation",
    default={"value": _identity(3)},
    widget_key=widget_keys.MATRIX_WIDGET,
    widget_config={"properties": {"size": 3, "orientation": "column"}},
)
class MAT3(_MatSerialize, PrimitiveType[Mat3]):
    """A 3x3 matrix of floats, starting as the identity.

    Rows come first: `m[row][col]`, as in numpy and OpenCV, so `np.array(m)` gives the
    matrix. Data from OpenGL lists columns first and needs transposing.
    """

    _mat_cls = Mat3


@type_decorator(
    wire_type=DataWire,
    label="Matrix 4x4",
    description="4x4 matrix: a 3D transform, a view or a projection",
    default={"value": _identity(4)},
    widget_key=widget_keys.MATRIX_WIDGET,
    widget_config={"properties": {"size": 4, "orientation": "column"}},
)
class MAT4(_MatSerialize, PrimitiveType[Mat4]):
    """A 4x4 matrix of floats, starting as the identity.

    Rows come first: `m[row][col]`, as in numpy and OpenCV, so `np.array(m)` gives the
    matrix. Data from OpenGL lists columns first and needs transposing.
    """

    _mat_cls = Mat4
