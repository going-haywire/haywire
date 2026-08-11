"""LibraryInfo carries a Haybale row whether or not the library is installed."""

from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.library.haybale import Haybale


def test_installed_info_carries_the_row():
    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="1.0.0", label="X", source="local"),
        identity=LibraryIdentity(id="x", label="X", version="1.0.0"),
        enabled=True,
        install_type=InstallType.EDITABLE,
        distribution_name="haybale-x",
    )
    assert info.installed is True
    assert info.row.label == "X"


def test_not_installed_info_has_empty_install_state():
    info = LibraryInfo(
        row=Haybale(name="haybale-x", version="2.0.0", label="X", source="pypi"),
        identity=LibraryIdentity(),
        enabled=False,
        install_type=InstallType.NOT_INSTALLED,
        distribution_name="",
    )
    assert info.installed is False
    assert info.enabled is False
    assert info.row.version == "2.0.0"


def test_entry_for_haybale_builds_a_not_installed_info():
    from haybale_marketplace.library_manager import LibraryManager

    pkg = Haybale(name="haybale-x", version="2.0.0", label="X", source="pypi")
    info = LibraryManager.entry_for_haybale(pkg)
    assert info.installed is False
    assert info.install_type is InstallType.NOT_INSTALLED
    assert info.row is pkg
    assert info.distribution_name == "haybale-x"
