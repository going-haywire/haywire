"""LibraryOrigin — the second, orthogonal ("where did this come from") axis
alongside InstallType ("how did this reach the environment"). See
internals/handoff/library-origin-and-required-classification.md.
"""

from haybale_marketplace.library_origin import (
    LibraryOrigin,
    compute_library_origin,
    is_project_library,
)
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType
from haywire.core.marketstall.types import Haybale


def _identity(folder_path: str) -> LibraryIdentity:
    return LibraryIdentity(
        label="Test Lib",
        version="0.1.0",
        description="",
        url="",
        author="",
        author_url="",
        folder_path=folder_path,
        module_name="testlib",
        id="testlib",
    )


def _lib(install_type: InstallType, folder_path: str, distribution_name: str = "") -> LibraryInfo:
    return LibraryInfo(
        row=Haybale(name="haybale-x", version="1.0.0"),
        identity=_identity(folder_path),
        enabled=True,
        install_type=install_type,
        distribution_name=distribution_name,
    )


class TestIsProtected:
    def test_framework_is_protected(self):
        assert LibraryOrigin.FRAMEWORK.is_protected is True

    def test_project_local_is_protected(self):
        assert LibraryOrigin.PROJECT_LOCAL.is_protected is True

    def test_pypi_is_not_protected(self):
        assert LibraryOrigin.PYPI.is_protected is False

    def test_git_is_not_protected(self):
        assert LibraryOrigin.GIT.is_protected is False

    def test_unknown_is_not_protected(self):
        # Deliberate: we don't know how this library got here, so we don't
        # newly restrict a working disable/uninstall path over an absence
        # of information. See spec's non-goals.
        assert LibraryOrigin.UNKNOWN.is_protected is False

    def test_exactly_two_members_are_protected(self):
        # Guards against a new LibraryOrigin member silently defaulting to
        # protected (or not) without an explicit decision.
        protected = [o for o in LibraryOrigin if o.is_protected]
        assert set(protected) == {LibraryOrigin.FRAMEWORK, LibraryOrigin.PROJECT_LOCAL}


class TestIsProjectLibrary:
    def test_true_when_folder_path_under_workspace_barn(self, tmp_path):
        workspace = tmp_path / "myproject"
        (workspace / "barn" / "haybale-foo").mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"))
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is True

    def test_false_when_folder_path_outside_workspace_barn(self, tmp_path):
        workspace = tmp_path / "myproject"
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other))
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is False

    def test_false_when_marketplace_path_is_none(self):
        lib = _lib(InstallType.EDITABLE, "/anywhere/haybale-foo")
        assert is_project_library(lib, None) is False

    def test_false_when_folder_path_is_empty(self, tmp_path):
        # LibraryIdentity.folder_path is typed str, not str | None — an
        # absent folder path is represented as "", which is_project_library's
        # `not lib.identity.folder_path` check treats the same as None.
        lib = LibraryInfo(
            row=Haybale(name="haybale-x", version="1.0.0"),
            identity=_identity(""),
            enabled=True,
            install_type=InstallType.EDITABLE,
            distribution_name="",
        )
        marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
        assert is_project_library(lib, marketplace_path) is False


class TestComputeLibraryOrigin:
    def test_folder_mechanism_is_framework_origin(self, tmp_path):
        # Rule 1: FOLDER implies FRAMEWORK directly, no path analysis.
        lib = _lib(InstallType.FOLDER, "/anywhere/builtin")
        marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
        assert compute_library_origin(lib, marketplace_path, catalog_entry=None) is LibraryOrigin.FRAMEWORK

    def test_path_under_barn_is_project_local(self, tmp_path):
        # Rule 2: takes priority over any catalog entry.
        workspace = tmp_path / "myproject"
        (workspace / "barn" / "haybale-foo").mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"), "haybale-foo")
        marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="pypi")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.PROJECT_LOCAL

    def test_catalog_entry_source_pypi(self, tmp_path):
        # Rule 3: outside barn, with a catalog row.
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other), "haybale-foo")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="pypi")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.PYPI

    def test_catalog_entry_source_git(self, tmp_path):
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.REGULAR, str(other), "haybale-foo")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        catalog_entry = Haybale(name="haybale-foo", version="1.0.0", source="git")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=catalog_entry)
        assert origin is LibraryOrigin.GIT

    def test_no_catalog_entry_is_unknown(self, tmp_path):
        # Rule 4: bare `pip install -e` outside the marketplace flow — no
        # catalog row. Honest unknown, never guessed from mechanism.
        other = tmp_path / "somewhere-else" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.EDITABLE, str(other), "")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
        assert origin is LibraryOrigin.UNKNOWN

    def test_regular_no_catalog_entry_is_unknown(self, tmp_path):
        other = tmp_path / "site-packages" / "haybale-foo"
        other.mkdir(parents=True)
        lib = _lib(InstallType.REGULAR, str(other), "")
        marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
        origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
        assert origin is LibraryOrigin.UNKNOWN
