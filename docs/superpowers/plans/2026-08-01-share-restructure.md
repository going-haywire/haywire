# Share Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganise the share code into a layered `haywire_studio/share/` package with thematically-grouped modules, without changing any behaviour.

**Architecture:** Two ~950-line files (`share.py`, `share_pipeline/pipeline.py`) are split along seams the code's own call graph already has. `share.py` becomes six themed modules (manifest, url, readme, drift, marketstall) plus the two leaf utilities it depends on. `SharePipeline` keeps all its state and public methods but delegates each of its six steps to a module in `share/pipeline/steps/`. The eager re-export in `share_pipeline/__init__.py` — the sole cause of the documented import cycle — is replaced by strict layering, so cycles become structurally impossible rather than policy-enforced.

**Tech Stack:** Python 3.12, pytest, ruff, mypy, `uv` for all commands.

## THIS IS A REFACTOR, NOT TDD

**Do not write failing tests first.** This plan changes no behaviour. The existing 300 tests already encode the contract; the risk is that a move silently breaks it. Inverting TDD is correct here:

| TDD (new features) | This plan (refactor) |
|---|---|
| Red first, then green | **Green at every commit** |
| Test proves new behaviour | Test proves behaviour *didn't* change |
| Red is expected | **Red means you broke something — stop and fix** |

Each move task follows: **`git mv` → fix imports in the moved file → repoint every consumer and test in the SAME commit → run tests → green → commit.** Never leave a commit where the suite is red.

Two exceptions, both flagged in their tasks:
- **Task 1** writes a characterization test *before* any move (it must pass immediately — it captures existing behaviour).
- **Task 14** is genuinely new (the step-divergence test) and is the only task using red-green.

## Global Constraints

- **Behaviour must not change.** No signature changes, no renames, no logic edits, except the single documented rename in Task 11 (`_record` → `record`).
- **Baseline (verified 2026-08-01, must stay true at every commit):** `uv run pytest tests/share_pipeline/ tests/test_share_*.py tests/test_gitcmd.py tests/test_barn.py tests/test_deps_cli.py tests/studio/test_share_examples.py` → **300 passed**. `uv run ruff check packages/haywire-studio/src/haywire_studio/` → clean. `uv run ruff format --check` → clean. `uv run mypy packages/haywire-studio/src/` → clean, 30 files.
- **Use `git mv`**, never delete-and-create — file history must survive.
- **Line length is 109** (`ruff` config). Run `uv run ruff format .` before every commit.
- **Never import `haywire_studio.share` (the package root) from inside `share/`.** The root re-exports; an internal module importing it recreates the cycle this restructure removes. Import concrete sibling modules instead.
- **Do not touch:** `barn/haybale-marketplace/.../_share_wizard.py` beyond its single import line · `docs_gen/` · `deps_cli.py` (beyond its import lines) · `decorator_io.py` · `dep_detect.py` · `init.py` · `rename.py`.
- **Layer order** (each may import only from layers above it): `git.py`/`barn.py` → `manifest/`, `url.py`, `readme.py` → `drift/`, `marketstall.py` → `pipeline/` → `cli.py`.

---

## File Structure

**Final layout** (`packages/haywire-studio/src/haywire_studio/share/`):

| File | Responsibility | Source |
|---|---|---|
| `__init__.py` | Re-exports the full current vocabulary. Imports from submodules; nothing imports it back. | new + `share_pipeline/__init__.py` |
| `git.py` | Hardened git subprocess wrappers. No `haywire_studio` imports. | `gitcmd.py` |
| `barn.py` | `barn/` repo-shape queries. No `haywire_studio` imports. | `barn.py` |
| `manifest/errors.py` | `ManifestReadError`, `InvalidOsDeclarationError` | `share.py:91-107` |
| `manifest/reader.py` | `_read_raw_toml`, `read_manifest`, `read_manifest_lenient` | `share.py:183-199, 264-293` |
| `manifest/os_field.py` | The 5 os-value functions + `_DECLARABLE_OS_VALUES` | `share.py:28, 110-129, 142-180, 202-261` |
| `manifest/deps.py` | `_read_library_label`, `_read_library_dependencies` | `share.py:348-376` |
| `url.py` | git-root/remote/ref probes, ssh→https, `_derive_url`, `ShareSaveResult` | `share.py:296-345, 792-798, 801-872` |
| `readme.py` | Marker-block rewriting | `share.py:30-32, 35-88` |
| `drift/model.py` | `DepDrift` | `share.py:498-518` |
| `drift/versionspec.py` | `_strip_specifier`, `_parse_floor_spec`, `_version_tuple` | `share.py:583-625` |
| `drift/detect.py` | `detect_share_drift`, `_detect_pyproject_version_lag` | `share.py:521-580, 670-701` |
| `drift/apply.py` | `apply_drift_fix`, `union_pyproject_deps` | `share.py:628-667, 729-785` |
| `drift/report.py` | `_format_drift_report` | `share.py:707-726` |
| `marketstall.py` | `NoBarnError`, `MarketstallWriteResult`, entry building, `write_marketstall` | `share.py:379-483, 788-789, 875-948` |
| `pipeline/errors.py` | 9 `ShareError` subclasses — **unchanged** | `share_pipeline/errors.py` |
| `pipeline/results.py` | 10 result dataclasses — **unchanged** | `share_pipeline/results.py` |
| `pipeline/versions.py` | Version read/plan/write, `refresh_lockfile` — **unchanged** | `share_pipeline/versions.py` |
| `pipeline/fixes.py` | `_fix_add_origin`, `_fix_strip_os`, `_PRECONDITION_FIXES` | `pipeline.py:89-160` |
| `pipeline/pipeline.py` | `SharePipeline` — state + thin delegating methods | `pipeline.py:162-957` |
| `pipeline/steps/preconditions.py` | `check_preconditions` body + `_detached_head_remedy` | `pipeline.py:185-401` |
| `pipeline/steps/drift.py` | drift check/union/replace/written-paths | `pipeline.py:435-510` |
| `pipeline/steps/version.py` | tag availability + bump | `pipeline.py:522-581` |
| `pipeline/steps/docs.py` | docs command/apply/write-set | `pipeline.py:585-677` |
| `pipeline/steps/commit.py` | marketstall, dirty files, commit plan, `_diffstat`, commit | `pipeline.py:681-757, 759-808, 866-916` |
| `pipeline/steps/push.py` | branch, push command, verify, push | `pipeline.py:810-864, 920-957` |
| `cli.py` | `haywire share` CLI — **unchanged** | `share_cli.py` |

**Staying put (do not move):** `docs_gen/` (no share coupling; the pipeline deliberately shells out — see `.insights/project_docs_gen_reentrancy.md`) · `deps_cli.py` (deliberately decoupled from `SharePipeline`, commit `241de53b`) · `haywire.core.library.decorator_io` / `dep_detect` (real non-share consumers, different distribution).

---

### Task 1: Characterization test for the public import surface

Locks in what `haywire_studio.share` must still export after the move. Written first and **passes immediately** — it describes today's behaviour.

**Files:**
- Create: `tests/share_pipeline/test_public_surface.py`

**Interfaces:**
- Produces: a test that every later task re-runs to prove the vocabulary survived.

- [ ] **Step 1: Write the characterization test**

```python
"""The public import surface of the share package.

A characterization test: it encodes what external consumers (the share
wizard, _overview_edit_dialog, deps_cli, app.py) import today, so the
restructure cannot silently drop a name. It is not a design statement —
narrowing this surface is a deliberate follow-up, not something to do by
accident.
"""

import importlib

# Every name the wizard imports from the pipeline package today.
_WIZARD_IMPORTS = (
    "CommitPlan",
    "CommitResult",
    "DocsResult",
    "DriftReport",
    "PreconditionFailure",
    "PreconditionsError",
    "PreconditionsReport",
    "PushResult",
    "ShareError",
    "SharePipeline",
    "VersionPlan",
)

# Names other in-repo consumers reach for.
_OTHER_CONSUMER_IMPORTS = (
    "derive_share_url_only",  # _share_wizard._panel_done
    "union_pyproject_deps",   # _overview_edit_dialog
    "detect_share_drift",     # deps_cli
)


def test_pipeline_vocabulary_is_importable() -> None:
    module = importlib.import_module("haywire_studio.share_pipeline")
    missing = [name for name in _WIZARD_IMPORTS if not hasattr(module, name)]
    assert missing == [], f"share_pipeline no longer exports: {missing}"


def test_share_domain_functions_are_importable() -> None:
    module = importlib.import_module("haywire_studio.share")
    missing = [name for name in _OTHER_CONSUMER_IMPORTS if not hasattr(module, name)]
    assert missing == [], f"share no longer exports: {missing}"


def test_share_error_hierarchy_is_intact() -> None:
    """Every step exception stays a ShareError, so the wizard's single
    `except ShareError` per step keeps catching all of them."""
    module = importlib.import_module("haywire_studio.share_pipeline")
    for name in (
        "PreconditionsError",
        "ManifestError",
        "VersionError",
        "TagCollisionError",
        "DocsGenerationError",
        "MarketstallError",
        "CommitError",
        "PushError",
        "PipelineStateError",
    ):
        assert issubclass(getattr(module, name), module.ShareError), name
```

- [ ] **Step 2: Run it — it must PASS (this is not TDD)**

Run: `uv run pytest tests/share_pipeline/test_public_surface.py -v`
Expected: **3 passed**. A failure here means the baseline is not what this plan assumes — stop and investigate before moving anything.

- [ ] **Step 3: Commit**

```bash
git add tests/share_pipeline/test_public_surface.py
git commit -m "test(share): characterize the public import surface before restructure"
```

---

### Task 2: Create the package skeleton and move the two leaf modules

`gitcmd.py` and `barn.py` have no `haywire_studio` imports, so they move with zero internal edits. Doing them first gives every later task a stable bottom layer.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share/__init__.py`
- Move: `gitcmd.py` → `share/git.py`; `barn.py` → `share/barn.py`
- Modify: `share.py`, `share_pipeline/pipeline.py`, `share_pipeline/versions.py`, `share_pipeline/__init__.py`, `deps_cli.py`
- Test: `tests/test_gitcmd.py`, `tests/test_barn.py`, `tests/share_pipeline/test_preconditions.py`, `tests/share_pipeline/test_bump_step.py`, `tests/share_pipeline/test_commit_step.py`, `tests/share_pipeline/test_docs_step.py`, `tests/share_pipeline/test_push_step.py`, `tests/test_share_wizard_ui.py`

**Interfaces:**
- Produces: `haywire_studio.share.git` (`GitResult`, `git`, `git_remote`, `git_remote_streaming`, `run`, `run_streaming`), `haywire_studio.share.barn` (`barn_library_dirs`, `current_ref`). Both importable with no `haywire_studio` dependency.

- [ ] **Step 1: Create the package and move both files**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio
mkdir -p share
touch share/__init__.py
git mv gitcmd.py share/git.py
git mv barn.py share/barn.py
```

- [ ] **Step 2: Update the moved files' docstrings**

In `share/git.py`, replace the first docstring line:

```python
"""Hardened ``git`` subprocess helpers for the share package.
```

In `share/barn.py`, replace the whole module docstring (it currently justifies the now-removed cycle rule):

```python
"""Repo-shape queries about ``barn/``.

The bottom layer of the share package: no imports from anywhere else in
``haywire_studio``, so every other share module can depend on it freely.
"""
```

- [ ] **Step 3: Repoint every importer**

`share.py:25-26` — replace both lines with:

```python
from haywire_studio.share import barn, git as gitcmd
from haywire_studio.share.barn import barn_library_dirs
```

`share_pipeline/pipeline.py:30-32` — replace with:

```python
from haywire_studio.share import barn
from haywire_studio.share.barn import barn_library_dirs
from haywire_studio.share.git import git, git_remote, git_remote_streaming, run_streaming
```

`share_pipeline/versions.py:20` and its `gitcmd` import — replace with:

```python
from haywire_studio.share import git as gitcmd
from haywire_studio.share.barn import barn_library_dirs
```

`share_pipeline/__init__.py:7` — replace `from haywire_studio.gitcmd import (` with:

```python
from haywire_studio.share.git import (
```

`deps_cli.py:14` — replace with:

```python
from haywire_studio.share.barn import barn_library_dirs
```

- [ ] **Step 4: Repoint the tests**

In `tests/test_gitcmd.py` and `tests/test_barn.py`, replace `haywire_studio.gitcmd` → `haywire_studio.share.git` and `haywire_studio.barn` → `haywire_studio.share.barn`.

In `tests/share_pipeline/test_preconditions.py`, `test_bump_step.py`, `test_commit_step.py`, `test_docs_step.py`, `test_push_step.py` and `tests/test_share_wizard_ui.py`, replace `from haywire_studio import gitcmd` with:

```python
from haywire_studio.share import git as gitcmd
```

This keeps every `gitcmd.GitResult(...)` call site in those files working unchanged.

`tests/share_pipeline/test_preconditions.py:141,232` patch `gitcmd.subprocess` — the alias above keeps these correct with no edit.

- [ ] **Step 5: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/ tests/
uv run pytest tests/share_pipeline/ tests/test_share_*.py tests/test_gitcmd.py tests/test_barn.py tests/test_deps_cli.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: **300 passed**, mypy clean. Any failure = a missed import site; fix before committing.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): move gitcmd and barn into the share package as leaf modules"
```

---

### Task 3: Extract `manifest/`

**Files:**
- Create: `share/manifest/__init__.py`, `share/manifest/errors.py`, `share/manifest/reader.py`, `share/manifest/os_field.py`, `share/manifest/deps.py`
- Modify: `share.py` (remove the extracted blocks, import them back)
- Test: `tests/test_share_os_field.py`, `tests/share_pipeline/test_manifest.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `share.manifest.errors`: `ManifestReadError(RuntimeError)`, `InvalidOsDeclarationError(ManifestReadError)`
  - `share.manifest.reader`: `_read_raw_toml(pyproject_path: Path) -> tuple[str, dict]`, `read_manifest(lib_dir: Path) -> dict`, `read_manifest_lenient(lib_dir: Path) -> dict`
  - `share.manifest.os_field`: `_DECLARABLE_OS_VALUES: frozenset[str]`, `_read_os_field(data: dict, lib_dir: Path) -> list[str]`, `describe_os_fix(invalid_values: list[str]) -> str`, `_partition_os_values(os_decl: list) -> tuple[list[str], list[str]]`, `invalid_os_values(lib_dir: Path) -> list[str]`, `strip_undeclarable_os_values(lib_dir: Path) -> list[str]`
  - `share.manifest.deps`: `_read_library_label(module_dir: Path, fallback: str) -> str`, `_read_library_dependencies(module_dir: Path) -> list[str]`

- [ ] **Step 1: Create the package directory**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio/share
mkdir -p manifest
touch manifest/__init__.py
```

Leave `manifest/__init__.py` empty — callers import the concrete submodule.

- [ ] **Step 2: Create `manifest/errors.py`**

Move `share.py:91-107` verbatim, replacing the cycle-rule docstring (the constraint no longer exists):

```python
"""Manifest read failures, as plain RuntimeErrors.

These sit below the pipeline's error taxonomy: the pipeline translates them
into ``ManifestError`` at its boundary so a wizard step's ``except
ShareError`` catches them. Keeping them independent of that taxonomy lets
non-pipeline callers (``deps_cli``) read manifests without importing it.
"""

from __future__ import annotations


class ManifestReadError(RuntimeError):
    """A library pyproject.toml could not be read or is invalid."""


class InvalidOsDeclarationError(ManifestReadError):
    """Raised when a library's [tool.haywire].os contains an invalid value.

    Only "macos", "windows", "linux" are declarable. "other" is a runtime
    sentinel for unmapped platform.system() results and must not be declared.
    """
```

- [ ] **Step 3: Create `manifest/os_field.py`, `manifest/reader.py`, `manifest/deps.py`**

Move the exact line ranges from `share.py` with **no logic edits**:
- `os_field.py`: line `28` (`_DECLARABLE_OS_VALUES`), `110-129` (`_read_os_field`), `142-180` (`describe_os_fix`, `_partition_os_values`), `202-261` (`invalid_os_values`, `strip_undeclarable_os_values`). Imports needed: `toml`, `Path`, `InvalidOsDeclarationError`/`ManifestReadError` from `.errors`, and `_read_raw_toml` from `.reader`.
- `reader.py`: `183-199` (`_read_raw_toml`), `264-293` (`read_manifest`, `read_manifest_lenient`). `read_manifest` calls `_read_os_field` — import it from `.os_field`.
- `deps.py`: `348-376`. Needs `merge_decorator_list_field`/`norm_dep` — check the existing `share.py` imports and carry across only what these two functions use.

**Circular-import note:** `reader.read_manifest` calls `os_field._read_os_field`, and `os_field` calls `reader._read_raw_toml`. Put the `from .reader import _read_raw_toml` import *inside* the two `os_field` functions that need it (`invalid_os_values`, `strip_undeclarable_os_values`) to break the cycle at module level. This mirrors the function-local import style already used in `app.py` and `_share_wizard.py`.

- [ ] **Step 4: Re-import into `share.py`**

Delete the moved blocks from `share.py` and add near the top:

```python
from haywire_studio.share.manifest.deps import _read_library_dependencies, _read_library_label
from haywire_studio.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.share.manifest.os_field import (
    _partition_os_values,
    _read_os_field,
    describe_os_fix,
    invalid_os_values,
    strip_undeclarable_os_values,
)
from haywire_studio.share.manifest.reader import _read_raw_toml, read_manifest, read_manifest_lenient
```

This keeps `from haywire_studio.share import read_manifest` working for every existing consumer and test.

- [ ] **Step 5: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/
uv run ruff check packages/haywire-studio/src/haywire_studio/
uv run pytest tests/test_share_os_field.py tests/share_pipeline/test_manifest.py tests/share_pipeline/ -q
uv run mypy packages/haywire-studio/src/
```

Expected: all pass. `tests/test_share_os_field.py` (21 tests) is the sharpest check here.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): extract manifest reading, os-field, and dep helpers"
```

---

### Task 4: Extract `url.py` and `readme.py`

**Files:**
- Create: `share/url.py`, `share/readme.py`
- Modify: `share.py`
- Test: `tests/test_share_url_derivation.py`, `tests/test_share_readme_markers.py`

**Interfaces:**
- Consumes: `share.git` (Task 2).
- Produces:
  - `share.url`: `ShareSaveResult` (frozen dataclass), `_find_git_root(start: Path) -> Path | None`, `_get_remote_url(git_root: Path) -> str | None`, `_get_current_ref(git_root: Path) -> str | None`, `_unknown_host_warning(hostname: str) -> str`, `_ssh_to_https(url: str) -> str`, `_derive_url(...) -> ShareSaveResult`, `derive_share_url_only(repo_root: Path) -> ShareSaveResult`
  - `share.readme`: `_README_MARKER_START`, `_README_MARKER_END`, `_README_NAMES`, `_update_readme_markers(content: str, share_url: str) -> str`, `_find_readme(directory: Path) -> Path | None`, `_update_repo_readmes(repo_root: Path, share_url: str) -> list[Path]`

- [ ] **Step 1: Create `share/readme.py`**

Move `share.py:30-32` (the three constants) and `35-88` (three functions) verbatim. Module docstring:

```python
"""README share-URL marker blocks.

``haywire share`` rewrites the block between the marketstall markers in the
repo README and each barn library's README; ``haywire docs`` regenerates
those files but preserves the blocks verbatim.
"""
```

Imports needed: `re`, `Path`.

- [ ] **Step 2: Create `share/url.py`**

Move `share.py:296-345` (git probes + `_ssh_to_https` + `_unknown_host_warning`), `792-798` (`ShareSaveResult`), `801-872` (`_derive_url`, `derive_share_url_only`).

**Important:** `tests/test_share_url_derivation.py` patches `haywire_studio.share._get_current_ref` and `haywire_studio.share._get_remote_url` by string. The re-import in Step 3 keeps those names bound in `share.py`, so those patches keep working — but only because `_derive_url` also lives in `url.py` and resolves them from *its own* module namespace. **The patches must be repointed to `haywire_studio.share.url` in Step 4.**

- [ ] **Step 3: Re-import into `share.py`**

Delete the moved blocks; add:

```python
from haywire_studio.share.readme import _update_repo_readmes
from haywire_studio.share.url import (
    ShareSaveResult,
    _derive_url,
    _get_current_ref,
    _get_remote_url,
    _ssh_to_https,
    derive_share_url_only,
)
```

- [ ] **Step 4: Repoint the string patches**

In `tests/test_share_url_derivation.py`, replace every occurrence:

```python
# before
patch("haywire_studio.share._get_current_ref", ...)
patch("haywire_studio.share._get_remote_url", ...)
# after
patch("haywire_studio.share.url._get_current_ref", ...)
patch("haywire_studio.share.url._get_remote_url", ...)
```

Find them all with:

```bash
grep -n "haywire_studio.share._get_" tests/test_share_url_derivation.py
```

In `tests/test_share_readme_markers.py`, replace `from haywire_studio.share import` with `from haywire_studio.share.readme import` for `_update_readme_markers`, `_find_readme`, `_update_repo_readmes`.

- [ ] **Step 5: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/ tests/
uv run pytest tests/test_share_url_derivation.py tests/test_share_readme_markers.py tests/test_share_save.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: all pass (8 + 8 + 6 tests).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): extract share-URL derivation and README markers"
```

---

### Task 5: Extract `drift/`

The largest extraction from `share.py`. `drift/` has **two** consumers — the pipeline's step 2 and `deps_cli` — so it is a reusable library, not pipeline-private.

**Files:**
- Create: `share/drift/__init__.py`, `share/drift/model.py`, `share/drift/versionspec.py`, `share/drift/detect.py`, `share/drift/apply.py`, `share/drift/report.py`
- Modify: `share.py`, `deps_cli.py`
- Test: `tests/test_share_drift.py`, `tests/test_deps_cli.py`

**Interfaces:**
- Consumes: `share.manifest.reader` (`read_manifest`, `read_manifest_lenient`), `share.manifest.deps` (`_read_library_dependencies`).
- Produces:
  - `share.drift.model`: `DepDrift` (frozen dataclass; fields `lib_dir`, `pyproject_missing`, `decorator_missing`, `pyproject_version_lag`, `unresolved`; property `has_drift`)
  - `share.drift.versionspec`: `_strip_specifier(spec: str) -> str`, `_parse_floor_spec(spec: str) -> tuple[str, str] | None`, `_version_tuple(version: str) -> tuple[int, ...]`
  - `share.drift.detect`: `detect_share_drift(lib_dir: Path) -> DepDrift`, `_detect_pyproject_version_lag(...)`
  - `share.drift.apply`: `apply_drift_fix(drift: DepDrift) -> None`, `union_pyproject_deps(...)`
  - `share.drift.report`: `_format_drift_report(drift: DepDrift) -> str`

- [ ] **Step 1: Create the directory and move in dependency order**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio/share
mkdir -p drift
touch drift/__init__.py
```

Move in this order so each module only imports ones already created:
1. `model.py` ← `share.py:498-518` (`DepDrift`) — imports only `dataclass`, `field`, `Path`
2. `versionspec.py` ← `share.py:583-625` — pure string/tuple helpers, no share imports
3. `detect.py` ← `share.py:521-580` + `670-701` — imports `.model`, `.versionspec`, `manifest.reader`, `manifest.deps`, and `dep_detect`
4. `apply.py` ← `share.py:628-667` + `729-785` — imports `.model`, `.versionspec`, `manifest.reader`, `decorator_io`, `dep_detect`
5. `report.py` ← `share.py:707-726` — imports `.model`

Also move `share.py:704` (`_norm_dep = norm_dep` alias) into whichever module still uses it — check with `grep -n "_norm_dep" share.py` before deleting.

- [ ] **Step 2: Re-import into `share.py`**

```python
from haywire_studio.share.drift.apply import apply_drift_fix, union_pyproject_deps
from haywire_studio.share.drift.detect import detect_share_drift
from haywire_studio.share.drift.model import DepDrift
from haywire_studio.share.drift.report import _format_drift_report
```

- [ ] **Step 3: Repoint `deps_cli.py`**

`deps_cli.py:15` — replace with:

```python
from haywire_studio.share.drift.detect import detect_share_drift
```

- [ ] **Step 4: Repoint the `deps_cli` string patch**

`tests/test_deps_cli.py` patches `"haywire_studio.packaging.deps.detect_share_drift"` — this targets the name *as bound in `deps_cli`*, which Step 3 keeps valid. **No edit needed.** Verify with:

```bash
grep -n "detect_share_drift" tests/test_deps_cli.py
```

- [ ] **Step 5: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/
uv run pytest tests/test_share_drift.py tests/test_deps_cli.py tests/share_pipeline/test_drift_step.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): extract dependency-drift detection, application, and reporting"
```

---

### Task 6: Extract `marketstall.py` and retire `share.py`

After this, `share.py` is empty of definitions and is deleted; `share/__init__.py` takes over its import surface.

**Files:**
- Create: `share/marketstall.py`
- Delete: `share.py`
- Modify: `share/__init__.py`
- Test: `tests/test_share_save.py`, `tests/test_share_marketstall_write.py`, `tests/test_share_os_field.py`

**Interfaces:**
- Consumes: `share.url` (`_derive_url`, `ShareSaveResult`), `share.readme` (`_update_repo_readmes`), `share.manifest` (all), `share.barn`.
- Produces: `share.marketstall`: `NoBarnError(RuntimeError)`, `MarketstallWriteResult` (frozen dataclass), `_build_entry_for_library(lib_dir: Path) -> dict | None`, `build_marketstall_entries(repo_root: Path) -> list[dict]`, `write_marketstall(...) -> MarketstallWriteResult`

- [ ] **Step 1: Create `share/marketstall.py`**

Move `share.py:379-483` (`_build_entry_for_library`), `788-789` (`NoBarnError`), `875-891` (`MarketstallWriteResult`), `894-912` (`build_marketstall_entries`), `915-918` (`_MARKETSTALL_HEADER`), `921-948` (`write_marketstall`).

- [ ] **Step 2: Confirm `share.py` holds only imports**

```bash
grep -n "^def \|^class \|^@dataclass" packages/haywire-studio/src/haywire_studio/share.py
```

Expected: **no output**. If anything remains, move it to the module it belongs to before continuing.

- [ ] **Step 3: Move `share.py`'s import block into `share/__init__.py`**

```bash
git rm packages/haywire-studio/src/haywire_studio/share.py
```

Write `share/__init__.py`:

```python
"""Publishing a haywire project's barn libraries — the ``haywire share`` story.

Layered bottom-up: ``git``/``barn`` (no in-package imports) → ``manifest``,
``url``, ``readme`` → ``drift``, ``marketstall`` → ``pipeline`` → ``cli``.
Modules inside this package import each other directly and never import this
``__init__``; the re-exports below exist for external consumers only, so the
one-directional import keeps cycles structurally impossible.
"""

from haywire_studio.share.drift.apply import apply_drift_fix, union_pyproject_deps
from haywire_studio.share.drift.detect import detect_share_drift
from haywire_studio.share.drift.model import DepDrift
from haywire_studio.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.share.manifest.os_field import (
    describe_os_fix,
    invalid_os_values,
    strip_undeclarable_os_values,
)
from haywire_studio.share.manifest.reader import read_manifest, read_manifest_lenient
from haywire_studio.share.marketstall import (
    MarketstallWriteResult,
    NoBarnError,
    build_marketstall_entries,
    write_marketstall,
)
from haywire_studio.share.url import ShareSaveResult, derive_share_url_only

__all__ = [
    "DepDrift",
    "InvalidOsDeclarationError",
    "ManifestReadError",
    "MarketstallWriteResult",
    "NoBarnError",
    "ShareSaveResult",
    "apply_drift_fix",
    "build_marketstall_entries",
    "derive_share_url_only",
    "describe_os_fix",
    "detect_share_drift",
    "invalid_os_values",
    "read_manifest",
    "read_manifest_lenient",
    "strip_undeclarable_os_values",
    "union_pyproject_deps",
    "write_marketstall",
]
```

**Note:** private names (`_build_entry_for_library`, `_read_library_dependencies`) are deliberately absent — tests reaching for them take the long path, updated in Step 4.

- [ ] **Step 4: Repoint tests that import private names**

`tests/test_share_os_field.py` — `_build_entry_for_library` (4 sites):

```python
from haywire_studio.share.marketstall import _build_entry_for_library
```

`init.py:478` — `_read_library_dependencies`:

```python
from haywire_studio.share.manifest.deps import _read_library_dependencies
```

Find any remaining private imports:

```bash
grep -rn "from haywire_studio.share import.*_" tests/ packages/ barn/ --include="*.py" | grep -v __pycache__
```

- [ ] **Step 5: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/ tests/
uv run pytest tests/test_share_save.py tests/test_share_marketstall_write.py tests/test_share_os_field.py tests/share_pipeline/ -q
uv run mypy packages/haywire-studio/src/
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): extract marketstall writing, retire the monolithic share.py"
```

---

### Task 7: Move `share_pipeline/` into the package (mechanical, no splitting)

Relocate first, split second — so a failure in Task 8+ is unambiguously a splitting bug, not a move bug.

**Files:**
- Move: `share_pipeline/` → `share/pipeline/` (all 5 files)
- Modify: `share/__init__.py`, `share_cli.py`, `barn/haybale-marketplace/.../_share_wizard.py`
- Create: `share_pipeline.py` (temporary compatibility shim — removed in Task 13)
- Test: all of `tests/share_pipeline/`

**Interfaces:**
- Produces: `haywire_studio.share.pipeline` exporting everything `share_pipeline` does today.

- [ ] **Step 1: Move the package**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio
git mv share_pipeline share/pipeline
```

- [ ] **Step 2: Repoint imports inside the moved files**

In `share/pipeline/pipeline.py`, `versions.py`, `__init__.py`, `errors.py`, `results.py`, replace every `haywire_studio.share_pipeline.` with `haywire_studio.share.pipeline.`, and the `from haywire_studio.share import (...)` block in `pipeline.py` with concrete module imports:

```python
from haywire_studio.share.drift.apply import apply_drift_fix
from haywire_studio.share.drift.detect import detect_share_drift
from haywire_studio.share.manifest.errors import InvalidOsDeclarationError, ManifestReadError
from haywire_studio.share.manifest.os_field import (
    describe_os_fix,
    invalid_os_values,
    strip_undeclarable_os_values,
)
from haywire_studio.share.manifest.reader import read_manifest
from haywire_studio.share.marketstall import MarketstallWriteResult, NoBarnError, write_marketstall
```

`share/pipeline/versions.py:21` — replace `from haywire_studio.share import read_manifest_lenient` with:

```python
from haywire_studio.share.manifest.reader import read_manifest_lenient
```

- [ ] **Step 3: Add the temporary compatibility shim**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline.py`:

```python
"""Deprecated import site — use ``haywire_studio.share.pipeline``.

Temporary shim so the pipeline move and the ~60 test-patch repointings can
land in separate commits. Removed in the final task of the restructure.
"""

from haywire_studio.share.pipeline import *  # noqa: F401,F403
from haywire_studio.share.pipeline import __all__  # noqa: F401
```

If `share/pipeline/__init__.py` has no `__all__`, add one listing every name it currently imports.

- [ ] **Step 4: Repoint the direct consumers**

`share_cli.py:20` — `from haywire_studio.share_pipeline import (` → `from haywire_studio.share.pipeline import (`

`_share_wizard.py:26` — `from haywire_studio.share_pipeline import (` → `from haywire_studio.share.pipeline import (` (this is the wizard's one line, per the agreed scope)

`_share_wizard.py:763` — `from haywire_studio.share import derive_share_url_only` — already valid, no edit.

- [ ] **Step 5: Verify green (shim keeps old test paths working)**

```bash
uv run ruff format packages/ barn/
uv run pytest tests/share_pipeline/ tests/test_share_*.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: **300 passed** — old `patch("haywire_studio.share_pipeline.pipeline.X")` strings still resolve through the shim.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share): relocate share_pipeline to share/pipeline behind a shim"
```

---

### Task 8: Extract `pipeline/fixes.py`

The two precondition-fix handlers already take `pipeline` as their first argument, so they move without signature changes.

**Files:**
- Create: `share/pipeline/fixes.py`
- Modify: `share/pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_preconditions.py`

**Interfaces:**
- Consumes: `share.git.git`, `share.manifest.os_field.strip_undeclarable_os_values`, `pipeline.errors`, `pipeline.results.PreconditionFailure`.
- Produces: `share.pipeline.fixes`: `_fix_add_origin(pipeline, **kwargs) -> None`, `_fix_strip_os(pipeline, **kwargs) -> None`, `_PRECONDITION_FIXES: dict[str, Callable[..., None]]`, `_MANIFEST_FAILURE_TYPES: tuple[type[Exception], ...]`

- [ ] **Step 1: Create `share/pipeline/fixes.py`**

Move `pipeline.py:89` (`_MANIFEST_FAILURE_TYPES`), `92-129` (`_fix_add_origin`), `134-149` (`_fix_strip_os`), `152-160` (`_PRECONDITION_FIXES`) verbatim. Use `TYPE_CHECKING` for the pipeline reference:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import toml

from haywire_studio.share.git import git
from haywire_studio.share.manifest.errors import ManifestReadError
from haywire_studio.share.manifest.os_field import strip_undeclarable_os_values
from haywire_studio.share.pipeline.errors import ManifestError, PipelineStateError, PreconditionsError
from haywire_studio.share.pipeline.results import PreconditionFailure

if TYPE_CHECKING:
    from haywire_studio.share.pipeline.pipeline import SharePipeline
```

`_fix_strip_os` currently calls `pipeline._record(...)` — leave it as `_record` for now; Task 11 renames it.

- [ ] **Step 2: Import back into `pipeline.py`**

```python
from haywire_studio.share.pipeline.fixes import _MANIFEST_FAILURE_TYPES, _PRECONDITION_FIXES
```

Delete the moved blocks. `apply_precondition_fix` (line 410-420) is unchanged — it still reads `_PRECONDITION_FIXES.get(fix_id)`.

- [ ] **Step 3: Verify green**

```bash
uv run ruff format packages/haywire-studio/src/haywire_studio/
uv run pytest tests/share_pipeline/test_preconditions.py -q
uv run mypy packages/haywire-studio/src/
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "refactor(share-pipeline): extract precondition fix handlers into fixes.py"
```

---

### Task 9: Extract steps 1–3 (`preconditions`, `drift`, `version`)

Each step module holds free functions taking `pipeline` as the first argument — the pattern `fixes.py` already uses. `SharePipeline`'s public methods stay, becoming one-line delegations.

**Files:**
- Create: `share/pipeline/steps/__init__.py`, `steps/preconditions.py`, `steps/drift.py`, `steps/version.py`
- Modify: `share/pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_preconditions.py`, `test_drift_step.py`, `test_bump_step.py`

**Interfaces:**
- Consumes: `pipeline.results`, `pipeline.errors`, `share.drift`, `share.manifest`, `share.git`, `share.barn`.
- Produces (each takes `pipeline: SharePipeline` first):
  - `steps.preconditions`: `check(pipeline) -> PreconditionsReport`, `_detached_head_remedy(pipeline) -> str`
  - `steps.drift`: `check(pipeline) -> DriftReport`, `apply_union(pipeline, report) -> list[Path]`, `apply_replace(pipeline, report) -> list[Path]`, `_written_paths(pipeline, lib_dir) -> list[Path]`
  - `steps.version`: `check_tag_available(pipeline, version) -> None`, `apply_bump(pipeline, spec) -> BumpResult`

- [ ] **Step 1: Create the steps package**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio/share/pipeline
mkdir -p steps
touch steps/__init__.py
```

Leave `steps/__init__.py` empty.

- [ ] **Step 2: Create `steps/preconditions.py`**

Move the **body** of `check_preconditions` (`pipeline.py:185-375`, 191 lines) and `_detached_head_remedy` (`377-401`) into module-level functions. Convert `self` → `pipeline` throughout:

```python
def check(pipeline: SharePipeline) -> PreconditionsReport:
    """Verify everything needed to publish, collecting ALL failures.

    Reports rather than raises so the wizard's first panel can explain why a
    workspace cannot be shared. The menu item is always enabled — a disabled
    one cannot carry a tooltip, since the design guide's disabled state
    includes pointer-events: none.
    """
    # ... body verbatim, with every `self.` replaced by `pipeline.`
```

Carry the module-level constants `GIT_INSTALL_HINT` (`pipeline.py:76-80`) and `_NO_REMOTE_HINT` (`82`) — but **re-export `GIT_INSTALL_HINT` from `pipeline.py`**, since `share/pipeline/__init__.py` exports it publicly.

- [ ] **Step 3: Create `steps/drift.py` and `steps/version.py`**

`steps/drift.py` ← `pipeline.py:435-450` (`check_drift`), `452-461` (`apply_drift_union`), `463-492` (`apply_drift_replace`), `498-510` (`_drift_written_paths`). Same `self` → `pipeline` conversion.

`steps/version.py` ← `pipeline.py:522-540` (`check_tag_available`), `542-581` (`apply_bump`).

Note `acknowledge_drift` (`494-496`, 3 lines) and `plan_version` (`518-520`, 3 lines) are trivial state setters — **leave them on the class**.

- [ ] **Step 4: Convert the class methods to delegations**

```python
    def check_preconditions(self) -> PreconditionsReport:
        """Verify everything needed to publish, collecting ALL failures."""
        return steps_preconditions.check(self)

    def check_drift(self) -> DriftReport:
        """Scan every barn library for dependency drift."""
        return steps_drift.check(self)

    def apply_drift_union(self, report: DriftReport) -> list[Path]:
        """Additively merge detected dependencies into what is declared."""
        return steps_drift.apply_union(self, report)

    def apply_drift_replace(self, report: DriftReport) -> list[Path]:
        """Overwrite declared dependencies with exactly what was detected."""
        return steps_drift.apply_replace(self, report)

    def check_tag_available(self, version: str) -> None:
        """Raise TagCollisionError if the version tag already exists."""
        steps_version.check_tag_available(self, version)

    def apply_bump(self, spec: str) -> BumpResult:
        """Write the new version to every barn library and refresh the lock."""
        return steps_version.apply_bump(self, spec)
```

with imports:

```python
from haywire_studio.share.pipeline.steps import drift as steps_drift
from haywire_studio.share.pipeline.steps import preconditions as steps_preconditions
from haywire_studio.share.pipeline.steps import version as steps_version
```

- [ ] **Step 5: Repoint the string patches for these steps**

The moved functions now resolve names from their *own* module namespace. Update:

```bash
grep -rn "share_pipeline.pipeline.detect_share_drift\|share_pipeline.pipeline.apply_drift_fix\|share_pipeline.pipeline.detect_deps" tests/
```

Replace in `tests/share_pipeline/test_drift_step.py` and `tests/test_share_wizard_ui.py`:

```python
# before
patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", ...)
patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix", ...)
patch("haywire_studio.share_pipeline.pipeline.detect_deps", ...)
# after
patch("haywire_studio.share.pipeline.steps.drift.detect_share_drift", ...)
patch("haywire_studio.share.pipeline.steps.drift.apply_drift_fix", ...)
patch("haywire_studio.share.pipeline.steps.drift.detect_deps", ...)
```

In `tests/share_pipeline/test_bump_step.py`:

```python
patch("haywire_studio.share.pipeline.steps.version.refresh_lockfile", ...)
```

In `tests/share_pipeline/test_preconditions.py`, `git_remote` / `git` patches:

```python
patch("haywire_studio.share.pipeline.steps.preconditions.git_remote", ...)
```

- [ ] **Step 6: Verify green**

```bash
uv run ruff format packages/ tests/
uv run pytest tests/share_pipeline/ tests/test_share_wizard_ui.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: all pass. A `patch` target that no longer exists raises `AttributeError` — loud, not silent.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(share-pipeline): extract preconditions, drift, and version steps"
```

---

### Task 10: Extract steps 4–6 (`docs`, `commit`, `push`)

**Files:**
- Create: `share/pipeline/steps/docs.py`, `steps/commit.py`, `steps/push.py`
- Modify: `share/pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_docs_step.py`, `test_commit_step.py`, `test_push_step.py`

**Interfaces:**
- Produces (each takes `pipeline: SharePipeline` first):
  - `steps.docs`: `command(pipeline, json_path=None) -> list[str]`, `apply(pipeline, ...) -> DocsResult` (async), `write_set(pipeline) -> list[Path]`
  - `steps.commit`: `apply_marketstall(pipeline) -> MarketstallWriteResult`, `barn_dirty_files(pipeline) -> list[BarnDirtyFile]`, `plan(pipeline, *, message=None) -> CommitPlan`, `_diffstat(pipeline, files) -> str`, `apply(pipeline, ...) -> CommitResult`
  - `steps.push`: `current_branch(pipeline) -> str | None`, `command(pipeline) -> list[str]`, `verify_allowed(pipeline) -> None`, `apply(pipeline, ...) -> PushResult` (async)

- [ ] **Step 1: Create the three step modules**

`steps/docs.py` ← `pipeline.py:585-606` (`docs_command`), `608-647` (`apply_docs`, async), `649-677` (`docs_write_set`).

`steps/commit.py` ← `pipeline.py:681-696` (`apply_marketstall`), `698-736` (`barn_dirty_files`), `738-757` (`plan_commit`), `759-808` (`_diffstat`), `866-916` (`apply_commit`).

`steps/push.py` ← `pipeline.py:810-822` (`current_branch`), `824-836` (`push_command`), `838-864` (`verify_push_allowed`), `920-957` (`apply_push`, async).

Same `self` → `pipeline` conversion. **Preserve `apply_docs`'s working-tree restore on failure** (`8e8e95eb`) and `_diffstat`'s git-status-based label classification (`ffa51e45`) exactly — both were bug fixes.

- [ ] **Step 2: Convert to delegations**

```python
    def docs_command(self, json_path: Path | None = None) -> list[str]:
        """The `haywire docs --all` argv this step will run."""
        return steps_docs.command(self, json_path)

    async def apply_docs(self, on_line: Callable[[str], None] | None = None) -> DocsResult:
        """Regenerate every library's docs in a subprocess."""
        return await steps_docs.apply(self, on_line)

    def docs_write_set(self) -> list[Path]:
        """Every doc file the generator may have written."""
        return steps_docs.write_set(self)
```

Match each existing signature **exactly** — check the current definition before writing the delegation. Follow the same shape for commit and push.

- [ ] **Step 3: Repoint the string patches**

```bash
grep -rn "share_pipeline.pipeline\.\|share.pipeline.pipeline\." tests/ | grep patch
```

Replace:

```python
# docs step
patch("haywire_studio.share.pipeline.steps.docs.run_streaming", ...)
# push step
patch("haywire_studio.share.pipeline.steps.push.git_remote_streaming", ...)
patch("haywire_studio.share.pipeline.steps.push.git_remote", ...)
# commit step
patch("haywire_studio.share.pipeline.steps.commit.git", ...)
```

Patches targeting **methods** (`"...pipeline.SharePipeline.apply_docs"`, `"...SharePipeline.apply_push"`) stay on the class — update only the module prefix to `haywire_studio.share.pipeline.pipeline.SharePipeline.<method>`.

- [ ] **Step 4: Verify green**

```bash
uv run ruff format packages/ tests/
uv run pytest tests/share_pipeline/ tests/test_share_wizard_ui.py tests/test_share_cli.py -q
uv run mypy packages/haywire-studio/src/
```

- [ ] **Step 5: Check the class shrank as intended**

```bash
grep -c "    def \|    async def " packages/haywire-studio/src/haywire_studio/share/pipeline/pipeline.py
wc -l packages/haywire-studio/src/haywire_studio/share/pipeline/pipeline.py
```

Expected: same method count as before (public surface unchanged), but the file well under 400 lines (from 957).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(share-pipeline): extract docs, commit, and push steps"
```

---

### Task 11: Rename `_record` → `record`

Six step modules now call `pipeline._record(...)` across a module boundary. A leading underscore that everything calls is a lie about the interface.

**Files:**
- Modify: `share/pipeline/pipeline.py`, all six `steps/*.py`, `share/pipeline/fixes.py`
- Test: any test referencing `_record`

**Interfaces:**
- Produces: `SharePipeline.record(paths: list[Path]) -> list[Path]` — the step-facing write-set API.

- [ ] **Step 1: Find every reference**

```bash
grep -rn "_record" packages/haywire-studio/src/haywire_studio/share/ tests/ barn/ --include="*.py" | grep -v __pycache__
```

- [ ] **Step 2: Rename the method and update its docstring**

In `share/pipeline/pipeline.py`:

```python
    def record(self, paths: list[Path]) -> list[Path]:
        """Append *paths* to the accumulated write set, de-duplicated, and return them.

        Public to the step modules in ``steps/`` — they call this to register
        what they wrote. Not part of the CLI/wizard surface: callers drive the
        pipeline through the step methods and read ``written``.

        Step 5 stages exactly ``self.written``, so a duplicate would make the
        commit preview lie about how many files changed.
        """
```

- [ ] **Step 3: Update every call site**

Replace `pipeline._record(` → `pipeline.record(` and `self._record(` → `self.record(` at every location from Step 1.

- [ ] **Step 4: Verify green**

```bash
uv run ruff format packages/ tests/
uv run pytest tests/share_pipeline/ tests/test_share_*.py -q
uv run mypy packages/haywire-studio/src/
grep -rn "_record" packages/haywire-studio/src/haywire_studio/share/ --include="*.py"
```

Expected: tests pass; the final grep returns **no output**.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(share-pipeline): rename _record to record, the step-facing write-set API"
```

---

### Task 12: Move `share_cli.py` and remove the shim

**Files:**
- Move: `share_cli.py` → `share/cli.py`
- Delete: `share_pipeline.py` (the Task 7 shim)
- Modify: `app.py:434`
- Test: `tests/test_share_cli.py`, `tests/share_pipeline/test_public_surface.py`

- [ ] **Step 1: Move the CLI**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-studio/src/haywire_studio
git mv share_cli.py share/cli.py
git rm share_pipeline.py
```

- [ ] **Step 2: Fix imports in `share/cli.py`**

`share_cli.py:19` → `from haywire_studio.share.url import derive_share_url_only`
`share_cli.py:20` → `from haywire_studio.share.pipeline import (`

- [ ] **Step 3: Repoint `app.py`**

`app.py:434`:

```python
        from haywire_studio.share.cli import run_share_cli
```

- [ ] **Step 4: Repoint remaining test imports**

```bash
grep -rn "haywire_studio.share_pipeline\|haywire_studio.share_cli" tests/ packages/ barn/ --include="*.py" | grep -v __pycache__
```

Replace every `haywire_studio.share_pipeline` → `haywire_studio.share.pipeline` and `haywire_studio.share_cli` → `haywire_studio.share.cli`. This is the commit where the shim's grace period ends, so the grep must come back empty.

- [ ] **Step 5: Update the characterization test**

In `tests/share_pipeline/test_public_surface.py`, change the two module names:

```python
    module = importlib.import_module("haywire_studio.share.pipeline")
```

(in `test_pipeline_vocabulary_is_importable` and `test_share_error_hierarchy_is_intact`).

- [ ] **Step 6: Verify no stale references anywhere**

```bash
grep -rn "share_pipeline\|share_cli\|haywire_studio.gitcmd\|haywire_studio\.barn" --include="*.py" packages/ barn/ tests/ scripts/ | grep -v __pycache__
```

Expected: **no output**. (`tests/share_pipeline/` as a *directory* name is fine and stays — only module paths matter.)

- [ ] **Step 7: Verify green + full suite**

```bash
uv run ruff format packages/ barn/ tests/
uv run ruff check packages/haywire-studio/src/haywire_studio/
uv run pytest tests/share_pipeline/ tests/test_share_*.py tests/test_gitcmd.py tests/test_barn.py tests/test_deps_cli.py tests/studio/test_share_examples.py -q
uv run mypy packages/haywire-studio/src/
```

Expected: **300 passed + 3 from Task 1 = 303 passed**.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(share): move the CLI into the package, remove the compatibility shim"
```

---

### Task 13: Verify the import cycle is structurally impossible

The old §5 rule was enforced by a manual fresh-interpreter check. Replace it with a test.

**Files:**
- Create: `tests/share_pipeline/test_layering.py`

- [ ] **Step 1: Write the layering test**

```python
"""The share package's layering, enforced.

Replaces the hand-run `python -c "import haywire_studio.share"` check that
guarded the old import-cycle rule. Cycles are now prevented structurally: no
module inside the package imports the package root, so the root's re-exports
cannot loop back.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

_SHARE_ROOT = (
    Path(__file__).resolve().parents[2]
    / "packages/haywire-studio/src/haywire_studio/share"
)


def _module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def test_no_internal_module_imports_the_package_root() -> None:
    """The re-exports in __init__ must stay one-directional.

    An internal module importing `haywire_studio.share` would run the root
    __init__, which imports every submodule — the exact loop that made the
    old share.py/share_pipeline pair circular.
    """
    offenders: list[str] = []
    for path in sorted(_SHARE_ROOT.rglob("*.py")):
        if path.name == "__init__.py" and path.parent == _SHARE_ROOT:
            continue  # the root itself is allowed to import its submodules
        if "haywire_studio.share" in _module_imports(path):
            offenders.append(str(path.relative_to(_SHARE_ROOT)))
    assert offenders == [], f"these import the package root: {offenders}"


def test_leaf_modules_have_no_in_package_dependencies() -> None:
    """git.py and barn.py are the bottom layer: everything may depend on
    them, so they must depend on nothing here."""
    for leaf in ("git.py", "barn.py"):
        imports = _module_imports(_SHARE_ROOT / leaf)
        internal = {name for name in imports if name.startswith("haywire_studio")}
        assert internal == set(), f"{leaf} must not import {internal}"


def test_every_share_module_imports_standalone() -> None:
    """Each module must import in a fresh interpreter without its siblings
    being imported first — the regression the old §5 rule guarded by hand."""
    modules = []
    for path in sorted(_SHARE_ROOT.rglob("*.py")):
        rel = path.relative_to(_SHARE_ROOT).with_suffix("")
        parts = [p for p in rel.parts if p != "__init__"]
        modules.append(".".join(["haywire_studio.share", *parts]))

    for name in modules:
        result = subprocess.run(
            [sys.executable, "-c", f"import {name}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, f"{name} failed to import:\n{result.stderr}"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/share_pipeline/test_layering.py -v`
Expected: **3 passed**. A failure names the offending module — fix the import rather than the test.

- [ ] **Step 3: Commit**

```bash
git add tests/share_pipeline/test_layering.py
git commit -m "test(share): enforce package layering, replacing the manual cycle check"
```

---

### Task 14: Step-divergence test (the one genuinely new test — TDD applies)

The wizard has 8 UI steps; the pipeline has 6. `checked` and `done` are UI-only. Nothing currently stops a step being added on one side and forgotten on the other.

**Files:**
- Create: `tests/share_pipeline/test_step_sequence.py`

**Interfaces:**
- Consumes: `_share_wizard.STEPS`, `share.pipeline.steps`.

- [ ] **Step 1: Write the test (expect it to FAIL first — this one is TDD)**

```python
"""The wizard's step sequence and the pipeline's step modules must agree.

Adding a step means touching the pipeline, the wizard's STEPS tuple, its
titles, its render dispatch, and the CLI. Nothing enforces that; this test
does, by failing when one side gains a step the other never learned about.
Deliberately hardcoded rather than derived — a six-step publish flow that
changes shape roughly never does not need a registry, but it does need a
tripwire.
"""

from __future__ import annotations

import pkgutil

from haywire_studio.share.pipeline import steps as steps_pkg

# Steps the wizard renders that have no pipeline counterpart.
_UI_ONLY_STEPS = frozenset({"checked", "done"})

# The pipeline's six steps, in order. Keep in sync with
# docs/architecture/sharing/share-pipeline-arch.md §2.
_EXPECTED_PIPELINE_STEPS = (
    "preconditions",
    "drift",
    "version",
    "docs",
    "commit",
    "push",
)


def _pipeline_step_modules() -> set[str]:
    return {m.name for m in pkgutil.iter_modules(steps_pkg.__path__)}


def test_pipeline_has_exactly_the_expected_step_modules() -> None:
    assert _pipeline_step_modules() == set(_EXPECTED_PIPELINE_STEPS)


def test_wizard_covers_every_pipeline_step() -> None:
    from haybale_marketplace.editors._share_wizard import STEPS

    missing = set(_EXPECTED_PIPELINE_STEPS) - set(STEPS)
    assert missing == set(), f"the wizard renders no panel for: {missing}"


def test_wizard_adds_only_known_ui_only_steps() -> None:
    from haybale_marketplace.editors._share_wizard import STEPS

    extra = set(STEPS) - set(_EXPECTED_PIPELINE_STEPS) - _UI_ONLY_STEPS
    assert extra == set(), (
        f"the wizard has steps the pipeline does not know about: {extra}. "
        "Add a pipeline step, or list it in _UI_ONLY_STEPS if it is pure UI."
    )


def test_wizard_step_order_follows_the_pipeline() -> None:
    """UI-only steps may be interleaved, but the pipeline steps the wizard
    does render must appear in pipeline order."""
    from haybale_marketplace.editors._share_wizard import STEPS

    rendered = [s for s in STEPS if s in _EXPECTED_PIPELINE_STEPS]
    assert rendered == list(_EXPECTED_PIPELINE_STEPS)
```

- [ ] **Step 2: Run it — it must FAIL if steps/ is incomplete**

Run: `uv run pytest tests/share_pipeline/test_step_sequence.py -v`
Expected: **4 passed** if Tasks 9–10 created exactly the six modules. If `test_pipeline_has_exactly_the_expected_step_modules` fails, the step extraction is incomplete — fix `steps/`, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/share_pipeline/test_step_sequence.py
git commit -m "test(share): pin the wizard's step sequence against the pipeline's"
```

---

### Task 15: Update the documentation

**Files:**
- Modify: `docs/architecture/sharing/share-pipeline-arch.md` (30 refs + delete §5)
- Modify: `docs/reference/glossary.md` (3 citations)

- [ ] **Step 1: Delete §5 entirely**

Remove the whole `## 5. The import-cycle constraint` section (through to `## 6.`) and renumber the sections after it. The constraint no longer exists — the layering makes cycles structurally impossible, and `tests/share_pipeline/test_layering.py` enforces it. **Do not** replace it with a history note: architecture docs describe the current solution only.

Update the frontmatter `scope:` line, dropping the cycle clause:

```yaml
scope: SharePipeline's step-by-step mechanics, the error taxonomy, the default-branch publishing rule, and the current CI-facing tooling
```

- [ ] **Step 2: Update every module citation**

```bash
grep -n "share_pipeline\|share\.py\|share_cli\|gitcmd\|haywire_studio\.barn" docs/architecture/sharing/share-pipeline-arch.md
```

Apply: `haywire_studio.share_pipeline.pipeline` → `haywire_studio.share.pipeline.pipeline` · `share.py` → the specific new module (`share/drift/detect.py`, `share/manifest/reader.py`, …) · `haywire_studio.gitcmd` → `haywire_studio.share.git` · `haywire_studio.barn` → `haywire_studio.share.barn`.

In §1, note that each step's implementation lives in `share/pipeline/steps/<step>.py` and `SharePipeline` delegates to it.

- [ ] **Step 3: Update the three glossary citations**

`docs/reference/glossary.md`:
- **Drift gate** (line ~233): `haywire_studio.share_pipeline` → `haywire_studio.share.pipeline`; `haywire_studio.packaging.deps` unchanged (it did not move).
- **DepDrift** (line ~256): "Dataclass from `haywire_studio.share`" → "Dataclass from `haywire_studio.share.drift.model`".
- **ShareError** (line ~257): `haywire_studio.share_pipeline.errors` → `haywire_studio.share.pipeline.errors`.

No term *definitions* change — the vocabulary survives the move intact.

- [ ] **Step 4: Verify the docs build and no stale refs remain**

```bash
grep -rn "share_pipeline\|haywire_studio.gitcmd\|haywire_studio\.barn\b" docs/ --include="*.md" | grep -v "superpowers/plans"
uv run mkdocs build --strict 2>&1 | tail -5
```

Expected: the grep returns nothing; mkdocs builds without warnings.

- [ ] **Step 5: Commit**

```bash
git add docs/
git commit -m "docs(share): update module citations, drop the retired import-cycle section"
```

---

### Task 16: Final verification

- [ ] **Step 1: Full quality suite**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: all clean. CI runs both ruff commands — they catch disjoint problems.

- [ ] **Step 2: Full test suite**

```bash
uv run pytest -m "not browser and not perf" -q
```

Expected: green. Then the browser harness, which covers the wizard UI:

```bash
uv run pytest tests/test_share_wizard_ui.py tests/test_share_wizard_menu.py -q
```

- [ ] **Step 3: Smoke-test the CLI end to end**

```bash
uv run haywire share --help
uv run haywire deps check
```

Expected: `--help` prints the share usage; `deps check` runs the drift gate and exits 0 or 1 (both valid — it reports on this repo).

- [ ] **Step 4: Confirm the size goal was met**

```bash
find packages/haywire-studio/src/haywire_studio/share -name "*.py" | xargs wc -l | sort -n | tail -20
```

Expected: no file over ~400 lines (from two at ~950).

- [ ] **Step 5: Run the rename checker**

The ~60 string patches are exactly what it exists to catch:

```
/check-rename
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "refactor(share): complete the share package restructure"
```

---

## Deferred (explicitly out of scope)

Agreed during design; **do not** start these here:

1. **Wizard restructure** — `_share_wizard.py` (785 lines) splits into a `_share_wizard/` sub-package (state machine / panels / chrome / async helpers / copy). Only its one import line changes in this plan.
2. **Constructor seams** — inject `detect_drift`, `apply_fix`, `refresh_lockfile` into `SharePipeline.__init__` so tests stop patching by string. A `StepContext` object is the natural shape.
3. **Narrow `share/__init__.py`** — curate the re-exports to a real public API once the wizard is restructured.
4. **`haywire_studio/cli/` folder** — collect all five subcommand entry points (`init`, `share`, `rename`, `deps`, `docs`).

## Rollback

Every task is one commit and the suite is green at each. To undo any task: `git revert <sha>`. To abandon entirely: `git reset --hard <sha-before-task-1>`. Because moves use `git mv`, `git log --follow <new-path>` still shows the full history.
