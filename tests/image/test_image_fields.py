"""Images carry fields: what keeps them, what drops them, and what the file sees."""

import numpy as np
import pytest

from haywire.barn.builtin.carrier import CarrierValue
from haywire.barn.builtin.types import CARRIER, FLOAT

from haybale_image.io.codecs import EncodeOptions, encode_image
from haybale_image.io.formats import Format
from haybale_image.types.image import IMAGE, IMAGE_GRAY, IMAGE_RGB, IMAGE_RGBA
from haybale_image.value import ImageMetadata, ImageValue, Layout, convert_layout

pytestmark = pytest.mark.unit


def _img() -> ImageValue:
    return ImageValue.from_array(np.zeros((2, 2, 3), np.uint8))


def test_an_image_is_a_carrier():
    assert isinstance(_img(), CarrierValue)
    assert dict(_img().fields) == {}


def test_stamping_shares_pixels_and_cache():
    a = _img()
    a.array()
    b = a.stamped("t", 1.5, FLOAT)
    assert b._primary is a._primary
    assert b._cache is a._cache
    assert dict(a.fields) == {}


def test_with_metadata_keeps_fields_and_the_cache():
    a = _img().stamped("t", 1.5, FLOAT)
    a.array()
    b = a.with_metadata(ImageMetadata(icc=b"x"))
    assert b.fields["t"].value == 1.5
    assert b._cache is a._cache
    assert a.metadata.icc is None


def test_derive_keeps_icc_and_drops_fields():
    src = _img().with_metadata(ImageMetadata(icc=b"x")).stamped("t", 1.5, FLOAT)
    out = src.derive(_img())
    assert out.metadata.icc == b"x"
    assert dict(out.fields) == {}


def test_a_bare_new_image_has_neither():
    assert dict(ImageValue.from_array(np.zeros((2, 2), np.uint8)).fields) == {}


@pytest.mark.parametrize("layout", [Layout.GRAY, Layout.RGBA])
def test_convert_layout_keeps_fields_and_metadata(layout):
    src = _img().with_metadata(ImageMetadata(icc=b"x")).stamped("t", 1.5, FLOAT)
    out = convert_layout(src, layout)
    assert out.layout is layout
    assert out.fields["t"].value == 1.5
    assert out.metadata.icc == b"x"


def test_fields_do_not_change_the_saved_file():
    img = _img()
    options = EncodeOptions()
    stamped = encode_image(img.stamped("t", 1.5, FLOAT), Format.PNG, options)
    assert stamped == encode_image(img, Format.PNG, options)


def test_describe_lists_icc_and_exif_sizes():
    assert _img().describe() == {}
    assert _img().with_metadata(ImageMetadata(icc=b"abc")).describe() == {"icc": "3 bytes"}
    both = _img().with_metadata(ImageMetadata(icc=b"abc", exif=b"e"))
    assert both.describe() == {"icc": "3 bytes", "exif": "1 bytes"}


@pytest.mark.parametrize("image_type", [IMAGE, IMAGE_GRAY, IMAGE_RGB, IMAGE_RGBA])
def test_image_types_are_visible_carriers_with_unchanged_keys(image_type):
    assert issubclass(image_type, CARRIER)
    assert image_type.element_type_cls is ImageValue
    assert image_type.class_identity.hidden is False
    assert image_type.class_identity.registry_key == f"haybale-image:type:{image_type.__name__}"


@pytest.mark.parametrize(("image_type", "layout"), [(IMAGE, Layout.GRAY), (IMAGE_RGB, Layout.RGB)])
def test_a_new_field_starts_as_the_empty_image_of_its_layout(image_type, layout):
    value = image_type.create_field().get_value()
    assert isinstance(value, ImageValue)
    assert value.layout is layout
    assert value.is_empty
