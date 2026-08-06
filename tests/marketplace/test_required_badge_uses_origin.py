"""is_required() must produce the IDENTICAL protected set before and after
routing through LibraryOrigin.is_protected — this is a centralization
refactor, not a policy change. See Global Constraints in
docs/superpowers/plans/2026-08-06-library-origin-axis.md.
"""

from haybale_marketplace.library_origin import LibraryOrigin, compute_library_origin
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.info import LibraryInfo
from haywire.core.library.install_type import InstallType


def _lib(install_type: InstallType, folder_path: str, distribution_name: str = "") -> LibraryInfo:
    identity = LibraryIdentity(
        label="Test Lib",
        version="0.1.0",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=folder_path,
        module_name="testlib",
        id="testlib",
    )
    return LibraryInfo(
        identity=identity, enabled=True, install_type=install_type, distribution_name=distribution_name
    )


def test_folder_library_origin_is_protected(tmp_path):
    lib = _lib(InstallType.FOLDER, "/anywhere/builtin")
    marketplace_path = str(tmp_path / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is True


def test_project_local_library_origin_is_protected(tmp_path):
    workspace = tmp_path / "myproject"
    (workspace / "barn" / "haybale-foo").mkdir(parents=True)
    lib = _lib(InstallType.EDITABLE, str(workspace / "barn" / "haybale-foo"))
    marketplace_path = str(workspace / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is True


def test_ordinary_editable_library_origin_is_not_protected(tmp_path):
    # An editable install of someone else's repo, outside barn/ — must NOT
    # be protected by origin alone (it may still be Required via
    # has_dependents, but that's a separate, orthogonal reason).
    other = tmp_path / "somewhere-else" / "haybale-foo"
    other.mkdir(parents=True)
    lib = _lib(InstallType.EDITABLE, str(other))
    marketplace_path = str(tmp_path / "myproject" / ".haywire" / "marketplace.toml")
    origin = compute_library_origin(lib, marketplace_path, catalog_entry=None)
    assert origin.is_protected is False
    assert origin is LibraryOrigin.UNKNOWN
