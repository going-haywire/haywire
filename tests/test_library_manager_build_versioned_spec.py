"""LibraryManager.build_versioned_spec — pins an install spec to a specific version.

The marketplace's "Update" button must pin, not pass the catalog's often-
unpinned Haybale.install_spec verbatim: with a bare (unpinned) spec, `uv pip
install` is free to resolve back to the already-installed version when the
framework-package constraints file (LibraryManager._write_constraints_file)
already pins a dependency like haywire-studio, silently reporting success
without upgrading anything. build_versioned_spec is the fix — it is what
"Install specific version" already used, and what the Update button now uses
too.
"""

from __future__ import annotations

import pytest

from haywire.core.library.haybale import Haybale

pytestmark = pytest.mark.unit


def _lib_manager_cls():
    from haybale_marketplace.library_manager import LibraryManager

    return LibraryManager


@pytest.mark.unit
def test_build_versioned_spec_pypi_pins_with_double_equals() -> None:
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(name="haybale-marketplace", version="0.0.34", source="pypi")

    assert LibraryManager.build_versioned_spec(pkg, "0.0.35") == "haybale-marketplace==0.0.35"


@pytest.mark.unit
def test_build_versioned_spec_pypi_ignores_unpinned_install_spec_field() -> None:
    """Regression: the bug was passing Haybale.install_spec (the bare, unpinned
    catalog field) straight to uv. build_versioned_spec must build the pinned
    spec from pkg.name, not read pkg.install_spec at all for pypi sources."""
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(
        name="haybale-marketplace", version="0.0.34", source="pypi", install_spec="haybale-marketplace"
    )

    spec = LibraryManager.build_versioned_spec(pkg, "0.0.35")
    assert spec == "haybale-marketplace==0.0.35"
    assert spec != pkg.install_spec


@pytest.mark.unit
def test_build_versioned_spec_git_replaces_existing_tag() -> None:
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(
        name="haybale-vision",
        version="0.3.0",
        source="git",
        install_spec="git+https://example.com/repo.git@0.3.0",
    )

    assert LibraryManager.build_versioned_spec(pkg, "0.4.0") == "git+https://example.com/repo.git@0.4.0"


@pytest.mark.unit
def test_build_versioned_spec_git_preserves_subdirectory_fragment() -> None:
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(
        name="haybale-vision",
        version="0.3.0",
        source="git",
        install_spec="git+https://example.com/repo.git@0.3.0#subdirectory=barn/haybale-vision",
    )

    assert LibraryManager.build_versioned_spec(pkg, "0.4.0") == (
        "git+https://example.com/repo.git@0.4.0#subdirectory=barn/haybale-vision"
    )


@pytest.mark.unit
def test_build_versioned_spec_git_no_prior_tag() -> None:
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(
        name="haybale-vision",
        version="0.3.0",
        source="git",
        install_spec="git+https://example.com/repo.git",
    )

    assert LibraryManager.build_versioned_spec(pkg, "0.4.0") == "git+https://example.com/repo.git@0.4.0"


@pytest.mark.unit
def test_build_versioned_spec_unknown_source_returns_install_spec_unchanged() -> None:
    LibraryManager = _lib_manager_cls()
    pkg = Haybale(name="haybale-local", version="0.1.0", source="local", install_spec="/path/to/local")

    assert LibraryManager.build_versioned_spec(pkg, "0.2.0") == "/path/to/local"
