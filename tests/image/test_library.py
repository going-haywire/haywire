import pytest

pytestmark = pytest.mark.unit


def test_library_identity_is_haybale_image():
    from haybale_image import Library

    assert Library.class_identity.name == "haybale-image"


def test_codec_dependencies_are_present():
    import cv2
    from PIL import features

    assert cv2.__version__.startswith("5.")  # contrib 5.x, not opencv-python 4.x
    assert features.check("avif")


def test_cv2_is_contrib():
    import cv2

    assert hasattr(cv2, "ximgproc")  # contrib-only module
