# Metadata Editing Moves Into Share Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the marketplace Edit dialog. Library metadata is edited on a new
`edit` screen in the Share wizard, between `preflight` and `review`, where the
sync-and-reload that makes an edit visible already exists.

**Architecture:** A fourth acting screen in `ShareFlow`. It collects changes into
pipeline state and writes them in `publish` alongside the version bump, per the
stepper's plan/apply rule. Declared paths validate inline so `preflight` stays a
single pass. `_overview_edit_dialog.py` and `LibraryManager.update_library_identity`
are deleted outright.

**Tech Stack:** Python 3.12, NiceGUI, `haywire.ui.components.stepper`, tomlkit
(`haywire.core.tomlio.edit_toml`), pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- **Only the last step may write** (`.insights/project_stepper_flows.md`). `edit`
  collects; `publish` writes. A flow abandoned before `publish` must leave the
  tree untouched — that is what makes `ShareFlow.fail`'s revert provable.
- Click handlers must **return** the coroutine, never schedule it
  (`.insights/project_stepper_flows.md`).
- Editing is **heap-only**. Share operates on a project's `barn/*`; an installed
  library's metadata is not editable at all.

## Predecessors

All landed:

- [foundation](2026-08-08-library-metadata-foundation.md) — `LibraryMetadata` base;
  rows carry coordinates.
- [distribution](2026-08-08-library-metadata-distribution.md) — decorator reads PEP
  621 fields from installed distribution metadata; `os`/`examples_path`/`tests_path`
  became decorator kwargs; `id` required.
- [one-reader](2026-08-08-library-metadata-one-reader.md) — `read_decorator()` is
  the single AST reader; `deps.py` deleted; both producers converged.

## Verified starting state

Confirmed on disk 2026-08-08.

**The dialog's editable surface has already shrunk to three fields.** The
distribution plan turned `description`, `authors`, `homepage_url`, `author_url`
and `tags` into read-only labels reading "(from pyproject.toml)". What remains
editable is `label`, `on_reload`, and `os`.

**`update_library_identity` (`library_manager.py:960-1020`) writes three places:**

| target | fields |
| --- | --- |
| decorator, via `_set_decorator_str_field`/`_set_decorator_list_field` | `label`, `on_reload`, `dependencies` |
| `pyproject.toml`, via `_apply_os_to_pyproject` | `[tool.haywire].os` |
| `.haywire/marketplace.toml`, via `edit_toml` | heap `label`, `description` |

**A live bug this plan fixes.** `os` became a *decorator kwarg* in the
distribution plan, but the dialog still reads it with `read_os_from_pyproject`
(`_overview_edit_dialog.py:35`) and writes it with `_apply_os_to_pyproject`
(`library_manager.py:178`) — both `[tool.haywire].os`. So editing OS in the UI
writes a key the identity never reads. The marketstall producer reads the
decorator first and only falls back to `[tool.haywire]`
(`marketstall.py:117-119`), so a UI edit silently does nothing until step 10
removes the fallback, at which point it silently reverts. Neither state is
correct.

**The decorator still writes `dependencies=`, not `linked_libraries=`**
(`library_manager.py:987`) — the shim both the decorator and `read_decorator`
carry. Step 10 rewrites the libraries; this plan must not widen that.

**`ShareFlow` shape** (`_flow/_state.py`):

- `STEPS = ("preflight", "review", "publish", "done")` in `_flow/copy.py:25`,
  with `STEP_TITLES` beside it.
- One `async def advance_from_<step>()` per non-terminal step; each sets
  `self.step` on success or calls `self.fail(exc)`.
- `advance_from_preflight` runs preconditions + drift + framework + version
  plans in threads, then sets `step = "review"`.
- `advance_from_review` is **the flow's first write** (`apply_all`, `apply_bump`).
- Panels are `panel_<step>(flow, rerender)` in `_flow/panels.py`, wired by name
  through `show_step_flow`, which raises if any `STEPS` entry lacks a panel.

**Failure posture** (`_state.py` docstring): three outcomes — preflight never
mutates; review→publish reverts a clean tree; post-commit does not revert. An
`edit` screen placed before `review` lands in the first, so an abandoned edit
needs no rollback.

## Out of scope

- **step 6: declared-path preconditions.** A declared path that does not exist
  fails `check_preconditions` with a `fix_id`. This plan validates the two path
  fields **inline on the edit screen** so `preflight` stays a single pass; step 6
  adds the preflight-side check for paths authored outside the wizard.
- **step 10: author-facing migration.** The 10 barn libraries, the `haywire init`
  scaffold, `haywire rename`, docs, and removing the `dependencies=` shim and the
  `[tool.haywire].os` fallback.

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/metadata.py` | **new** — plan/apply for a metadata edit |
| `packages/haywire-core/src/haywire/core/publishing/pipeline/pipeline.py` | `plan_metadata()` / `apply_metadata()` |
| `barn/haybale-share/haybale_share/_flow/copy.py` | `STEPS` gains `edit`; titles |
| `barn/haybale-share/haybale_share/_flow/_state.py` | `advance_from_edit`; edit state |
| `barn/haybale-share/haybale_share/_flow/panels.py` | `panel_edit` |
| `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py` | **deleted** |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py` | `update_library_identity` + `_apply_os_to_pyproject` deleted |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | Edit button → Share entry point |
| `tests/share_pipeline/test_metadata_step.py` | **new** |
| `tests/ui/components/test_stepper_flow.py` | five-step flow |

---

### Task 1: The pipeline's metadata step

Plan/apply, no UI. The write must be atomic across two files: a half-applied edit
leaves the decorator and `pyproject.toml` disagreeing, which is the failure the
whole ADR exists to prevent.

**Files:**

- Create: `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/metadata.py`
- Modify: `packages/haywire-core/src/haywire/core/publishing/pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_metadata_step.py` (create)

**Interfaces:**

- Consumes: `read_decorator(init_py) -> DecoratorFields`;
  `decorator_io._set_decorator_str_field` / `_set_decorator_list_field`;
  `haywire.core.tomlio.edit_toml`; `barn_library_dirs(repo_root)`;
  `find_module_dir(lib_dir)`.
- Produces:
  - `LibraryEdit` — frozen dataclass: `lib_dir: Path`, `name: str`, `label: str`,
    `on_reload: str`, `os: list[str]`, `examples_path: str`, `tests_path: str`.
  - `MetadataPlan` — frozen dataclass: `edits: list[LibraryEdit]`.
  - `plan_metadata(repo_root) -> MetadataPlan` — current values, one per barn library.
  - `apply_metadata(repo_root, edits) -> list[Path]` — writes; returns files touched.
  - `validate_edit(lib_dir, edit) -> list[str]` — human-readable problems, empty when clean.
  - `SharePipeline.plan_metadata()` / `.apply_metadata(edits)`.

- [x] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_metadata_step.py`:

```python
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

DECORATOR = '''from haywire.core.library.decorator import library


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
'''


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    lib = tmp_path / "barn" / "haybale-demo"
    (lib / "haybale_demo").mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        '[project]\nname = "haybale-demo"\nversion = "0.1.0"\n'
    )
    (lib / "haybale_demo" / "__init__.py").write_text(DECORATOR)
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")
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
    with pytest.raises(ValueError):
        apply_metadata(repo, [bad])
    assert (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text() == before
```

- [x] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_metadata_step.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named
'haywire.core.publishing.pipeline.steps.metadata'`.

- [x] **Step 3: Write the step module**

Create `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/metadata.py`:

```python
"""Read and rewrite the decorator-authored half of a library's metadata.

Only fields the decorator owns are editable here. The PEP 621 half — version,
description, authors, keywords, urls — lives in ``pyproject.toml`` and reaches
the identity through the installed distribution, so writing a second copy would
be overwritten by the next ``uv sync``. That asymmetry is the point of ADR 0024,
not an omission.

Writes happen in the pipeline's ``publish`` step. The whole batch is validated
before any file is touched: a partially applied edit leaves two libraries
disagreeing about what was published, which is exactly the split this change
removes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from haywire.core.library.decorator_io import (
    _set_decorator_list_field,
    _set_decorator_str_field,
)
from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.reload import LibraryReloadAction
from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.manifest.decorator_ast import read_decorator
from haywire.core.publishing.manifest.os_field import _DECLARABLE_OS_VALUES


@dataclass(frozen=True)
class LibraryEdit:
    """One library's editable metadata, as shown and as submitted."""

    lib_dir: Path
    name: str
    label: str
    on_reload: str
    os: list[str] = field(default_factory=list)
    examples_path: str = ""
    tests_path: str = ""


@dataclass(frozen=True)
class MetadataPlan:
    """Current values for every barn library, one entry each."""

    edits: list[LibraryEdit] = field(default_factory=list)


def _init_py(lib_dir: Path) -> Path | None:
    module_dir = find_module_dir(lib_dir)
    return (module_dir / "__init__.py") if module_dir else None


def plan_metadata(repo_root: Path) -> MetadataPlan:
    """Read each barn library's current editable metadata.

    A library whose module directory or ``__init__.py`` cannot be found is
    skipped rather than reported empty — an empty form would invite the user to
    "fix" it by overwriting a file the wizard never read.
    """
    edits: list[LibraryEdit] = []
    for lib_dir in barn_library_dirs(repo_root):
        init_py = _init_py(lib_dir)
        if init_py is None or not init_py.is_file():
            continue
        decorator = read_decorator(init_py)
        edits.append(
            LibraryEdit(
                lib_dir=lib_dir,
                name=lib_dir.name,
                label=decorator.label,
                on_reload=decorator.on_reload,
                os=list(decorator.os),
                examples_path=decorator.examples_path,
                tests_path=decorator.tests_path,
            )
        )
    return MetadataPlan(edits=edits)


def validate_edit(lib_dir: Path, edit: LibraryEdit) -> list[str]:
    """Everything wrong with *edit*, in human-readable form. Empty when clean.

    Declared paths are checked against the working tree: an empty path means
    "no examples", which needs no check, but a declared one asserts a file the
    publish would otherwise contradict. Rows are tag-pinned, so a wrong path is
    unfixable without cutting another release.
    """
    problems: list[str] = []

    if not edit.label.strip():
        problems.append(f"{edit.name}: label cannot be empty")

    try:
        LibraryReloadAction(edit.on_reload.strip().lower())
    except ValueError:
        problems.append(
            f"{edit.name}: on_reload must be none, refresh or restart — got {edit.on_reload!r}"
        )

    for value in edit.os:
        if value not in _DECLARABLE_OS_VALUES:
            problems.append(f"{edit.name}: unknown platform {value!r}")

    for label, declared in (("examples_path", edit.examples_path), ("tests_path", edit.tests_path)):
        if declared and not (lib_dir / declared).exists():
            problems.append(f"{edit.name}: {label} {declared!r} does not exist")

    return problems


def apply_metadata(repo_root: Path, edits: list[LibraryEdit]) -> list[Path]:
    """Write every edit. Validates the whole batch first; returns files written.

    Raises :class:`ValueError` listing every problem when validation fails,
    before any file is touched.
    """
    problems: list[str] = []
    for edit in edits:
        problems.extend(validate_edit(edit.lib_dir, edit))
    if problems:
        raise ValueError("; ".join(problems))

    written: list[Path] = []
    for edit in edits:
        init_py = _init_py(edit.lib_dir)
        if init_py is None or not init_py.is_file():
            continue
        source = init_py.read_text()
        source = _set_decorator_str_field(source, "label", edit.label.strip())
        source = _set_decorator_str_field(source, "on_reload", edit.on_reload.strip().lower())
        source = _set_decorator_list_field(source, "os", list(edit.os))
        source = _set_decorator_str_field(source, "examples_path", edit.examples_path.strip())
        source = _set_decorator_str_field(source, "tests_path", edit.tests_path.strip())
        init_py.write_text(source)
        written.append(init_py)
    return written
```

- [x] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_metadata_step.py -v`

Expected: all PASS.

If `_set_decorator_str_field` inserts a field that was absent rather than
skipping it, `test_apply_is_a_round_trip`'s `tests_path == ""` assertion may fail
with an empty-string field written into the source. That is acceptable — an
empty `tests_path=""` reads the same as absent — but if the assertion trips,
prefer *removing* the field when the value is empty and add a helper to
`decorator_io` rather than weakening the test.

- [x] **Step 5: Expose it on the pipeline**

In `packages/haywire-core/src/haywire/core/publishing/pipeline/pipeline.py`, add
two methods beside the existing `plan_*`/`apply_*` pairs:

```python
    def plan_metadata(self) -> MetadataPlan:
        """Current editable metadata for every barn library."""
        return plan_metadata(self.repo_root)

    def apply_metadata(self, edits: list[LibraryEdit]) -> list[Path]:
        """Write the metadata edits. Raises ValueError if any edit is invalid."""
        return apply_metadata(self.repo_root, edits)
```

with the import:

```python
from haywire.core.publishing.pipeline.steps.metadata import (
    LibraryEdit,
    MetadataPlan,
    apply_metadata,
    plan_metadata,
)
```

Export `LibraryEdit` and `MetadataPlan` from
`packages/haywire-core/src/haywire/core/publishing/pipeline/__init__.py` alongside
the other plan dataclasses — `_flow/_state.py` imports them from there.

- [x] **Step 6: Run the pipeline suite**

```bash
uv run pytest tests/share_pipeline/ -q
```

Expected: all pass.

- [x] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-core/src/ tests/share_pipeline/
uv run ruff format --check packages/haywire-core/src/ tests/share_pipeline/
uv run mypy packages/haywire-core/src/
```

Expected: clean.

- [x] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(share): plan/apply for decorator metadata edits

No UI yet. The batch is validated before any file is written: a partially
applied edit leaves two libraries disagreeing about what was published, which
is the split ADR 0024 exists to close.

Only decorator-owned fields are editable. version/description/authors/keywords
live in pyproject.toml and reach the identity through the installed
distribution, so a copy written here would be overwritten by the next uv sync.

ADR 0024."
```

---

### Task 2: The `edit` screen

**Files:**

- Modify: `barn/haybale-share/haybale_share/_flow/copy.py:25-32`
- Modify: `barn/haybale-share/haybale_share/_flow/_state.py`
- Modify: `barn/haybale-share/haybale_share/_flow/panels.py`
- Modify: `barn/haybale-share/haybale_share/_flow/chrome.py` (panel wiring)
- Test: `tests/share_pipeline/test_edit_screen.py` (create)

**Interfaces:**

- Consumes: `SharePipeline.plan_metadata()` / `.apply_metadata(edits)` from Task 1.
- Produces:
  - `ShareFlow.metadata_plan: MetadataPlan | None`
  - `ShareFlow.metadata_edits: list[LibraryEdit]` — the working copy the form binds to
  - `ShareFlow.metadata_problems: list[str]`
  - `async ShareFlow.advance_from_edit()` — validates, sets `step = "review"`
  - `panel_edit(flow, rerender)`

- [x] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_edit_screen.py`:

```python
"""The edit screen collects; publish writes.

Placed between preflight and review: preflight's verdict is what makes the
edit safe to offer, and review's decisions (drift, framework floor, version)
must see the edited state — a linked_libraries change after review would
invalidate a decision the user just authorized.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haybale_share._flow._state import ShareFlow
from haywire.core.publishing.pipeline import LibraryEdit, MetadataPlan


def _flow(**pipeline_attrs) -> ShareFlow:
    pipeline = MagicMock()
    for key, value in pipeline_attrs.items():
        setattr(pipeline, key, value)
    return ShareFlow(pipeline=pipeline)


def test_edit_is_between_preflight_and_review():
    assert ShareFlow.STEPS == ("preflight", "edit", "review", "publish", "done")


def test_every_step_has_a_panel():
    """show_step_flow raises when a STEPS entry has no panel."""
    from haybale_share._flow import panels

    for step in ShareFlow.STEPS:
        assert hasattr(panels, f"panel_{step}"), step


def test_preflight_advances_into_edit():
    flow = _flow()
    flow.pipeline.require_preconditions.return_value = MagicMock()
    flow.pipeline.plan_metadata.return_value = MetadataPlan(edits=[])
    import asyncio

    asyncio.run(flow.advance_from_preflight())
    assert flow.step == "edit"


def test_edit_loads_the_plan_at_preflight_time():
    """The form must be populated when the screen renders, not on first click."""
    edit = LibraryEdit(
        lib_dir=Path("/tmp/x"), name="haybale-x", label="X", on_reload="none"
    )
    flow = _flow()
    flow.pipeline.require_preconditions.return_value = MagicMock()
    flow.pipeline.plan_metadata.return_value = MetadataPlan(edits=[edit])
    import asyncio

    asyncio.run(flow.advance_from_preflight())
    assert flow.metadata_edits == [edit]


def test_advance_from_edit_validates_and_blocks():
    flow = _flow()
    flow.step = "edit"
    flow.metadata_edits = [
        LibraryEdit(lib_dir=Path("/tmp/x"), name="haybale-x", label="", on_reload="none")
    ]
    flow.pipeline.validate_metadata.return_value = ["haybale-x: label cannot be empty"]
    import asyncio

    asyncio.run(flow.advance_from_edit())
    assert flow.step == "edit"
    assert flow.metadata_problems


def test_advance_from_edit_passes_to_review_when_clean():
    flow = _flow()
    flow.step = "edit"
    flow.metadata_edits = []
    flow.pipeline.validate_metadata.return_value = []
    flow.pipeline.check_drift.return_value = MagicMock()
    flow.pipeline.plan_framework.return_value = MagicMock()
    flow.pipeline.plan_version.return_value = MagicMock()
    import asyncio

    asyncio.run(flow.advance_from_edit())
    assert flow.step == "review"
    assert flow.metadata_problems == []


def test_edit_writes_nothing():
    """Abandoning the flow here must leave the tree untouched — that is what
    makes ShareFlow.fail's revert a narrow, provable operation."""
    flow = _flow()
    flow.step = "edit"
    flow.metadata_edits = []
    flow.pipeline.validate_metadata.return_value = []
    flow.pipeline.check_drift.return_value = MagicMock()
    flow.pipeline.plan_framework.return_value = MagicMock()
    flow.pipeline.plan_version.return_value = MagicMock()
    import asyncio

    asyncio.run(flow.advance_from_edit())
    flow.pipeline.apply_metadata.assert_not_called()


def test_publish_applies_the_edits():
    flow = _flow()
    flow.step = "review"
    edit = LibraryEdit(lib_dir=Path("/tmp/x"), name="haybale-x", label="X", on_reload="none")
    flow.metadata_edits = [edit]
    flow.pipeline.apply_bump.return_value = MagicMock(lock_warning=None)
    import asyncio

    asyncio.run(flow.advance_from_review(MagicMock(), version_spec="0.2.0"))
    flow.pipeline.apply_metadata.assert_called_once_with([edit])
```

- [x] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_edit_screen.py -v`

Expected: FAIL — `STEPS` has four entries, `panel_edit` and `advance_from_edit`
do not exist.

- [x] **Step 3: Add the step**

In `barn/haybale-share/haybale_share/_flow/copy.py`:

```python
STEPS = ("preflight", "edit", "review", "publish", "done")

STEP_TITLES = {
    "preflight": "Check the project",
    "edit": "Edit library details",
    "review": "Review and decide",
    "publish": "Publish",
    "done": "Published",
}
```

Extend the comment above `STEPS` to say why `edit` sits where it does:

```python
#: `edit` sits between them because `review` authorizes decisions the pipeline
#: *computed* — drift, framework floor, version — while `edit` is free-text
#: authoring with no computed proposal. Mixing "approve this bump" with "type a
#: new description" would muddy what the confirm button means. Placing it first
#: also means drift detection and the marketstall generator see the edited
#: state; editing afterwards could invalidate a decision just authorized.
```

- [x] **Step 4: Add flow state and the advance method**

In `_flow/_state.py`, add to `ShareFlow.__init__`:

```python
        self.metadata_plan: MetadataPlan | None = None
        #: The working copy the edit form binds to. Written in `publish`,
        #: never here — an abandoned flow must leave the tree untouched.
        self.metadata_edits: list[LibraryEdit] = []
        self.metadata_problems: list[str] = []
```

At the end of `advance_from_preflight`, load the plan and go to `edit` instead of
`review`. The drift/framework/version planning **moves to `advance_from_edit`**,
so `review` still has everything it needs and now sees the edited state:

```python
        self.retry()
        try:
            self.preconditions_report = await asyncio.to_thread(self.pipeline.require_preconditions)
            self.metadata_plan = await asyncio.to_thread(self.pipeline.plan_metadata)
        except ShareError as exc:
            self.fail(exc)
            return
        self.metadata_edits = list(self.metadata_plan.edits)
        self.step = "edit"

    async def advance_from_edit(self) -> None:
        """Validate the edits, then plan everything `review` decides.

        Writes nothing: the edits are applied in `publish` alongside the bump,
        per the stepper's rule that only the last step may write. Planning moves
        here from preflight so drift and the version plan see the edited state —
        a linked_libraries change after review would invalidate a decision the
        user had just authorized.
        """
        self.retry()
        self.metadata_problems = self.pipeline.validate_metadata(self.metadata_edits)
        if self.metadata_problems:
            return
        try:
            self.drift_report = await asyncio.to_thread(self.pipeline.check_drift)
            self.framework_plan = await asyncio.to_thread(self.pipeline.plan_framework)
            self.version_plan = await asyncio.to_thread(self.pipeline.plan_version)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "review"
```

Add `validate_metadata` to `SharePipeline` beside the Task 1 methods:

```python
    def validate_metadata(self, edits: list[LibraryEdit]) -> list[str]:
        """Every problem across the batch, human-readable. Empty when clean."""
        problems: list[str] = []
        for edit in edits:
            problems.extend(validate_edit(edit.lib_dir, edit))
        return problems
```

In `advance_from_review`, apply the edits before the bump:

```python
        try:
            if self.metadata_edits:
                await asyncio.to_thread(self.pipeline.apply_metadata, self.metadata_edits)
            await asyncio.to_thread(self.pipeline.apply_all, decisions)
            result = await asyncio.to_thread(self.pipeline.apply_bump, version_spec)
```

Import `LibraryEdit` and `MetadataPlan` from `haywire.core.publishing.pipeline`.

- [x] **Step 5: Write the panel**

In `_flow/panels.py`, add `panel_edit` following `panel_review`'s shape — read it
first for the section/field idiom and the confirm-button wiring:

```python
def panel_edit(flow: ShareFlow, rerender: Callable[[], None]) -> None:
    """Per-library metadata form. Collects only; `publish` writes.

    Only decorator-authored fields appear. version/description/authors/keywords
    come from pyproject.toml through the installed distribution, so editing them
    here would write a copy the next sync overwrites — they are shown read-only
    on the library detail view instead.
    """
    if not flow.metadata_edits:
        ui.label("No libraries to edit.").classes("text-sm hw-text-dim")
    for index, edit in enumerate(flow.metadata_edits):

        def _update(i: int, **changes) -> None:
            flow.metadata_edits[i] = replace(flow.metadata_edits[i], **changes)

        with hui.section(edit.name):
            hui.input_field(
                label="Label",
                value=edit.label,
                on_change=lambda e, i=index: _update(i, label=e.value),
            )
            hui.select_field(
                options={
                    LibraryReloadAction.NONE.value: "No special action — hot-reloadable",
                    LibraryReloadAction.REFRESH.value: "Reload the page — Vue or JS resources",
                    LibraryReloadAction.RESTART.value: "Restart the Studio — C extensions",
                },
                value=edit.on_reload,
                on_change=lambda e, i=index: _update(i, on_reload=e.value),
            ).classes("w-full")
            hui.select_field(
                options={"macos": "macOS", "windows": "Windows", "linux": "Linux"},
                value=list(edit.os),
                multiple=True,
                label="Supported OS (empty = all platforms)",
            ).classes("w-full").props("use-chips").on_value_change(
                lambda e, i=index: _update(i, os=list(e.value or []))
            )
            hui.input_field(
                label="Examples path (relative to the library)",
                value=edit.examples_path,
                on_change=lambda e, i=index: _update(i, examples_path=e.value),
            )
            hui.input_field(
                label="Tests path",
                value=edit.tests_path,
                on_change=lambda e, i=index: _update(i, tests_path=e.value),
            )

    for problem in flow.metadata_problems:
        ui.label(problem).classes("text-sm hw-text-danger")

    # RETURN the coroutine — scheduling it breaks the stepper's advance
    # contract (.insights/project_stepper_flows.md).
    hui.dialog_actions(
        on_confirm=lambda: busy_advance(rerender, flow.advance_from_edit),
        confirm_label="Continue",
    )
```

Match the file's existing imports and helpers — `replace` from `dataclasses`,
`LibraryReloadAction`, and whatever `busy_advance` wrapper `panel_review` uses.
If `hui.section` does not exist, use the same grouping element `panel_review`
uses.

- [x] **Step 6: Wire the panel**

`show_step_flow` raises when a `STEPS` entry has no panel, so find the panels dict
(likely in `_flow/chrome.py`) and add `"edit": panel_edit`.

- [x] **Step 7: Run the tests**

```bash
uv run pytest tests/share_pipeline/ -q
```

Expected: all pass. Existing tests asserting the four-step `STEPS` tuple or
`advance_from_preflight` landing on `"review"` must be updated — those are the
behavior this task changes.

- [x] **Step 8: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task2.log | head -20
```

Expected: `exit=0`, no FAILED lines.

- [x] **Step 9: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [x] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(share): edit library metadata inside the wizard

A fourth acting screen between preflight and review. It collects; publish
writes, per the stepper rule that only the last step may write — so a flow
abandoned here leaves the tree untouched, which is what makes fail()'s revert
provable.

Drift, framework and version planning move from preflight to advance_from_edit
so review sees the edited state; a linked_libraries change after review would
otherwise invalidate a decision the user had just authorized.

Declared paths validate inline rather than re-running preflight, keeping it a
single pass.

ADR 0024."
```

---

### Task 3: Delete the marketplace Edit dialog

**Files:**

- Delete: `barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/library_manager.py` (delete
  `update_library_identity` and `_apply_os_to_pyproject`)
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py`
- Delete or rewrite: tests covering the dialog

**Interfaces:**

- Consumes: nothing new.
- Produces: `update_library_identity` and `_apply_os_to_pyproject` cease to exist.

- [x] **Step 1: Find every reference**

```bash
grep -rn "update_library_identity\|_overview_edit_dialog\|build_edit_dialog\|_apply_os_to_pyproject\|read_os_from_pyproject" --include="*.py" packages/ barn/ tests/
```

Record the list. Expect: the dialog module, `library_manager.py`, the overview
editor's Edit button, and their tests.

- [x] **Step 2: Delete the dialog and the writer**

```bash
rm barn/haybale-marketplace/haybale_marketplace/editors/_overview_edit_dialog.py
```

In `library_manager.py`, delete `update_library_identity` (~lines 960-1020) and
`_apply_os_to_pyproject` (~lines 178-210), plus imports left unused —
`_set_decorator_str_field`, `_set_decorator_list_field`, `_DECLARABLE_OS_VALUES`,
and `LibraryReloadAction` if nothing else in the file uses them. Check each with
grep before removing.

This also removes the **live bug** noted in the verified state: the dialog wrote
`[tool.haywire].os` while the decorator owns `os`, so an OS edit made in the UI
was never read back.

- [x] **Step 3: Repoint the overview editor's Edit button**

In `library_overview_editor.py`, replace the Edit button's handler. The library
detail view becomes read-only for metadata, which fits its role.

Find the button (grep for `build_edit_dialog`) and either remove it, or — if the
editor already has a way to open the Share flow — relabel it "Share…". If it does
not, remove the button and leave a tooltip-free read-only view; adding a
cross-library entry point is not this plan's scope.

Delete `_do_update_identity` / `_offer_restart` and any helper left with no
caller. Verify with grep before each removal.

- [x] **Step 4: Update or delete the dialog's tests**

```bash
grep -rln "update_library_identity\|build_edit_dialog\|read_os_from_pyproject" tests/
```

Tests exercising the dialog's behavior are testing something that no longer
exists — delete them. Tests exercising `_set_decorator_str_field` directly (the
quote-bug regression from the foundation plan) test `decorator_io`, which
survives: keep those, and move them to a `tests/core/test_library/` path if they
currently live under `tests/marketplace/`.

- [x] **Step 5: Verify nothing dangles**

```bash
grep -rn "update_library_identity\|_overview_edit_dialog\|build_edit_dialog\|_apply_os_to_pyproject\|read_os_from_pyproject" --include="*.py" packages/ barn/ tests/
```

Expected: no output.

- [x] **Step 6: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task3.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task3.log | head -20
```

Expected: `exit=0`, no FAILED lines.

- [x] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [x] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(marketplace)!: delete the identity Edit dialog

Metadata is edited in the Share wizard, where the sync-and-reload that makes an
edit visible already exists. A standalone dialog would have had to invent one.

Fixes a live bug on the way out: the dialog read and wrote [tool.haywire].os
while the decorator has owned `os` since the distribution plan, so an OS edit
made in the UI was written somewhere the identity never reads.

The library detail view is now read-only for metadata, which fits its role.
Editing is heap-only — an author cannot edit someone else's published library,
and the dialog pretending otherwise was a bug.

BREAKING CHANGE: LibraryManager.update_library_identity is removed.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration **step 8**. After it lands,
metadata has one editing surface and one source per field, which is the ADR's
end state for authoring.

**Deviation from the design doc, flagged.** The consolidation doc places
`edit` between `preflight` and `review` and says nothing about where the *planning*
runs. Task 2 moves drift/framework/version planning out of `advance_from_preflight`
into `advance_from_edit`. Without that move, `review` would show decisions
computed against the pre-edit tree — a `linked_libraries` change would produce a
drift report the user then authorizes, describing a state that no longer exists.
The alternative (re-planning on leaving `edit`) is the same work in a worse place.

**What this plan does not do.** It edits only decorator-authored fields.
`description`, `authors`, `keywords` and the URLs are pyproject-owned and reach
the identity through the installed distribution; a form writing them would be
overwritten by the next `uv sync`. Editing those means editing `pyproject.toml`
and re-syncing — worth adding later, but it is a different mechanism and would
double this plan's size.

**Type consistency.** `LibraryEdit` is frozen; the panel updates the working copy
with `dataclasses.replace`, never mutation. `plan_metadata`/`apply_metadata`/
`validate_edit` take and return the same `LibraryEdit`. `MetadataPlan.edits` and
`ShareFlow.metadata_edits` are both `list[LibraryEdit]`; the flow copies the plan's
list rather than aliasing it.

**Three risks worth naming.**

1. **`_set_decorator_str_field` inserts absent fields.** Setting `tests_path=""`
   on a library that never declared it writes `tests_path=""` into the source
   rather than leaving it out. Harmless (empty reads as absent) but noisy in a
   diff. Task 1 Step 4 says to add a remove-when-empty helper rather than weaken
   the round-trip test — do that if the diff noise is objectionable.
2. **The panel's `on_change` closures capture `index`.** Every lambda binds
   `i=index` explicitly for that reason; a lambda that closes over the loop
   variable instead would write every field to the last library. This is the
   `.insights/feedback_nicegui_redraw_deletes_handler_slot.md` family of bug —
   worth a manual check in the running studio, since the tests here are unit-level.
3. **Task 3 removes the Edit button without adding a Share entry point.** The
   detail view loses an affordance and the plan does not replace it, on the
   grounds that a cross-library entry point is out of scope. If that leaves the
   flow undiscoverable from the library view, add the entry point in step 10
   rather than widening this plan.

---

## Landed

All three tasks landed 2026-08-09 (`7f8ca3eb`, `c04f4cf9`, `914edc55`). Gate
green at each commit: `pytest -m "not browser and not perf"` exit=0, ruff
check + format clean, mypy clean.

Five deviations from the plan as written, each forced by the code as found:

1. **`SharePipeline.apply_metadata` routes through `self.record()`.** Every
   other apply step registers what it wrote, and step 5 stages exactly
   `self.written` — without it the edited `__init__.py` would be written but
   never staged, so the publish would commit everything except the edit.
2. **`fail()` no longer rolls back on `edit`.** The branch was
   `step != "preflight"`; `edit` writes nothing, so a failure there would have
   run a rollback reaching past this flow into the user's own working tree.
   Now `step not in ("preflight", "edit")`.
3. **`tests/share_pipeline/test_step_sequence.py` pins the step-module roster**
   and screen→module map; both gained `metadata`/`edit`. The plan did not
   mention this guard test.
4. **The panel follows the file's real idiom** — `_footer()` + `_decision()` +
   `_busy_advance(rerender, button, coro)`, not the sketched
   `hui.section`/`dialog_actions`, which do not exist. Selects pass
   `in_popup=True`: the flow renders in a `Popup` (z-7001) and a QMenu at
   z-6000 would open behind it.
5. **`LibraryReloadAction` imports from `haywire.core.library.identity`**, not
   `.reload`, matching `_state.py`.

Two smaller notes: the plan's `test_apply_writes_the_decorator` declared
`tests_path="tests/"` against a fixture that never created it, which
`validate_edit` correctly rejects — the fixture now creates the directory. And
`_set_decorator_str_field`'s insert-when-absent behavior did NOT trip the
round-trip test, so the remove-when-empty helper Task 1 Step 4 anticipated was
not needed.

Risk 3 from the self-review is now real: the library detail view has no Edit
button and no Share entry point. Deferred to step 10, as the plan directed.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-library-metadata-edit-in-share.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
