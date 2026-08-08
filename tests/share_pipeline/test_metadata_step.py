"""Plan/apply for a metadata edit.

Every field here is decorator-authored. The PEP 621 half (description, authors,
keywords, urls) is NOT editable through this path — it lives in pyproject.toml
and reaches the identity through the installed distribution, so a second copy
written here would be overwritten on the next sync.
"""

from pathlib import Path

import pytest

from haywire.core.publishing.pipeline.steps.metadata import (
    LibraryEdit,
    apply_metadata,
    plan_metadata,
    validate_edit,
)

DECORATOR = """from haywire.core.library.decorator import library


@library(
    id="demo",
    label="Demo",
    on_reload="none",
    os=["macos"],
    examples_path="examples/OVERVIEW.md",
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
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")
    # A declared path must exist for validate_edit to accept it, so the tests
    # that write tests_path="tests/" need it on disk.
    (lib / "tests").mkdir()
    return tmp_path


def test_plan_reads_current_values(repo):
    plan = plan_metadata(repo)
    assert len(plan.edits) == 1
    edit = plan.edits[0]
    assert edit.name == "haybale-demo"
    assert edit.label == "Demo"
    assert edit.on_reload == "none"
    assert edit.os == ["macos"]
    assert edit.examples_path == "examples/OVERVIEW.md"


def test_apply_writes_the_decorator(repo):
    plan = plan_metadata(repo)
    edited = [
        LibraryEdit(
            lib_dir=plan.edits[0].lib_dir,
            name="haybale-demo",
            label="Renamed",
            on_reload="restart",
            os=["linux"],
            examples_path="",
            tests_path="tests/",
        )
    ]
    written = apply_metadata(repo, edited)

    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert 'label="Renamed"' in source
    assert 'on_reload="restart"' in source
    assert "'linux'" in source or '"linux"' in source
    assert 'tests_path="tests/"' in source
    assert written


def test_apply_is_a_round_trip(repo):
    """What plan reads back after apply is what apply was given."""
    plan = plan_metadata(repo)
    edited = [
        LibraryEdit(
            lib_dir=plan.edits[0].lib_dir,
            name="haybale-demo",
            label="Round Trip",
            on_reload="refresh",
            os=["macos", "windows"],
            examples_path="examples/OVERVIEW.md",
            tests_path="",
        )
    ]
    apply_metadata(repo, edited)
    after = plan_metadata(repo).edits[0]
    assert after.label == "Round Trip"
    assert after.on_reload == "refresh"
    assert after.os == ["macos", "windows"]
    assert after.tests_path == ""


def test_apply_leaves_unedited_fields_alone(repo):
    plan = plan_metadata(repo)
    apply_metadata(repo, [plan.edits[0]])
    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert 'id="demo"' in source
    assert "file_watcher=True" in source


def test_validate_accepts_an_existing_path(repo):
    plan = plan_metadata(repo)
    assert validate_edit(plan.edits[0].lib_dir, plan.edits[0]) == []


def test_validate_rejects_a_missing_path(repo):
    plan = plan_metadata(repo)
    edit = LibraryEdit(
        lib_dir=plan.edits[0].lib_dir,
        name="haybale-demo",
        label="Demo",
        on_reload="none",
        os=[],
        examples_path="examples/GONE.md",
        tests_path="",
    )
    problems = validate_edit(edit.lib_dir, edit)
    assert problems
    assert "examples/GONE.md" in problems[0]


def test_validate_accepts_an_empty_path(repo):
    """Absent means 'no examples' — a complete answer needing no check."""
    plan = plan_metadata(repo)
    edit = LibraryEdit(
        lib_dir=plan.edits[0].lib_dir,
        name="haybale-demo",
        label="Demo",
        on_reload="none",
        os=[],
        examples_path="",
        tests_path="",
    )
    assert validate_edit(edit.lib_dir, edit) == []


def test_validate_rejects_an_unknown_reload_action(repo):
    plan = plan_metadata(repo)
    edit = LibraryEdit(
        lib_dir=plan.edits[0].lib_dir,
        name="haybale-demo",
        label="Demo",
        on_reload="explode",
        os=[],
        examples_path="",
        tests_path="",
    )
    assert validate_edit(edit.lib_dir, edit)


def test_validate_rejects_an_empty_label(repo):
    plan = plan_metadata(repo)
    edit = LibraryEdit(
        lib_dir=plan.edits[0].lib_dir,
        name="haybale-demo",
        label="   ",
        on_reload="none",
        os=[],
        examples_path="",
        tests_path="",
    )
    assert validate_edit(edit.lib_dir, edit)


def test_apply_validates_before_writing_anything(repo):
    """One bad edit in the batch leaves every file untouched.

    A half-applied batch is the failure this whole change exists to prevent:
    two libraries disagreeing about what was published.
    """
    plan = plan_metadata(repo)
    before = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    bad = LibraryEdit(
        lib_dir=plan.edits[0].lib_dir,
        name="haybale-demo",
        label="Demo",
        on_reload="explode",
        os=[],
        examples_path="",
        tests_path="",
    )
    with pytest.raises(ValueError, match="on_reload"):
        apply_metadata(repo, [bad])
    assert (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text() == before
