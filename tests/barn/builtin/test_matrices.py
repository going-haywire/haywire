"""MAT3 and MAT4: identity defaults, row-major values and their shape check."""

import json
from typing import Any

import pytest

from haywire.barn.builtin.types import MAT3, MAT4
from haywire.core.settings import Mat3, Mat4

pytestmark = pytest.mark.unit

IDENTITY_3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _field(type_cls: Any) -> Any:
    return type_cls.create_field()


def test_a_new_matrix_is_the_identity():
    assert _field(MAT3).get_value() == IDENTITY_3
    assert _field(MAT4).get_value()[3] == [0.0, 0.0, 0.0, 1.0]


def test_a_matrix_saves_row_by_row_and_comes_back_as_its_class():
    rows = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
    field = _field(MAT3)
    field.set_value(Mat3(rows))
    saved = json.loads(json.dumps(field.to_dict()))
    assert saved == {"value": rows}
    back = MAT3.from_dict(saved)
    assert isinstance(back, Mat3)
    assert back[1][2] == 6.0


def test_integers_and_numpy_rows_save_as_floats():
    np = pytest.importorskip("numpy")
    field = _field(MAT3)
    field.set_value(np.eye(3, dtype=np.float32) * 2)
    assert field.to_dict()["value"][0] == [2.0, 0.0, 0.0]
    field.set_value([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
    assert isinstance(field.to_dict()["value"][0][0], float)


@pytest.mark.parametrize(
    "bad",
    [
        [[1.0, 0.0], [0.0, 1.0]],
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 1.0]],
        [["a", 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
    ],
)
def test_a_wrong_shape_or_content_cannot_be_saved(bad):
    field = _field(MAT3)
    field.set_value(bad)
    with pytest.raises((TypeError, ValueError)):
        field.to_dict()
    with pytest.raises((TypeError, ValueError)):
        MAT3.from_dict({"value": bad})


def test_mat4_and_mat3_are_different_shapes():
    assert isinstance(MAT4.from_dict({"value": [[1.0] * 4] * 4}), Mat4)
    with pytest.raises(ValueError, match="expected 4 rows"):
        MAT4.from_dict({"value": IDENTITY_3})


def test_two_new_matrices_do_not_share_rows():
    one, other = _field(MAT3), _field(MAT3)
    one.get_value()[0][0] = 9.0
    assert other.get_value()[0][0] == 1.0
