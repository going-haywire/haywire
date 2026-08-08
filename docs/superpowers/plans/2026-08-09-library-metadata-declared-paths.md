# Declared-Path Preconditions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A library declaring `examples_path` or `tests_path` that does not exist
fails preflight with a repairable fault, instead of publishing a tag-pinned row
pointing at nothing.

**Architecture:** One more per-library check in the preconditions loop, emitting a
`PreconditionFailure` with `kind="act"` and a `fix_id`, plus two handlers in
`_PRECONDITION_FIXES`. Reuses the shape `strip_os` already established, including
its `lib_dir` kwarg for disambiguating which library failed.

**Tech Stack:** Python 3.12, `haywire.core.publishing.pipeline`, pytest.

## Global Constraints

- Line length 109 (`uv run ruff check .` **and** `uv run ruff format --check .` — CI runs both).
- Type-check with the exact command in `CLAUDE.md`; `haybale-visiongraph` is excluded.
- Gate before every commit: `uv run pytest -m "not browser and not perf"` (~2.5 min).
- Never call `create_test_injector()` directly in a test — use the `test_injector` fixtures.
- `PreconditionFailure.fix_id` is a **string, not a callable** — the report stays
  serializable and repo-mutating closures never cross the engine/UI seam.
- Preflight **never mutates**. That is what makes `ShareFlow.fail`'s revert a
  narrow, provable operation; a fix runs only on an explicit click, after which
  the user restarts the wizard to re-check from the top.

## Predecessors

All landed:

- [foundation](2026-08-08-library-metadata-foundation.md) — `LibraryMetadata` base;
  rows carry `docs_path`/`examples_path`/`tests_path` resolved through `HostProvider`.
- [distribution](2026-08-08-library-metadata-distribution.md) — `examples_path` and
  `tests_path` became decorator kwargs.
- [one-reader](2026-08-08-library-metadata-one-reader.md) — `read_decorator()` is
  the single AST reader.
- [edit-in-share](2026-08-08-library-metadata-edit-in-share.md) — the `edit` screen
  validates the two path fields **inline**, via
  `pipeline/steps/metadata.validate_edit`.

## Verified starting state

Confirmed on disk 2026-08-09.

**`STEPS = ("preflight", "edit", "review", "publish", "done")`** — five entries,
four acting screens.

**The precondition machinery this plan extends:**

- `PreconditionFailure` (`pipeline/results.py:13`) carries `message`, `remedy`,
  `kind` (`"inform"` | `"act"`), `fix_id`, `fix_label`, `lib_dir`.
- `_PRECONDITION_FIXES` (`pipeline/fixes.py:198`) currently maps four ids:
  `strip_os`, `add_origin`, `commit_dirty_tree`, `switch_branch`.
- `_fix_strip_os` (`fixes.py:121`) is the closest analogue — it takes a `lib_dir`
  kwarg **relative to `pipeline.repo_root`** because a repo can have several barn
  libraries each with an independent fault, and calls `pipeline.record([...])` with
  the files it touched.
- The per-library loop is `steps/preconditions.py:135`, which already computes
  `rel_lib_dir` for exactly this purpose and **returns on the first failing
  library** rather than collecting across all of them.

**A gap this plan closes.** `validate_edit` checks declared paths, but only for
edits made *through the wizard*. A path authored by hand in `__init__.py`, or one
whose target was deleted after the edit, reaches `publish` unchecked. Rows are
tag-pinned, so a wrong path is unfixable without cutting another release.

**Two fix shapes are possible**, and they differ in what they assert:

| fix | what it does | when it is right |
| --- | --- | --- |
| `clear_examples_path` | removes the kwarg | the author no longer has examples |
| `set_examples_path` | rewrites it to a path that exists | the folder moved |

The second needs a target, which preflight cannot guess. This plan ships **only
the clearing fix**, and states in the remedy that the alternative is to edit the
path on the wizard's `edit` screen — which already exists and already validates.

## Out of scope

- **step 10: author-facing migration.** The 10 barn libraries still pass the six
  superseded kwargs; the `dependencies=` shim, `_SUPERSEDED_KWARGS`, and the
  `[tool.haywire].os` fallback all survive until then.
- **`docs_path`.** Derived from the module directory at publish time, never
  authored, so there is no declaration to contradict.

## File Structure

| File | Responsibility |
| --- | --- |
| `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/preconditions.py` | the per-library path check |
| `packages/haywire-core/src/haywire/core/publishing/pipeline/fixes.py` | two clearing handlers |
| `packages/haywire-core/src/haywire/core/publishing/manifest/decorator_ast.py` | unchanged — reader already returns both paths |
| `tests/share_pipeline/test_declared_paths.py` | **new** |

---

### Task 1: Clear a declared path

The repair, written before the check that offers it, so the check can be wired to
a handler that already works.

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/publishing/pipeline/fixes.py`
- Test: `tests/share_pipeline/test_declared_paths.py` (create)

**Interfaces:**

- Consumes: `decorator_io._set_decorator_str_field`; `find_module_dir(lib_dir)`;
  `pipeline.record(paths)`; `PipelineStateError`.
- Produces:
  - `_fix_clear_examples_path(pipeline, **kwargs)` — `fix_id="clear_examples_path"`,
    requires a `lib_dir` kwarg relative to `repo_root`.
  - `_fix_clear_tests_path(pipeline, **kwargs)` — likewise.
  - Both registered in `_PRECONDITION_FIXES`.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_declared_paths.py`:

```python
"""A declared examples_path/tests_path must exist, or the publish is a lie.

Rows are tag-pinned: a path pointing at nothing cannot be corrected without
cutting another release, so the fault is caught at preflight rather than
discovered by a consumer.
"""

from pathlib import Path

import pytest

from haywire.core.publishing.pipeline.fixes import _PRECONDITION_FIXES

DECORATOR = '''from haywire.core.library.decorator import library


@library(
    id="demo",
    label="Demo",
    examples_path="examples/OVERVIEW.md",
    tests_path="tests/",
    file_watcher=True,
)
class Library:
    pass
'''


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

    def record(self, paths) -> None:
        self.recorded.extend(paths)


def test_both_clearing_fixes_are_registered():
    assert "clear_examples_path" in _PRECONDITION_FIXES
    assert "clear_tests_path" in _PRECONDITION_FIXES


def test_clear_examples_path_removes_only_that_kwarg(repo):
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")

    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert "examples_path" not in source
    assert 'tests_path="tests/"' in source
    assert 'id="demo"' in source
    assert "file_watcher=True" in source


def test_clear_tests_path_removes_only_that_kwarg(repo):
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_tests_path"](pipeline, lib_dir="barn/haybale-demo")

    source = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    assert "tests_path" not in source
    assert 'examples_path="examples/OVERVIEW.md"' in source


def test_the_fix_records_the_file_it_touched(repo):
    """SharePipeline.record drives the rollback set; an unrecorded write is
    a write the revert cannot undo."""
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    assert pipeline.recorded == [
        repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py"
    ]


def test_the_result_still_parses(repo):
    """A fix that leaves the decorator unreadable is worse than the fault."""
    from haywire.core.publishing.manifest.decorator_ast import read_decorator

    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")

    got = read_decorator(repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py")
    assert got.id == "demo"
    assert got.examples_path == ""
    assert got.tests_path == "tests/"


def test_missing_lib_dir_kwarg_raises(repo):
    from haywire.core.publishing.pipeline.errors import PipelineStateError

    with pytest.raises(PipelineStateError, match="lib_dir"):
        _PRECONDITION_FIXES["clear_examples_path"](_FakePipeline(repo))


def test_clearing_an_absent_kwarg_is_a_no_op(repo):
    """Idempotent: the user may click the fix twice, or the path may already
    have been cleared on the edit screen."""
    pipeline = _FakePipeline(repo)
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    before = (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text()
    _PRECONDITION_FIXES["clear_examples_path"](pipeline, lib_dir="barn/haybale-demo")
    assert (repo / "barn" / "haybale-demo" / "haybale_demo" / "__init__.py").read_text() == before
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_declared_paths.py -v`

Expected: FAIL — `KeyError: 'clear_examples_path'`.

Check the `PipelineStateError` import path against the repo before running; the
test above assumes `pipeline/errors.py`. Correct it if `fixes.py` imports it from
elsewhere.

- [ ] **Step 3: Add a remover to `decorator_io`**

`_set_decorator_str_field` writes `field=""` when given an empty value, which
leaves a meaningless `examples_path=""` in the source. Clearing means *removing*
the kwarg.

Add to `packages/haywire-core/src/haywire/core/library/decorator_io.py`, beside
the setters:

```python
def _remove_decorator_field(content: str, field: str) -> str:
    """Delete a whole kwarg line from the ``@library(...)`` call.

    Distinct from setting it empty: an absent kwarg means "not declared", which
    is what a cleared path must say. ``examples_path=""`` would still read as a
    declaration to anyone scanning the source, and would round-trip back through
    the AST reader as an empty string rather than as absent.

    A no-op when the field is not present, so a repair offered twice is safe.
    """
    pattern = rf"^[ \t]*{re.escape(field)}=(?:['\"][^'\"]*['\"]|\[[^\]]*\]),?[ \t]*\r?\n"
    return re.sub(pattern, "", content, count=1, flags=re.MULTILINE)
```

- [ ] **Step 4: Write the handlers**

In `packages/haywire-core/src/haywire/core/publishing/pipeline/fixes.py`, beside
`_fix_strip_os`:

```python
def _fix_clear_declared_path(pipeline: "SharePipeline", field: str, **kwargs: str) -> None:
    """Remove *field* from a library's ``@library(...)`` call.

    Requires a `lib_dir` kwarg relative to `pipeline.repo_root` — a repo can
    have several barn libraries, each with its own independent path fault, same
    reasoning as :func:`_fix_strip_os`.

    Clearing rather than correcting: preflight knows the declared path is wrong
    but not what the author meant instead. Repointing it is an edit, and the
    wizard's `edit` screen already offers that with inline validation.
    """
    lib_dir_rel = kwargs.get("lib_dir")
    if not lib_dir_rel:
        raise PipelineStateError(
            f"apply_precondition_fix('clear_{field}', ...) requires a lib_dir kwarg."
        )
    lib_dir = pipeline.repo_root / lib_dir_rel
    module_dir = find_module_dir(lib_dir)
    if module_dir is None:
        raise PipelineStateError(f"No module directory found under {lib_dir_rel}.")
    init_py = module_dir / "__init__.py"
    if not init_py.is_file():
        raise PipelineStateError(f"No __init__.py found under {lib_dir_rel}.")

    init_py.write_text(_remove_decorator_field(init_py.read_text(), field))
    pipeline.record([init_py])


def _fix_clear_examples_path(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="clear_examples_path"."""
    _fix_clear_declared_path(pipeline, "examples_path", **kwargs)


def _fix_clear_tests_path(pipeline: "SharePipeline", **kwargs: str) -> None:
    """Handler for fix_id="clear_tests_path"."""
    _fix_clear_declared_path(pipeline, "tests_path", **kwargs)
```

Register both:

```python
_PRECONDITION_FIXES: dict[str, Callable[..., None]] = {
    "strip_os": _fix_strip_os,
    "add_origin": _fix_add_origin,
    "commit_dirty_tree": _fix_commit_dirty_tree,
    "switch_branch": _fix_switch_branch,
    "clear_examples_path": _fix_clear_examples_path,
    "clear_tests_path": _fix_clear_tests_path,
}
```

Add the imports `find_module_dir` and `_remove_decorator_field`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_declared_paths.py -v`

Expected: all PASS.

If `test_clear_examples_path_removes_only_that_kwarg` fails because the regex ate
the following line, the trailing-newline group is wrong — the pattern must consume
exactly one line including its terminator. Add a case with the kwarg on the last
line before `)` to pin that.

- [ ] **Step 6: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-core/src/ tests/share_pipeline/
uv run ruff format --check packages/haywire-core/src/ tests/share_pipeline/
uv run mypy packages/haywire-core/src/
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(share): repair a declared path that does not exist

Two precondition fixes that remove examples_path/tests_path from a library's
decorator, plus the _remove_decorator_field helper they need — setting the
field empty would leave examples_path=\"\" in the source, which still reads as
a declaration.

Clearing rather than correcting: preflight knows the path is wrong but not what
the author meant instead. Repointing it is an edit, and the wizard's edit screen
already offers that with inline validation.

No check emits these yet.

ADR 0024."
```

---

### Task 2: The preflight check

**Files:**

- Modify: `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/preconditions.py:135-181`
- Test: `tests/share_pipeline/test_declared_paths.py` (extend)

**Interfaces:**

- Consumes: `read_decorator(init_py)`; `_fix_clear_examples_path` /
  `_fix_clear_tests_path` from Task 1.
- Produces: a `PreconditionFailure` with `kind="act"`,
  `fix_id="clear_examples_path"` or `"clear_tests_path"`, and
  `lib_dir=str(rel_lib_dir)`.

- [ ] **Step 1: Write the failing test**

Append to `tests/share_pipeline/test_declared_paths.py`:

```python
def _report(repo: Path):
    """Run preconditions against a real SharePipeline over *repo*."""
    from haywire.core.publishing.pipeline import SharePipeline

    return SharePipeline(repo_root=repo).check_preconditions()


def test_an_existing_path_passes(repo):
    lib = repo / "barn" / "haybale-demo"
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")
    (lib / "tests").mkdir()

    failures = [f for f in _report(repo).failures if "path" in f.message]
    assert failures == []


def test_a_missing_examples_path_fails_with_a_repairable_fault(repo):
    lib = repo / "barn" / "haybale-demo"
    (lib / "tests").mkdir()  # only tests/ exists

    failure = next(f for f in _report(repo).failures if "examples_path" in f.message)
    assert failure.kind == "act"
    assert failure.fix_id == "clear_examples_path"
    assert failure.lib_dir == "barn/haybale-demo"
    assert "examples/OVERVIEW.md" in failure.message


def test_a_missing_tests_path_fails(repo):
    lib = repo / "barn" / "haybale-demo"
    (lib / "examples").mkdir()
    (lib / "examples" / "OVERVIEW.md").write_text("# Examples\n")

    failure = next(f for f in _report(repo).failures if "tests_path" in f.message)
    assert failure.fix_id == "clear_tests_path"


def test_an_undeclared_path_is_not_checked(tmp_path):
    """Absent means 'no examples' — a complete answer needing no check."""
    lib = tmp_path / "barn" / "haybale-bare"
    (lib / "haybale_bare").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-bare"\nversion = "0.1.0"\n')
    (lib / "haybale_bare" / "__init__.py").write_text(
        '@library(id="bare", label="Bare")\nclass Library: pass\n'
    )

    assert [f for f in _report(tmp_path).failures if "path" in f.message] == []


def test_the_remedy_names_both_ways_out(repo):
    """The user can clear the declaration or repoint it on the edit screen."""
    failure = next(f for f in _report(repo).failures if "examples_path" in f.message)
    assert "edit" in failure.remedy.lower()


def test_the_fix_makes_preflight_pass(repo):
    """End-to-end: the offered repair actually clears the fault."""
    from haywire.core.publishing.pipeline import SharePipeline

    (repo / "barn" / "haybale-demo" / "tests").mkdir()
    pipeline = SharePipeline(repo_root=repo)
    failure = next(f for f in pipeline.check_preconditions().failures if "examples_path" in f.message)

    pipeline.apply_precondition_fix(failure.fix_id, lib_dir=failure.lib_dir)

    assert [f for f in pipeline.check_preconditions().failures if "examples_path" in f.message] == []
```

`SharePipeline(repo_root=...)` may need more construction arguments, and
`check_preconditions` may be spelled `require_preconditions` (which raises) versus
a non-raising variant. Read `pipeline.py` first and match it; if only the raising
form exists, catch `PreconditionsError` and read `.report`.

These tests need a git repo for the earlier preconditions (remote, branch) to pass
far enough to reach the per-library loop. Either `git init` + `git remote add` in
the fixture, or assert only on the presence of the path failure among whatever
failures come back — the loop at line 135 runs before the remote check, so the
latter works and is simpler.

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_declared_paths.py -v -k "path"`

Expected: the new tests FAIL — no failure mentions `examples_path`.

- [ ] **Step 3: Add the check**

In `steps/preconditions.py`, inside the `for lib_dir in barn_libraries:` loop and
**after** the `read_manifest` try/except (so a library with unparseable TOML is
reported as that, not as a path fault), add:

```python
        module_dir = find_module_dir(lib_dir)
        init_py = (module_dir / "__init__.py") if module_dir else None
        if init_py is not None and init_py.is_file():
            decorator = read_decorator(init_py)
            for field, declared in (
                ("examples_path", decorator.examples_path),
                ("tests_path", decorator.tests_path),
            ):
                if declared and not (lib_dir / declared).exists():
                    return PreconditionsReport(
                        failures=[_declared_path_failure(field, declared, rel_lib_dir)],
                        remote_url=None,
                        barn_libraries=barn_libraries,
                    )
```

and the failure builder beside the other module-level builders:

```python
def _declared_path_failure(field: str, declared: str, rel_lib_dir: Path | str) -> PreconditionFailure:
    """A library declares a path that is not there.

    Publishing would emit a tag-pinned row pointing at nothing, and a pinned row
    cannot be corrected without cutting another release — so this blocks rather
    than warns. An *absent* declaration is not a fault: it means "no examples",
    which is a complete answer.
    """
    return PreconditionFailure(
        message=f"{rel_lib_dir} declares {field}={declared!r}, which does not exist.",
        remedy=(
            f"Publishing would point consumers at {declared!r} inside this library, "
            "and the row is pinned to the release tag — so a wrong path cannot be "
            "corrected without publishing again.\n\n"
            f"Either clear the declaration with the button below, or set {field} to "
            "the right path on the wizard's edit screen."
        ),
        kind="act",
        fix_id=f"clear_{field}",
        fix_label=f"Clear {field}",
        lib_dir=str(rel_lib_dir),
    )
```

Import `find_module_dir` and `read_decorator`.

**Note the loop returns on the first failure** — matching `strip_os`'s existing
behavior. A repo with faults in two libraries surfaces them one at a time, which
is the established pattern here; do not change it in this plan.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/share_pipeline/test_declared_paths.py -v`

Expected: all PASS.

- [ ] **Step 5: Run the pipeline and share suites**

```bash
uv run pytest tests/share_pipeline/ -q
```

Expected: all pass. A failure in `test_preconditions.py` asserting an exact
failure count or the first failure's identity is a test that now sees the new
check — read it before changing it, since some of those pin ordering deliberately.

- [ ] **Step 6: Run the full gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/task2.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/task2.log | head -20
```

Expected: `exit=0`, no FAILED lines.

**Watch for a self-inflicted failure:** this repo's own barn libraries do not
declare `examples_path`/`tests_path`, so the check should not fire on them. If a
share-pipeline test that runs against the real repo starts failing, a barn library
does declare one — fix the declaration or the folder, do not weaken the check.

- [ ] **Step 7: Lint, format, type-check**

```bash
uv run ruff check packages/ barn/ tests/
uv run ruff format --check packages/ barn/ tests/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(share): block a publish that declares a path it does not have

A library declaring examples_path or tests_path that is not on disk now fails
preflight with a repairable fault, offering to clear the declaration.

Rows are tag-pinned, so a path pointing at nothing cannot be corrected without
cutting another release — the fault has to be caught before the tag, not
discovered by a consumer. An absent declaration is not a fault: it means 'no
examples', which is a complete answer.

The wizard's edit screen already validated these inline; this covers paths
authored by hand, and targets deleted after an edit.

ADR 0024."
```

---

## Self-Review

**Spec coverage.** This plan implements migration **step 6**. After it lands, only
**step 10** (the author-facing migration) remains.

**Deviation from the design doc, flagged.** The consolidation doc names two fix
handlers per field — `clear_examples_path` *and* `set_examples_path`. This plan
ships only the clearing pair. `set_examples_path` needs a target path, which
preflight cannot guess and a modal cannot sensibly prompt for without becoming a
file browser; and the wizard's `edit` screen already offers exactly that, with
inline validation, one screen later. The remedy text names both routes so the user
is not left thinking clearing is the only option. If a "browse for the folder"
affordance is wanted later, it belongs on the edit screen, not in a fix handler.

**One duplication accepted.** `validate_edit` (edit screen) and
`_declared_path_failure` (preflight) both check that a declared path exists. They
run at different times against different inputs — pending edits versus what is on
disk — so a shared helper would take a `LibraryEdit` in one case and a
`DecoratorFields` in the other. Two four-line checks is cheaper than the seam.
Worth revisiting only if a third caller appears.

**Type consistency.** `fix_id` strings are `f"clear_{field}"` where `field` is
`"examples_path"` or `"tests_path"`, matching the `_PRECONDITION_FIXES` keys
exactly. `lib_dir` is a **relative** string on both the failure and the fix kwarg,
consistent with `_fix_strip_os`.

**Three risks worth naming.**

1. **`_remove_decorator_field`'s regex is line-oriented.** A kwarg written across
   several lines (a long list, or a string broken with implicit concatenation)
   would leave a fragment behind and break the file. The two fields it targets are
   short single-line strings in every current library, but the helper is general
   enough to be reused. Task 1 Step 5 adds a last-line-before-`)` case; consider
   also asserting the result still parses via `ast.parse`, which
   `test_the_result_still_parses` does for the happy path.
2. **The check runs on every publish, for every barn library.** It is a
   `Path.exists()` per declared path — negligible — but it sits in a loop that
   already does a TOML read per library, and now adds an AST parse per library.
   For a 10-library repo that is 10 more parses on a path that already takes
   ~2s for `git ls-remote`. Acceptable; worth remembering if preflight ever feels
   slow.
3. **Returning on the first failure hides sibling faults.** Established behavior
   (`strip_os` does the same), so this plan matches it rather than diverging — but
   a repo with three bad paths needs three fix-and-restart cycles. If that becomes
   a complaint, changing it is a separate, cross-cutting decision about the whole
   preconditions loop.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-09-library-metadata-declared-paths.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
