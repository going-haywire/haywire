import pytest

pytestmark = pytest.mark.unit


def test_library_identity_is_haybale_image():
    from haybale_image import Library

    assert Library.class_identity.name == "haybale-image"
