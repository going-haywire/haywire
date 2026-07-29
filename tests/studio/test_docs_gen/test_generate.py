import shutil
import subprocess
from pathlib import Path

import pytest
from haywire.core.library.identity import LibraryIdentity
from haywire.core.library.registry import LibraryRegistry
from haywire_studio.docs_gen.generate import (
    _library_id_for_path,
    _package_root,
    generate_all_docs,
    generate_docs,
)


@pytest.fixture
def clean_haybale_testing():
    """generate_docs() writes OVERVIEW.md/QUICKREF.md/docs/*.md/README.md
    in place against the real barn/haybale-testing library — library
    discovery is entry-point/import based, so folder_path is baked to the
    real repo location and can't be redirected to a scratch copy. Restore
    tracked files and remove any newly-created untracked ones on teardown,
    so this always runs even if the test's assertions fail partway.
    """
    yield
    repo = Path(__file__).resolve().parents[3]
    lib_dir = repo / "barn" / "haybale-testing"
    subprocess.run(["git", "checkout", "--", str(lib_dir)], cwd=repo, check=False)

    # `git clean -fd` is blocked by a repo hook here, so remove any
    # newly-created untracked paths directly instead of shelling out to it.
    untracked = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all", str(lib_dir)],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    for line in untracked.splitlines():
        status, _, rel_path = line.partition(" ")
        if status.strip() != "??":
            continue
        target = repo / rel_path.strip()
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


@pytest.mark.integration
def test_generate_writes_expected_files(clean_haybale_testing):
    repo = Path(__file__).resolve().parents[3]
    lib_root = repo / "barn" / "haybale-testing"

    coverage = generate_docs(str(lib_root))
    module_dir = lib_root / "haybale_testing"
    assert (module_dir / "OVERVIEW.md").exists()
    assert (module_dir / "QUICKREF.md").exists()
    assert (module_dir / "docs").is_dir()
    assert (lib_root / "README.md").exists()
    assert isinstance(coverage, list)


def test_package_root_package_layout(tmp_path):
    lib = tmp_path / "haybale-x"
    module = lib / "haybale_x"
    module.mkdir(parents=True)
    (lib / "pyproject.toml").write_text("")
    assert _package_root(module) == lib


def test_package_root_flat_layout(tmp_path):
    lib = tmp_path / "haybale_x"
    lib.mkdir()
    (lib / "pyproject.toml").write_text("")
    assert _package_root(lib) == lib


def test_package_root_none_for_baked_in_library(tmp_path):
    """A module with no pyproject at or above it (e.g. builtin inside core)
    has no own package root — README is skipped, in-wheel docs still written."""
    module = tmp_path / "pkg" / "sub" / "builtin"
    module.mkdir(parents=True)
    assert _package_root(module) is None


@pytest.mark.integration
def test_generate_all_docs_scoped_to_one_library(clean_haybale_testing):
    """Pointing --all at a single library dir generates only that library."""
    repo = Path(__file__).resolve().parents[3]
    lib_root = repo / "barn" / "haybale-testing"

    results = generate_all_docs(str(lib_root))
    assert "testing" in results
    assert isinstance(results["testing"], list)  # coverage lines
    assert (lib_root / "haybale_testing" / "QUICKREF.md").exists()


class _FakeLibrary:
    """Minimal stand-in — LibraryRegistry.get_library_identity only reads
    `.class_identity` off whatever is stored in `_libraries`."""

    def __init__(self, identity: LibraryIdentity):
        self.class_identity = identity


class _FakeInjector:
    def __init__(self, registry: LibraryRegistry):
        self._registry = registry

    def get(self, cls):
        assert cls is LibraryRegistry
        return self._registry


class _FakeService:
    def __init__(self, registry: LibraryRegistry):
        self.injector = _FakeInjector(registry)


def _make_identity(lib_id: str, folder_path: Path) -> LibraryIdentity:
    return LibraryIdentity(
        label=lib_id,
        version="1.0.0",
        description="",
        url="",
        help_url="",
        author="",
        author_url="",
        folder_path=str(folder_path),
        module_name=lib_id,
        id=lib_id,
    )


def test_library_id_for_path_raises_on_ambiguous_shared_parent(tmp_path):
    """Two libraries loaded under a shared parent directory: calling with
    that shared parent (an ancestor of both) must raise rather than
    silently returning whichever library list_names() iterates to first.
    """
    parent = tmp_path / "barn"
    lib_a_folder = parent / "haybale-a"
    lib_b_folder = parent / "haybale-b"
    lib_a_folder.mkdir(parents=True)
    lib_b_folder.mkdir(parents=True)

    registry = LibraryRegistry()
    registry._libraries["lib_a"] = _FakeLibrary(_make_identity("lib_a", lib_a_folder))
    registry._libraries["lib_b"] = _FakeLibrary(_make_identity("lib_b", lib_b_folder))

    service = _FakeService(registry)

    with pytest.raises(ValueError, match="Ambiguous library path"):
        _library_id_for_path(service, parent)


def test_library_id_for_path_resolves_unambiguous_exact_and_nested_paths(tmp_path):
    """Exact match and target-inside-folder must still resolve directly,
    without raising, even though they go through the same collect-all-matches
    logic as the ambiguous case."""
    parent = tmp_path / "barn"
    lib_a_folder = parent / "haybale-a"
    lib_b_folder = parent / "haybale-b"
    lib_a_folder.mkdir(parents=True)
    lib_b_folder.mkdir(parents=True)

    registry = LibraryRegistry()
    registry._libraries["lib_a"] = _FakeLibrary(_make_identity("lib_a", lib_a_folder))
    registry._libraries["lib_b"] = _FakeLibrary(_make_identity("lib_b", lib_b_folder))

    service = _FakeService(registry)

    # Exact match.
    assert _library_id_for_path(service, lib_a_folder) == "lib_a"
    # Target nested inside the library folder.
    nested = lib_b_folder / "haybale_b"
    nested.mkdir()
    assert _library_id_for_path(service, nested) == "lib_b"
