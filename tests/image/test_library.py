from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def test_library_identity_is_haybale_image():
    from haybale_image import Library

    assert Library.class_identity.name == "haybale-image"


def test_codec_dependencies_are_present():
    from PIL import features

    assert features.check("avif")


def test_no_plain_opencv_beside_contrib():
    from importlib.metadata import PackageNotFoundError, version

    # The opencv wheels share one cv2/ package; a plain one installed beside contrib
    # silently replaces it (.insights/project_cv2_distribution_clash.md).
    for name in ("opencv-python", "opencv-python-headless"):
        try:
            found = version(name)
        except PackageNotFoundError:
            continue
        pytest.fail(f"{name} {found} is installed beside opencv-contrib-python")


def test_cv2_is_contrib():
    import cv2

    assert hasattr(cv2, "ximgproc")  # contrib-only module
