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


def _report(repo: Path):
    """Run preconditions against a real SharePipeline over *repo*.

    *repo* is a plain tmp directory, not a git repo — `git status` fails there
    rather than reporting dirt, so the run falls through to the per-library
    loop, which is what these tests are about. Assertions therefore filter for
    the path failure among whatever comes back rather than expecting `ok`.
    """
    from haywire.core.publishing.pipeline.pipeline import SharePipeline

    return SharePipeline(repo).check_preconditions()


def test_an_existing_path_passes(repo: Path) -> None:
    lib = repo / "barn" / "haybale-demo"
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")
    (lib / "tests").mkdir()

    assert [f for f in _report(repo).failures if "does not exist" in f.message] == []


def test_a_missing_examples_path_fails_with_a_repairable_fault(repo: Path) -> None:
    lib = repo / "barn" / "haybale-demo"
    (lib / "tests").mkdir()  # only tests/ exists

    failure = next(f for f in _report(repo).failures if "examples_path" in f.message)
    assert failure.kind == "act"
    assert failure.fix_id == "clear_examples_path"
    assert failure.lib_dir == "barn/haybale-demo"
    assert "examples/OVERVIEW.md" in failure.message


def test_a_missing_tests_path_fails(repo: Path) -> None:
    lib = repo / "barn" / "haybale-demo"
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")

    failure = next(f for f in _report(repo).failures if "tests_path" in f.message)
    assert failure.fix_id == "clear_tests_path"
    assert failure.fix_label == "Clear tests_path"


def test_an_undeclared_path_is_not_checked(tmp_path: Path) -> None:
    """Absent means 'no examples' — a complete answer needing no check."""
    lib = tmp_path / "barn" / "haybale-bare"
    (lib / "haybale_bare").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-bare"\nversion = "0.1.0"\n')
    (lib / "haybale_bare" / "__init__.py").write_text(
        '@library(id="bare", label="Bare")\nclass Library: pass\n'
    )

    assert [f for f in _report(tmp_path).failures if "does not exist" in f.message] == []


def test_the_remedy_names_both_ways_out(repo: Path) -> None:
    """The user can clear the declaration or repoint it on the edit screen."""
    failure = next(f for f in _report(repo).failures if "examples_path" in f.message)
    assert "edit" in failure.remedy.lower()


def test_the_fix_makes_preflight_pass(repo: Path) -> None:
    """End-to-end: the offered repair actually clears the fault."""
    from haywire.core.publishing.pipeline.pipeline import SharePipeline

    (repo / "barn" / "haybale-demo" / "tests").mkdir()
    pipeline = SharePipeline(repo)
    failure = next(f for f in pipeline.check_preconditions().failures if "examples_path" in f.message)

    assert failure.fix_id is not None
    assert failure.lib_dir is not None
    pipeline.apply_precondition_fix(failure.fix_id, lib_dir=failure.lib_dir)

    remaining = pipeline.check_preconditions().failures
    assert [f for f in remaining if "examples_path" in f.message] == []
