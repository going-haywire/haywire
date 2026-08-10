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


def test_not_installed_is_not_editable():
    from haywire.core.library.install_type import InstallType

    assert InstallType.NOT_INSTALLED.value == "not_installed"
    assert InstallType.NOT_INSTALLED.is_editable() is False


def test_not_installed_is_not_framework_origin():
    from haywire.core.library.info import LibraryInfo
    from haywire.core.library.install_type import InstallType
    from haywire.core.marketstall import Haybale
    from haywire.core.library.identity import LibraryIdentity
    from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin

    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="1.0.0", source="pypi"),
        identity=LibraryIdentity(id="x"),
        enabled=False,
        install_type=InstallType.NOT_INSTALLED,
        distribution_name="haybale-x",
    )
    origin = compute_library_origin(info, None, catalog_entry=info.row)
    assert origin is LibraryOrigin.PYPI
    assert origin.is_protected is False
