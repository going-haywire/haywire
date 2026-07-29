import subprocess
from pathlib import Path

from haywire_studio.share import _build_entry_for_library


def _init_repo_with_lib(tmp_path: Path) -> Path:
    lib = tmp_path / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "haybale_demo" / "__init__.py").write_text("")
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-demo"\nversion = "1.0.0"\n')
    (lib / "examples").mkdir()
    (lib / "examples" / "demo.haywire").write_text("{}")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/me/repo.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    return lib


def test_examples_url_emitted_when_folder_has_graphs(tmp_path):
    lib = _init_repo_with_lib(tmp_path)
    entry = _build_entry_for_library(lib)
    assert entry is not None
    assert entry["examples_url"].endswith("/examples/")
    assert "raw.githubusercontent.com" in entry["examples_url"]
    # No tests/ folder -> no tests_url key (empty omitted by to_dict).
    assert "tests_url" not in entry


def test_no_examples_url_when_folder_absent(tmp_path):
    lib = _init_repo_with_lib(tmp_path)
    (lib / "examples" / "demo.haywire").unlink()  # now empty
    entry = _build_entry_for_library(lib)
    assert "examples_url" not in entry
