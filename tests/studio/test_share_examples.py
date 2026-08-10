"""The producer emits repo-relative paths, not URLs.

`examples_path`/`tests_path` are author *declarations* read from haybale.toml.
The behaviour this replaced scanned <lib>/examples/ for ``*.haywire`` files and
published a URL only if it found one — which silently published nothing for an
examples folder holding anything else, and could not point at examples living
elsewhere.
"""

import subprocess
from pathlib import Path
from typing import cast

from haywire.core.marketstall import Haybale
from haywire.core.marketstall.locate import module_dir_path, resolve_row_path
from haywire.core.publishing import _build_entry_for_library

_DECORATOR = """from haywire.core.library.decorator import library


@library(id="demo", file_watcher=False)
class Library:
    pass
"""

_BASE = 'name = "haybale-demo"\nid = "demo"\nlabel = "Demo"\n'
_DECLARES_EXAMPLES = _BASE + 'examples_path = "examples/"\n'


def _init_repo_with_lib(tmp_path: Path, declared: str = _BASE) -> Path:
    lib = tmp_path / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "haybale_demo" / "__init__.py").write_text(_DECORATOR)
    (lib / "haybale_demo" / "haybale.toml").write_text(declared)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-demo"\nversion = "1.0.0"\n')
    (lib / "examples").mkdir()
    (lib / "examples" / "demo.haywire").write_text("{}")
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "t@t.test"], cwd=tmp_path, check=True, capture_output=True
    )
    subprocess.run(["git", "config", "user.name", "T"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://github.com/me/repo.git"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"], cwd=tmp_path, check=True, capture_output=True
    )
    return lib


def test_examples_path_emitted_when_declared(tmp_path):
    lib = _init_repo_with_lib(tmp_path, _DECLARES_EXAMPLES)
    entry = cast(dict, _build_entry_for_library(lib))
    assert entry is not None
    # Verbatim: examples are project-relative, so the publisher does not prefix
    # them with the library's own path.
    assert entry["examples_path"] == "examples/"
    # tests_path is undeclared -> key omitted by to_dict().
    assert "tests_path" not in entry


def test_no_examples_path_when_undeclared(tmp_path):
    """The folder existing is not a declaration — the author must say so."""
    lib = _init_repo_with_lib(tmp_path)
    entry = cast(dict, _build_entry_for_library(lib))
    assert "examples_path" not in entry


def test_the_module_dir_is_derived_from_install_spec(tmp_path):
    """It used to be stored as docs_path, which could disagree with the spec
    about which directory was published. Now it is a function of it."""
    lib = _init_repo_with_lib(tmp_path)
    entry = cast(dict, _build_entry_for_library(lib))
    row = Haybale(**entry)
    assert module_dir_path(row) == "haybale-demo/haybale_demo/"


def test_paths_carry_no_ref_and_resolve_against_install_spec(tmp_path):
    """The tag lands in install_spec ONLY; the paths resolve against it.

    A path that baked its own ref could disagree with install_spec about which
    commit was published — the whole reason rows carry coordinates.
    """
    lib = _init_repo_with_lib(tmp_path, _DECLARES_EXAMPLES)

    entry = cast(dict, _build_entry_for_library(lib, tag="v1.0.0"))

    assert entry is not None
    assert entry["install_spec"] == (
        "haybale-demo @ git+https://github.com/me/repo.git@v1.0.0#subdirectory=haybale-demo"
    )
    assert "v1.0.0" not in entry["examples_path"]

    row = Haybale(**entry)
    assert resolve_row_path(row, module_dir_path(row), form="raw") == (
        "https://raw.githubusercontent.com/me/repo/v1.0.0/haybale-demo/haybale_demo/"
    )
    assert resolve_row_path(row, row.examples_path, form="raw") == (
        "https://raw.githubusercontent.com/me/repo/v1.0.0/examples/"
    )


def test_origin_provider_is_recorded(tmp_path):
    """The publisher resolved the host to let this publish through; recording
    which kind it is means a consumer needs no local config for a self-hosted
    forge."""
    lib = _init_repo_with_lib(tmp_path)
    entry = cast(dict, _build_entry_for_library(lib))
    assert entry["origin_provider"] == "github"
