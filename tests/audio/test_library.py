import pytest

pytestmark = pytest.mark.unit


def test_library_identity_is_haybale_audio():
    from haybale_audio import Library

    assert Library.class_identity.name == "haybale-audio"
