"""InstallType.is_editable — the single authority for source-write permission."""

import pytest

from haywire.core.library.install_type import InstallType

pytestmark = pytest.mark.unit


def test_only_editable_is_editable():
    # EDITABLE is a pip -e install pointing at the developer's on-disk source.
    assert InstallType.EDITABLE.is_editable() is True
    # REGULAR lives in immutable site-packages; FOLDER is the framework-owned
    # builtin library — neither is user-editable.
    assert InstallType.REGULAR.is_editable() is False
    assert InstallType.FOLDER.is_editable() is False


def test_is_editable_covers_every_member():
    # Guards against a new InstallType silently defaulting to "editable" —
    # exactly one member may return True.
    editable = [t for t in InstallType if t.is_editable()]
    assert editable == [InstallType.EDITABLE]
