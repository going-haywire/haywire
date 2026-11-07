"""Fields as text: what can be stored, and how a bad field is named."""

import json

import pytest
import numpy as np
from haybale_core.types.specs import LIST
from haybale_image.types.image import IMAGE_RGB
from haybale_image.value import ImageValue

from haywire.barn.builtin.carrier import BundleValue
from haywire.barn.builtin.field_text import can_be_saved, fields_from_text, fields_to_text
from haywire.barn.builtin.types import BOOL, FLOAT, INT, MAT3, STRING, VEC3F
from haywire.core.settings import Mat3, Vec3f

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _libraries(library_system):
    return library_system


def _round_trip(carrier):
    fields, problems = fields_from_text(fields_to_text(carrier.fields))
    assert problems == []
    return fields


def test_numbers_text_vectors_and_matrices_come_back_with_their_types():
    rows = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]]
    carrier = (
        BundleValue()
        .stamped("n", 3, INT)
        .stamped("t", 1.5, FLOAT)
        .stamped("ok", True, BOOL)
        .stamped("s", "text", STRING)
        .stamped("v", Vec3f([1.0, 2.0, 3.0]), VEC3F)
        .stamped("m", Mat3(rows), MAT3)
    )
    fields = _round_trip(carrier)
    assert {key: stamp.value for key, stamp in fields.items()} == {
        "n": 3,
        "t": 1.5,
        "ok": True,
        "s": "text",
        "v": [1.0, 2.0, 3.0],
        "m": rows,
    }
    assert fields["m"].type_key == MAT3.class_identity.registry_key


def test_every_bad_field_is_named_with_why():
    image = ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))
    carrier = (
        BundleValue()
        .stamped("good", 1, INT)
        .stamped("preview", image, IMAGE_RGB)
        .stamped("lut", [np.zeros(2)], LIST)
        .stamped("crooked", [[1.0]], MAT3)
    )
    with pytest.raises(ValueError, match="Cannot write fields") as caught:
        fields_to_text(carrier.fields)
    text = str(caught.value)
    assert "preview (IMAGE_RGB, this type is not saved)" in text
    assert "lut (LIST" in text
    assert "crooked (MAT3" in text
    assert "good" not in text


def test_a_value_too_large_is_named():
    carrier = BundleValue().stamped("big", "x" * 2_000_000, STRING)
    with pytest.raises(ValueError, match=r"big \(STRING, .*larger than"):
        fields_to_text(carrier.fields)


def test_a_type_that_does_not_read_back_is_named(monkeypatch):
    carrier = BundleValue().stamped("t", 1.5, FLOAT)
    monkeypatch.setattr(FLOAT, "from_dict", classmethod(lambda cls, data: 0.0))
    with pytest.raises(ValueError, match=r"t \(FLOAT, .*does not read back"):
        fields_to_text(carrier.fields)


def test_a_type_not_installed_is_left_out_and_named():
    text = fields_to_text(BundleValue().stamped("a", 1, INT).stamped("b", 2, INT).fields)
    doc = json.loads(text)
    doc["fields"]["b"]["type"] = "nolib:type:GONE"
    fields, problems = fields_from_text(json.dumps(doc))
    assert set(fields) == {"a"}
    assert len(problems) == 1
    assert "'b'" in problems[0]
    assert "nolib:type:GONE" in problems[0]


def test_a_file_cannot_ask_for_a_type_that_is_never_saved():
    key = IMAGE_RGB.class_identity.registry_key
    text = json.dumps({"version": 1, "fields": {"x": {"type": key, "data": {"value": {}}}}})
    fields, problems = fields_from_text(text)
    assert fields == {}
    assert "x" in problems[0]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[]",
        '{"version": 1}',
        '{"version": 99, "fields": {}}',
        '{"version": 1, "fields": []}',
    ],
)
def test_unreadable_text_gives_no_fields_and_says_so(text):
    fields, problems = fields_from_text(text)
    assert fields == {}
    assert problems


@pytest.mark.parametrize(
    "entry",
    [
        "x",
        {"type": 3, "data": {}},
        {"type": "haywire-core:type:INT"},
        {"type": "haywire-core:type:MAT3", "data": {"value": [[1.0]]}},
    ],
)
def test_a_malformed_entry_is_left_out_and_named(entry):
    fields, problems = fields_from_text(json.dumps({"version": 1, "fields": {"bad": entry}}))
    assert fields == {}
    assert "bad" in problems[0]


def test_an_invalid_key_is_left_out():
    text = json.dumps(
        {"version": 1, "fields": {"a b": {"type": "haywire-core:type:INT", "data": {"value": 1}}}}
    )
    fields, problems = fields_from_text(text)
    assert fields == {}
    assert "a b" in problems[0]


def test_what_can_be_saved_comes_from_the_type():
    assert can_be_saved(FLOAT.class_identity)
    assert can_be_saved(MAT3.class_identity)
    assert not can_be_saved(IMAGE_RGB.class_identity)
