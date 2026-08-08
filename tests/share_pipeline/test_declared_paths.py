"""A declared examples_path/tests_path must exist, or the publish is a lie.

Rows are tag-pinned: a path pointing at nothing cannot be corrected without
cutting another release, so the fault is caught at preflight rather than
discovered by a consumer.
"""

from pathlib import Path

import pytest

from haywire.core.publishing.pipeline.fixes import _PRECONDITION_FIXES

DECORATOR = """from haywire.core.library.decorator import library


@library(
    id="demo",
    label="Demo",
    examples_path="examples/OVERVIEW.md",
    tests_path="tests/",
    file_watcher=True,
)
class Library:
    pass
"""


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-demo"\nversion = "0.1.0"\n')
    (lib / "haybale_demo" / "__init__.py").write_text(DECORATOR)
    return tmp_path


class _FakePipeline:
    """Enough SharePipeline for a fix handler: a root and a record() sink."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.recorded: list[Path] = []

    def record(self, paths: list[Path]) -> None:
        self.recorded.extend(paths)


def test_both_clearing_fixes_are_registered() -> None:
    assert "clear_examples_path" in _PRECONDITION_FIXES
    assert "clear_tests_path" in _PRECONDITION_FIXES


def test_clear_examples_path_removes_only_that_kwarg(repo: Path) -> None:
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")

    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert "examples_path" not in source
    assert 'tests_path="tests/"' in source
    assert 'id="demo"' in source
    assert "file_watcher=True" in source


def test_clear_tests_path_removes_only_that_kwarg(repo: Path) -> None:
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_tests_path"](pipeline, lib_dir="barn/haybale-demo")

    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert "tests_path" not in source
    assert 'examples_path="examples/OVERVIEW.md"' in source


def test_clearing_the_last_kwarg_before_the_paren(tmp_path: Path) -> None:
    """The regex must consume exactly one line including its terminator — a
    kwarg written last, with `)` on the next line, is where an over-greedy
    trailing-newline group would eat the closing paren."""
    lib = tmp_path / "barn" / "haybale-last"
    (lib / "haybale_last").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-last"\nversion = "0.1.0"\n')
    (lib / "haybale_last" / "__init__.py").write_text(
        "from haywire.core.library.decorator import library\n\n\n"
        "@library(\n"
        '    id="last",\n'
        '    tests_path="tests/",\n'
        ")\n"
        "class Library:\n"
        "    pass\n"
    )

    _PRECONDITION_FIXES["clear_tests_path"](_FakePipeline(tmp_path), lib_dir="barn/haybale-last")

    source = (lib / "haybale_last" / "__init__.py").read_text()
    assert "tests_path" not in source
    assert ")\nclass Library:" in source


def test_the_fix_records_the_file_it_touched(repo: Path) -> None:
    """SharePipeline.record drives the rollback set; an unrecorded write is
    a write the revert cannot undo."""
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    assert pipeline.recorded == [repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py"]


def test_the_result_still_parses(repo: Path) -> None:
    """A fix that leaves the decorator unreadable is worse than the fault."""
    from haywire.core.publishing.manifest.decorator_ast import read_decorator

    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")

    got = read_decorator(repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py")
    assert got.id == "demo"
    assert got.examples_path == ""
    assert got.tests_path == "tests/"


def test_missing_lib_dir_kwarg_raises(repo: Path) -> None:
    from haywire.core.publishing.pipeline.errors import PipelineStateError

    with pytest.raises(PipelineStateError, match="lib_dir"):
        _PRECONDITION_FIXES["clear_examples_path"](_FakePipeline(repo))


def test_clearing_an_absent_kwarg_is_a_no_op(repo: Path) -> None:
    """Idempotent: the user may click the fix twice, or the path may already
    have been cleared on the edit screen."""
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    before = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    assert (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text() == before
