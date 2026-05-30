# Versioning Pre-Release Migration & Bump Script — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate every publishable package to version `0.0.1` with `~=0.0.1` inter-package constraints, add the `[tool.haywire.release]` canonical config to the root `pyproject.toml`, and ship `scripts/bump_version.py` so future releases can patch all versions and constraints in one command.

**Architecture:** Two parts. **Part 1 (manual migration, one-time):** edit each publishable package's `pyproject.toml` from `version = "0.1.0"` → `"0.0.1"` and rewrite `>=0.1.0` deps to `~=0.0.1` (Tier 1/2 only). Add `[tool.haywire.release]` to the root pyproject as the machine-readable list of publishable packages. **Part 2 (bump script):** a TDD-driven Python CLI that reads `[tool.haywire.release]`, walks each listed package's `pyproject.toml`, rewrites the `version = "..."` line and any `~=` constraints on sibling packages to the new version, prints a unified diff, and asks for confirmation before writing. The script uses regex-based surgical edits (no full TOML round-trip) to preserve formatting, comments, and dependency ordering.

**Tech Stack:** Python 3.10+, `tomllib` (stdlib, read-only) for `[tool.haywire.release]` parsing, `re` for surgical line edits, `argparse` for the CLI, `difflib` for the preview diff, `pytest` for tests.

**Scope reference:** This plan covers spec sections §1 (lockstep versioning), §2 (pyproject.toml is source of truth — already implemented via T1), §3 (first release = `0.0.1`), §4 (`~=X.Y.Z` constraint format), §5 (`[tool.haywire.release]` machine-readable canonical list), and implementation task **T2** plus the pre-release migration row of the "Files changed at first migration" table. T1 is already complete; this plan deliberately does NOT cover T3/T4 (CI), T5–T13 (separate plans).

---

## File Structure

### Files modified (Part 1 — pre-release migration, no script involved)

- `pyproject.toml` (root) — add `[tool.haywire.release]` block listing `publish_order` and excluding non-publishable packages.
- `packages/haywire-core/pyproject.toml` — `version = "0.0.1"`.
- `packages/haywire-studio/pyproject.toml` — `version = "0.0.1"`, `haywire-core>=0.1.0` → `haywire-core~=0.0.1`.
- `barn/haybale-core/pyproject.toml` — `version = "0.0.1"`, `haywire-core>=0.1.0` → `haywire-core~=0.0.1`.
- `barn/haybale-studio/pyproject.toml` — `version = "0.0.1"`, two deps to `~=0.0.1`.
- `barn/haybale-graph-editor/pyproject.toml` — `version = "0.0.1"`, two deps to `~=0.0.1`.
- `barn/haybale-haystack/pyproject.toml` — `version = "0.0.1"`, four deps to `~=0.0.1`.
- `barn/haybale-example/pyproject.toml` — `version = "0.0.1"`, two deps to `~=0.0.1`.
- `barn/haybale-visiongraph/pyproject.toml` — `version = "0.0.1"`, two haybale/haywire deps to `~=0.0.1` (NOT `visiongraph[all]`).
- `barn/haybale-testing/pyproject.toml` — `version = "0.0.1"`, three deps to `~=0.0.1`. **Internal package: stays at version but NOT in `[tool.haywire.release]`'s `publish_order`.**
- `barn/haybale-TEST_A/pyproject.toml` — `version = "0.0.1"`, one dep to `~=0.0.1`. **Internal: not in `publish_order`.**

### Files created (Part 2 — bump script)

- `scripts/bump_version.py` — the CLI.
- `scripts/__init__.py` — empty marker so `scripts` is importable as a package for testing. **Check first — only create if missing.**
- `tests/scripts/__init__.py` — empty marker. **Check first — only create if missing.**
- `tests/scripts/test_bump_version.py` — unit tests.
- `tests/scripts/fixtures/sample_root_pyproject.toml` — fixture: a stand-in for the workspace root with `[tool.haywire.release]`.
- `tests/scripts/fixtures/sample_package_pyproject.toml` — fixture: a stand-in publishable package's pyproject.

### Spec & docs

- `docs/reference/publish_releases.md` — referenced from the spec (§5) as the canonical operational doc. **Out of scope for this plan** (the spec calls it operational procedure; will be written when T8 — the `/haywire-release` skill — is built). This plan only ships the script and migration.

---

## Approach Rationale (read before starting)

**Why regex, not TOML round-trip:** `pyproject.toml` files are hand-authored and contain comments, blank-line groupings, and aligned formatting that matter. The only stdlib TOML lib (`tomllib`) is read-only; `tomli_w` (write) would reflow the file and lose comments. Since the bump script only edits two narrow line patterns (`version = "X.Y.Z"` at top level and `"<pkg-name>~=X.Y.Z"` inside `dependencies = [...]`), surgical regex edits are robust and preserve the file exactly otherwise.

**Why `[tool.haywire.release]` lives in the root pyproject:** Spec §5 makes the root pyproject the machine-readable canonical list. The bump script, CI workflow (separate plan), and marketstall generator (separate plan) all read from this single block. Keeping it in `pyproject.toml` (already loaded by `uv`/tooling) means no new file types to ship.

**Why version `0.0.1` is hardcoded into the migration, not via the script:** The script's job is to take an old version → new version. The initial migration goes from `0.1.0` → `0.0.1` (a *downgrade*), which is the same surgical edit but easier to do manually as a one-time step, before the script exists or works on a clean baseline. The script's tests can then assume the baseline is `0.0.1` and bump forward.

---

## Task list

### Task 1: Baseline verification

**Files:** read-only.

- [ ] **Step 1: Confirm pre-edit baseline is clean**

Run from repo root:

```bash
uv run ruff check .
uv run pytest -m "not integration" -q
```

Expected: both pass. CLAUDE.md states the baseline is clean — if either fails, **stop and notify the user** before proceeding (per CLAUDE.md's pre-edit baseline rule).

- [ ] **Step 2: Snapshot the current versions for verification**

```bash
for f in packages/*/pyproject.toml barn/*/pyproject.toml; do
    echo "=== $f ==="
    grep -E '^(name|version) =' "$f"
done
```

Expected: every file shows `version = "0.1.0"`. Note any deviation; the migration steps below assume `0.1.0` as the starting point.

---

### Task 2: Add `[tool.haywire.release]` to root pyproject

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Append the canonical release config**

Open `pyproject.toml` and append at the end of the file (after the existing `[tool.pytest.ini_options]` block):

```toml

[tool.haywire.release]
# Canonical machine-readable list of releasable packages.
# Consumed by: scripts/bump_version.py (this repo),
#              scripts/generate_marketstall.py (separate plan),
#              .github/workflows/publish.yml (separate plan).
# Order is significant for the publish workflow: dependencies first.
# If this disagrees with the §5 table in
# internals/specs/versioning-and-publishing.md, this block wins.

# Packages published to PyPI on every release tag, in dependency order.
publish_order = [
    "haywire-core",
    "haywire-studio",
    "haybale-core",
    "haybale-studio",
    "haybale-graph-editor",
    "haybale-haystack",
    "haybale-example",
]

# Packages versioned in lockstep with the release but NOT published.
# The bump script updates these too so internal users stay coherent.
# - haybale-visiongraph: Tier 2 git-only (binary deps, deferred from PyPI).
# - haybale-testing, haybale-TEST_A: Tier 3 internal test fixtures.
lockstep_unpublished = [
    "haybale-visiongraph",
    "haybale-testing",
    "haybale-TEST_A",
]
```

- [ ] **Step 2: Verify TOML parses cleanly**

```bash
uv run python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('pyproject.toml').read_text()); print(d['tool']['haywire']['release'])"
```

Expected: dict with `publish_order` (7 entries) and `lockstep_unpublished` (3 entries).

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add [tool.haywire.release] canonical package list

Machine-readable source of truth for which packages are published and
in what order. Consumed by the upcoming bump script, marketstall
generator, and CI workflow.

Refs spec internals/specs/versioning-and-publishing.md §5."
```

---

### Task 3: Migrate `haywire-core` to `0.0.1`

**Files:**
- Modify: `packages/haywire-core/pyproject.toml`

- [ ] **Step 1: Patch version**

In `packages/haywire-core/pyproject.toml`, change:

```toml
version = "0.1.0"
```

to:

```toml
version = "0.0.1"
```

(No inter-package deps in this file — it's the root of the dependency tree.)

- [ ] **Step 2: Verify the wheel still builds**

```bash
uv build --package haywire-core 2>&1 | tail -5
```

Expected: a successful build line ending in `dist/haywire_core-0.0.1-*.whl` and `.tar.gz`. If the build fails, revert and stop.

---

### Task 4: Migrate `haywire-studio` to `0.0.1`

**Files:**
- Modify: `packages/haywire-studio/pyproject.toml`

- [ ] **Step 1: Patch version and constraint**

In `packages/haywire-studio/pyproject.toml`, change:

```toml
version = "0.1.0"
...
dependencies = [
    "haywire-core>=0.1.0",
]
```

to:

```toml
version = "0.0.1"
...
dependencies = [
    "haywire-core~=0.0.1",
]
```

- [ ] **Step 2: Verify**

```bash
uv build --package haywire-studio 2>&1 | tail -5
```

Expected: builds cleanly.

---

### Task 5: Migrate `haybale-core` to `0.0.1`

**Files:**
- Modify: `barn/haybale-core/pyproject.toml`

- [ ] **Step 1: Patch**

Change `version = "0.1.0"` → `"0.0.1"` and the single dep `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`.

- [ ] **Step 2: Verify**

```bash
uv build --package haybale-core 2>&1 | tail -5
```

Expected: clean build.

---

### Task 6: Migrate `haybale-studio` to `0.0.1`

**Files:**
- Modify: `barn/haybale-studio/pyproject.toml`

- [ ] **Step 1: Patch**

Change `version = "0.1.0"` → `"0.0.1"`. In `dependencies`, change `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"` and `"haywire-studio>=0.1.0"` → `"haywire-studio~=0.0.1"`. Leave `"packaging"` (no version pin) untouched.

- [ ] **Step 2: Verify**

```bash
uv build --package haybale-studio 2>&1 | tail -5
```

---

### Task 7: Migrate `haybale-graph-editor` to `0.0.1`

**Files:**
- Modify: `barn/haybale-graph-editor/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies`:
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`
- `"haywire-studio>=0.1.0"` → `"haywire-studio~=0.0.1"`

- [ ] **Step 2: Verify**

```bash
uv build --package haybale-graph-editor 2>&1 | tail -5
```

---

### Task 8: Migrate `haybale-haystack` to `0.0.1`

**Files:**
- Modify: `barn/haybale-haystack/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies`, rewrite all four sibling deps to `~=0.0.1`:
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`
- `"haywire-studio>=0.1.0"` → `"haywire-studio~=0.0.1"`
- `"haybale-studio>=0.1.0"` → `"haybale-studio~=0.0.1"`
- `"haybale-graph-editor>=0.1.0"` → `"haybale-graph-editor~=0.0.1"`

- [ ] **Step 2: Verify**

```bash
uv build --package haybale-haystack 2>&1 | tail -5
```

---

### Task 9: Migrate `haybale-example` to `0.0.1`

**Files:**
- Modify: `barn/haybale-example/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies`:
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`
- `"haybale-core>=0.1.0"` → `"haybale-core~=0.0.1"`

- [ ] **Step 2: Verify**

```bash
uv build --package haybale-example 2>&1 | tail -5
```

---

### Task 10: Migrate `haybale-visiongraph` to `0.0.1`

**Files:**
- Modify: `barn/haybale-visiongraph/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies`, rewrite the two sibling deps only — DO NOT touch `"visiongraph[all]"` (external):
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`
- `"haybale-core>=0.1.0"` → `"haybale-core~=0.0.1"`

- [ ] **Step 2: Verify the file parses (no build — this package has binary deps)**

```bash
uv run python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('barn/haybale-visiongraph/pyproject.toml').read_text()); print(d['project']['version'], d['project']['dependencies'])"
```

Expected: `0.0.1 ['haywire-core~=0.0.1', 'haybale-core~=0.0.1', 'visiongraph[all]']`.

---

### Task 11: Migrate `haybale-testing` to `0.0.1`

**Files:**
- Modify: `barn/haybale-testing/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies` (three entries):
- `"haybale-core>=0.1.0"` → `"haybale-core~=0.0.1"`
- `"haybale-graph-editor>=0.1.0"` → `"haybale-graph-editor~=0.0.1"`
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`

- [ ] **Step 2: Verify**

```bash
uv run python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('barn/haybale-testing/pyproject.toml').read_text()); print(d['project']['version'], d['project']['dependencies'])"
```

Expected version `0.0.1` and all three deps with `~=0.0.1`.

---

### Task 12: Migrate `haybale-TEST_A` to `0.0.1`

**Files:**
- Modify: `barn/haybale-TEST_A/pyproject.toml`

- [ ] **Step 1: Patch**

`version = "0.1.0"` → `"0.0.1"`. In `dependencies` (one entry):
- `"haywire-core>=0.1.0"` → `"haywire-core~=0.0.1"`

- [ ] **Step 2: Verify**

```bash
uv run python -c "import tomllib, pathlib; d = tomllib.loads(pathlib.Path('barn/haybale-TEST_A/pyproject.toml').read_text()); print(d['project']['version'], d['project']['dependencies'])"
```

Expected: `0.0.1 ['haywire-core~=0.0.1']`.

---

### Task 13: Full-repo sanity after migration

**Files:** read-only.

- [ ] **Step 1: Re-sync the workspace**

```bash
uv sync --dev
```

Expected: completes without errors. Workspace `[tool.uv.sources]` overrides the version constraints inside the workspace, so `uv sync` resolves the editable installs even though the constraints now say `~=0.0.1` while the dev environment shares one venv.

- [ ] **Step 2: Verify all `@library(version=…)` calls still resolve via importlib.metadata**

```bash
uv run python -c "from importlib.metadata import version; pkgs = ['haywire-core','haywire-studio','haybale-core','haybale-studio','haybale-graph-editor','haybale-haystack','haybale-example','haybale-visiongraph','haybale-testing','haybale-TEST_A']; [print(p, version(p)) for p in pkgs]"
```

Expected: every package prints `0.0.1`. If any prints `0.1.0` or errors, the corresponding pyproject was missed.

- [ ] **Step 3: Run the fast test suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: all tests pass. The baseline was clean (Task 1 step 1), so any new failures are caused by this migration. CLAUDE.md: "Anything new is yours."

- [ ] **Step 4: Re-run ruff**

```bash
uv run ruff check .
```

Expected: clean.

- [ ] **Step 5: Commit the migration**

```bash
git add packages/*/pyproject.toml barn/*/pyproject.toml uv.lock
git commit -m "chore: migrate all packages to v0.0.1 with ~= constraints

Pre-release migration per versioning spec §3 and §4. Every Tier 1+2
package now versions at 0.0.1 with inter-package dependencies pinned
via PEP 440 compatible-release constraints. uv.lock refreshed.

Refs spec internals/specs/versioning-and-publishing.md §3, §4."
```

---

### Task 14: Bump script skeleton + first failing test

**Files:**
- Create: `scripts/bump_version.py`
- Create: `tests/scripts/__init__.py` (only if missing)
- Create: `tests/scripts/test_bump_version.py`
- Create: `tests/scripts/fixtures/sample_root_pyproject.toml`
- Create: `tests/scripts/fixtures/sample_package_pyproject.toml`

- [ ] **Step 1: Create test fixtures**

Create `tests/scripts/fixtures/sample_root_pyproject.toml`:

```toml
[project]
name = "fake-workspace"
version = "0.0.0"

[tool.haywire.release]
publish_order = [
    "alpha-pkg",
    "beta-pkg",
]
lockstep_unpublished = [
    "gamma-pkg",
]
```

Create `tests/scripts/fixtures/sample_package_pyproject.toml`:

```toml
[project]
name = "alpha-pkg"
version = "0.0.1"
description = "test fixture"

dependencies = [
    "external-lib>=1.0",
    "beta-pkg~=0.0.1",
    "gamma-pkg~=0.0.1",
    "unrelated~=3.2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Create `tests/scripts/__init__.py` if missing**

```bash
test -f tests/scripts/__init__.py || touch tests/scripts/__init__.py
```

- [ ] **Step 3: Write the first failing test**

Create `tests/scripts/test_bump_version.py`:

```python
"""Tests for scripts/bump_version.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import bump_version


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_read_release_config_returns_publishable_and_lockstep_lists(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    config = bump_version.read_release_config(root)

    assert config.publish_order == ["alpha-pkg", "beta-pkg"]
    assert config.lockstep_unpublished == ["gamma-pkg"]
    assert config.all_packages == ["alpha-pkg", "beta-pkg", "gamma-pkg"]
```

- [ ] **Step 4: Create the script with just enough scaffold for the import to resolve**

Create `scripts/__init__.py` if missing:

```bash
test -f scripts/__init__.py || touch scripts/__init__.py
```

Create `scripts/bump_version.py`:

```python
"""Bump every haywire monorepo publishable package to a new version.

Reads [tool.haywire.release] from the workspace root pyproject.toml,
then surgically edits every listed package's pyproject.toml:
  - rewrites `version = "X.Y.Z"` to the new version,
  - rewrites every `"<sibling>~=A.B.C"` dep on a known sibling to
    `"<sibling>~=<new>"`.

Prints a unified diff of all changes and asks for confirmation before
writing. Use --yes to skip the prompt (for scripted use).
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseConfig:
    publish_order: list[str]
    lockstep_unpublished: list[str]

    @property
    def all_packages(self) -> list[str]:
        return [*self.publish_order, *self.lockstep_unpublished]


def read_release_config(root_pyproject: Path) -> ReleaseConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["release"]
    return ReleaseConfig(
        publish_order=list(block["publish_order"]),
        lockstep_unpublished=list(block.get("lockstep_unpublished", [])),
    )
```

- [ ] **Step 5: Run the test and confirm it passes (we made the assertion match the fixture; this is one-shot rather than red→green because the data model is trivial)**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: PASS. If it fails, fix the import path or fixture mismatch before continuing.

- [ ] **Step 6: Commit**

```bash
git add scripts/__init__.py scripts/bump_version.py tests/scripts/
git commit -m "feat(scripts): bump_version skeleton + release config reader

Reads [tool.haywire.release] from the workspace root and exposes the
publishable + lockstep package lists. First slice of the bump script
that the upcoming release skill (T8) will wrap.

Refs spec internals/specs/versioning-and-publishing.md T2."
```

---

### Task 15: Locate each package's pyproject from its pip-distribution name

The script needs to map `"haybale-haystack"` → `barn/haybale-haystack/pyproject.toml`. Naive guess (`barn/<name>` or `packages/<name>`) works for the current layout but is fragile. Better: scan workspace members and match on `[project] name`.

**Files:**
- Modify: `scripts/bump_version.py`
- Modify: `tests/scripts/test_bump_version.py`
- Modify: `tests/scripts/fixtures/sample_root_pyproject.toml`

- [ ] **Step 1: Extend the root fixture with a workspace block**

Replace `tests/scripts/fixtures/sample_root_pyproject.toml` entirely with:

```toml
[project]
name = "fake-workspace"
version = "0.0.0"

[tool.uv.workspace]
members = [
    "subdir-a/*",
    "subdir-b/*",
]

[tool.haywire.release]
publish_order = [
    "alpha-pkg",
    "beta-pkg",
]
lockstep_unpublished = [
    "gamma-pkg",
]
```

- [ ] **Step 2: Add a failing test for `locate_packages`**

Append to `tests/scripts/test_bump_version.py`:

```python
@pytest.mark.unit
def test_locate_packages_finds_pyprojects_by_project_name(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    # Lay out fake workspace members.
    for member_dir, pkg_name in [
        ("subdir-a/alpha", "alpha-pkg"),
        ("subdir-a/beta", "beta-pkg"),
        ("subdir-b/gamma", "gamma-pkg"),
        ("subdir-b/unrelated", "noise-pkg"),  # not in release config
    ]:
        d = tmp_path / member_dir
        d.mkdir(parents=True)
        (d / "pyproject.toml").write_text(
            f'[project]\nname = "{pkg_name}"\nversion = "0.0.1"\n'
        )

    config = bump_version.read_release_config(root)
    located = bump_version.locate_packages(root, config)

    assert set(located.keys()) == {"alpha-pkg", "beta-pkg", "gamma-pkg"}
    assert located["alpha-pkg"] == tmp_path / "subdir-a/alpha/pyproject.toml"
    assert located["gamma-pkg"] == tmp_path / "subdir-b/gamma/pyproject.toml"


@pytest.mark.unit
def test_locate_packages_raises_when_a_release_package_is_missing(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())
    # Only one of three packages exists on disk.
    d = tmp_path / "subdir-a/alpha"
    d.mkdir(parents=True)
    (d / "pyproject.toml").write_text('[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n')

    config = bump_version.read_release_config(root)
    with pytest.raises(bump_version.MissingPackageError) as exc:
        bump_version.locate_packages(root, config)

    assert "beta-pkg" in str(exc.value)
    assert "gamma-pkg" in str(exc.value)
```

- [ ] **Step 3: Run, confirm both new tests FAIL**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: `test_read_release_config_returns_publishable_and_lockstep_lists` PASSES, the two new tests FAIL with `AttributeError: module 'scripts.bump_version' has no attribute 'locate_packages'`.

- [ ] **Step 4: Implement `locate_packages`**

Add to `scripts/bump_version.py` (below `read_release_config`):

```python
class MissingPackageError(RuntimeError):
    """Raised when a package listed in [tool.haywire.release] has no pyproject on disk."""


def _expand_workspace_globs(root_pyproject: Path) -> list[Path]:
    """Return every pyproject.toml under [tool.uv.workspace].members globs."""
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    members = data.get("tool", {}).get("uv", {}).get("workspace", {}).get("members", [])
    root_dir = root_pyproject.parent
    found: list[Path] = []
    for pattern in members:
        # Workspace globs are filesystem patterns like "barn/*" — pyproject.toml lives inside.
        for member_dir in sorted(root_dir.glob(pattern)):
            candidate = member_dir / "pyproject.toml"
            if candidate.is_file():
                found.append(candidate)
    return found


def locate_packages(root_pyproject: Path, config: ReleaseConfig) -> dict[str, Path]:
    """Map every package name in `config.all_packages` to its pyproject.toml path."""
    wanted = set(config.all_packages)
    located: dict[str, Path] = {}
    for pyproject_path in _expand_workspace_globs(root_pyproject):
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        name = data.get("project", {}).get("name")
        if name in wanted:
            located[name] = pyproject_path
    missing = wanted - located.keys()
    if missing:
        raise MissingPackageError(
            f"release config references packages not found in workspace: {sorted(missing)}"
        )
    return located
```

- [ ] **Step 5: Run tests, confirm all pass**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: all three tests PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/bump_version.py tests/scripts/
git commit -m "feat(scripts): locate package pyprojects via workspace globs

Maps every package in [tool.haywire.release] to its on-disk pyproject
by scanning [tool.uv.workspace] members. Raises MissingPackageError
if the release config references a package not in the workspace.

Refs spec internals/specs/versioning-and-publishing.md T2."
```

---

### Task 16: Surgical version-line rewriter

**Files:**
- Modify: `scripts/bump_version.py`
- Modify: `tests/scripts/test_bump_version.py`

- [ ] **Step 1: Write failing tests for `rewrite_pyproject`**

Append to `tests/scripts/test_bump_version.py`:

```python
@pytest.mark.unit
def test_rewrite_pyproject_bumps_top_level_version() -> None:
    src = '[project]\nname = "alpha"\nversion = "0.0.1"\n'
    known_siblings = {"alpha"}

    new_text, edits = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert 'version = "0.0.2"' in new_text
    assert 'version = "0.0.1"' not in new_text
    assert any("version" in e for e in edits)


@pytest.mark.unit
def test_rewrite_pyproject_rewrites_sibling_constraints_only() -> None:
    src = (
        '[project]\n'
        'name = "alpha"\n'
        'version = "0.0.1"\n'
        'dependencies = [\n'
        '    "beta-pkg~=0.0.1",\n'
        '    "external-lib>=1.0",\n'
        '    "gamma-pkg~=0.0.1",\n'
        '    "unrelated~=3.2.0",\n'
        ']\n'
    )
    known_siblings = {"alpha", "beta-pkg", "gamma-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert '"beta-pkg~=0.0.2"' in new_text
    assert '"gamma-pkg~=0.0.2"' in new_text
    # external libs are untouched even if their version coincidentally matches:
    assert '"external-lib>=1.0"' in new_text
    assert '"unrelated~=3.2.0"' in new_text


@pytest.mark.unit
def test_rewrite_pyproject_handles_first_migration_from_other_operator() -> None:
    """Bump script can also migrate >= constraints to ~= on the first run."""
    src = (
        '[project]\n'
        'name = "alpha"\n'
        'version = "0.1.0"\n'
        'dependencies = [\n'
        '    "beta-pkg>=0.1.0",\n'
        ']\n'
    )
    known_siblings = {"alpha", "beta-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.1", known_siblings)

    assert '"beta-pkg~=0.0.1"' in new_text


@pytest.mark.unit
def test_rewrite_pyproject_preserves_comments_and_blank_lines() -> None:
    src = (
        '# top comment\n'
        '[project]\n'
        'name = "alpha"\n'
        'version = "0.0.1"\n'
        '\n'
        '# deps below\n'
        'dependencies = [\n'
        '    "beta-pkg~=0.0.1",  # inline note\n'
        ']\n'
    )
    known_siblings = {"alpha", "beta-pkg"}

    new_text, _ = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert new_text.startswith("# top comment\n")
    assert "# deps below" in new_text
    assert "# inline note" in new_text


@pytest.mark.unit
def test_rewrite_pyproject_idempotent_when_target_matches_current() -> None:
    src = '[project]\nname = "alpha"\nversion = "0.0.2"\ndependencies = ["beta-pkg~=0.0.2"]\n'
    known_siblings = {"alpha", "beta-pkg"}

    new_text, edits = bump_version.rewrite_pyproject(src, "0.0.2", known_siblings)

    assert new_text == src
    assert edits == []
```

- [ ] **Step 2: Run, confirm all five new tests FAIL**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: the new tests fail with `AttributeError: module 'scripts.bump_version' has no attribute 'rewrite_pyproject'`.

- [ ] **Step 3: Implement `rewrite_pyproject`**

Add to `scripts/bump_version.py`:

```python
import re

# Matches `version = "X.Y.Z"` at the start of a line, with optional surrounding spaces.
# We anchor on start-of-line + optional spaces to skip occurrences inside dep strings or
# nested tables. `[project]` is the only top-level table where this should fire.
_VERSION_LINE_RE = re.compile(r'^(?P<lead>\s*version\s*=\s*")[^"]+(?P<trail>")', re.MULTILINE)

# Matches a quoted PEP 508 requirement like "pkg-name~=0.0.1" or "pkg-name>=0.1.0",
# capturing the name and operator separately. Used to rewrite sibling deps only.
_DEP_REQ_RE = re.compile(
    r'"(?P<name>[A-Za-z0-9_.-]+)(?P<op>~=|>=|==|>|<|<=)(?P<ver>[0-9][0-9A-Za-z.+!*-]*)"'
)


def rewrite_pyproject(
    source: str,
    new_version: str,
    known_siblings: set[str],
) -> tuple[str, list[str]]:
    """Return (new_source, list_of_human_edit_descriptions).

    Edits:
      * one `version = "..."` line at top of `[project]`
      * every `"<sibling>~=..."` (or other operator) dep — rewritten to `~=<new_version>`.

    Non-sibling deps are left untouched. If `new_version` already matches everywhere,
    returns source unchanged and edits == [].
    """
    edits: list[str] = []

    def _version_sub(m: re.Match[str]) -> str:
        existing = m.group(0)[len(m.group("lead")):-len(m.group("trail"))]
        if existing == new_version:
            return m.group(0)
        edits.append(f'version: "{existing}" → "{new_version}"')
        return f'{m.group("lead")}{new_version}{m.group("trail")}'

    # Only rewrite the first occurrence — `version = ...` should appear once in [project].
    new_source, count = _VERSION_LINE_RE.subn(_version_sub, source, count=1)
    if count == 0:
        raise ValueError("could not find `version = \"...\"` line in pyproject")

    def _dep_sub(m: re.Match[str]) -> str:
        name = m.group("name")
        if name not in known_siblings:
            return m.group(0)
        old = m.group(0)
        new = f'"{name}~={new_version}"'
        if old == new:
            return old
        edits.append(f'dep {name}: {old} → {new}')
        return new

    new_source = _DEP_REQ_RE.sub(_dep_sub, new_source)
    return new_source, edits
```

- [ ] **Step 4: Run tests, confirm all pass**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: all 8 tests pass (3 from earlier + 5 new).

- [ ] **Step 5: Commit**

```bash
git add scripts/bump_version.py tests/scripts/test_bump_version.py
git commit -m "feat(scripts): surgical version + sibling-constraint rewriter

Regex-based edits preserve file formatting, comments, and order.
Rewrites the [project] version line and every dep that references
a sibling package, leaving external deps untouched.

Refs spec internals/specs/versioning-and-publishing.md T2, §4."
```

---

### Task 17: CLI entry point with diff preview + confirmation

**Files:**
- Modify: `scripts/bump_version.py`
- Modify: `tests/scripts/test_bump_version.py`

- [ ] **Step 1: Write a failing integration-style test for `apply_bump`**

Append to `tests/scripts/test_bump_version.py`:

```python
@pytest.mark.unit
def test_apply_bump_writes_files_and_returns_diff(tmp_path: Path) -> None:
    # Build a mini workspace with two packages on disk.
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())

    alpha_dir = tmp_path / "subdir-a/alpha"
    alpha_dir.mkdir(parents=True)
    (alpha_dir / "pyproject.toml").write_text(
        '[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n'
        'dependencies = ["beta-pkg~=0.0.1"]\n'
    )

    beta_dir = tmp_path / "subdir-a/beta"
    beta_dir.mkdir(parents=True)
    (beta_dir / "pyproject.toml").write_text(
        '[project]\nname = "beta-pkg"\nversion = "0.0.1"\n'
    )

    gamma_dir = tmp_path / "subdir-b/gamma"
    gamma_dir.mkdir(parents=True)
    (gamma_dir / "pyproject.toml").write_text(
        '[project]\nname = "gamma-pkg"\nversion = "0.0.1"\n'
        'dependencies = ["alpha-pkg~=0.0.1"]\n'
    )

    diff_text, edited_count = bump_version.apply_bump(
        root, new_version="0.0.2", dry_run=False
    )

    assert edited_count == 3
    assert 'version = "0.0.2"' in (alpha_dir / "pyproject.toml").read_text()
    assert '"alpha-pkg~=0.0.2"' in (gamma_dir / "pyproject.toml").read_text()
    # Diff should reference all three files:
    assert "alpha/pyproject.toml" in diff_text
    assert "beta/pyproject.toml" in diff_text
    assert "gamma/pyproject.toml" in diff_text


@pytest.mark.unit
def test_apply_bump_dry_run_does_not_write(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_root_pyproject.toml").read_text())
    alpha_dir = tmp_path / "subdir-a/alpha"
    alpha_dir.mkdir(parents=True)
    original = '[project]\nname = "alpha-pkg"\nversion = "0.0.1"\n'
    (alpha_dir / "pyproject.toml").write_text(original)
    (tmp_path / "subdir-a/beta").mkdir(parents=True)
    (tmp_path / "subdir-a/beta/pyproject.toml").write_text(
        '[project]\nname = "beta-pkg"\nversion = "0.0.1"\n'
    )
    (tmp_path / "subdir-b/gamma").mkdir(parents=True)
    (tmp_path / "subdir-b/gamma/pyproject.toml").write_text(
        '[project]\nname = "gamma-pkg"\nversion = "0.0.1"\n'
    )

    diff_text, edited_count = bump_version.apply_bump(
        root, new_version="0.0.2", dry_run=True
    )

    assert edited_count == 3
    assert (alpha_dir / "pyproject.toml").read_text() == original
    assert "0.0.2" in diff_text
```

- [ ] **Step 2: Run, confirm both fail**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: AttributeError on `apply_bump`.

- [ ] **Step 3: Implement `apply_bump` + `main`**

Add to `scripts/bump_version.py`:

```python
import argparse
import difflib
import sys


def apply_bump(
    root_pyproject: Path,
    new_version: str,
    dry_run: bool,
) -> tuple[str, int]:
    """Apply the bump to every release package; return (combined_unified_diff, edited_count).

    `edited_count` is the number of files whose content changed.
    """
    config = read_release_config(root_pyproject)
    located = locate_packages(root_pyproject, config)
    known_siblings = set(config.all_packages)
    root_dir = root_pyproject.parent

    diff_parts: list[str] = []
    edited = 0

    # Walk in publish_order first, then lockstep_unpublished — deterministic ordering.
    for pkg_name in config.all_packages:
        path = located[pkg_name]
        original = path.read_text(encoding="utf-8")
        new_text, edits = rewrite_pyproject(original, new_version, known_siblings)
        if not edits:
            continue
        edited += 1
        rel = path.relative_to(root_dir).as_posix()
        diff_parts.append(
            "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    new_text.splitlines(keepends=True),
                    fromfile=f"a/{rel}",
                    tofile=f"b/{rel}",
                )
            )
        )
        if not dry_run:
            path.write_text(new_text, encoding="utf-8")

    return "\n".join(diff_parts), edited


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bump_version",
        description="Bump every haywire monorepo package to a new lockstep version.",
    )
    parser.add_argument("new_version", help="Target version, e.g. 0.0.2")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to the workspace root pyproject.toml (default: ./pyproject.toml)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (for scripted use).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the diff but do not write any files.",
    )
    args = parser.parse_args(argv)

    # First pass: dry-run so we can show the diff before writing.
    diff_text, edited = apply_bump(args.root, args.new_version, dry_run=True)
    if edited == 0:
        print(f"Nothing to do: all packages already at version {args.new_version}.")
        return 0

    print(diff_text)
    print(f"\n{edited} file(s) will change. Target version: {args.new_version}.")

    if args.dry_run:
        return 0

    if not args.yes:
        try:
            response = input("Apply changes? [y/N] ").strip().lower()
        except EOFError:
            response = ""
        if response != "y":
            print("Aborted.")
            return 1

    # Second pass: actually write.
    apply_bump(args.root, args.new_version, dry_run=False)
    print(f"Wrote {edited} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, confirm pass**

```bash
uv run pytest tests/scripts/test_bump_version.py -v
```

Expected: all 10 tests pass.

- [ ] **Step 5: Try the script end-to-end against the real repo, dry-run only**

```bash
uv run python scripts/bump_version.py 0.0.1 --dry-run
```

Expected: `Nothing to do: all packages already at version 0.0.1.` (we're already at the target).

- [ ] **Step 6: Try a fake forward bump in dry-run mode**

```bash
uv run python scripts/bump_version.py 0.0.99 --dry-run | head -40
```

Expected: a unified diff that shows `version = "0.0.1"` → `"0.0.99"` and every `~=0.0.1` → `~=0.0.99` across all 10 packages, ending with `10 file(s) will change. Target version: 0.0.99.`. **Do not** answer `y` if it ever asks — the `--dry-run` flag should prevent the prompt entirely. If it prompts, the implementation is wrong.

- [ ] **Step 7: Lint and type-check the new file**

```bash
uv run ruff check scripts/bump_version.py tests/scripts/
uv run mypy scripts/bump_version.py
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add scripts/bump_version.py tests/scripts/test_bump_version.py
git commit -m "feat(scripts): apply_bump + CLI with diff preview

End-to-end bump command. Dry-run first to print a unified diff, then
prompt for confirmation before writing. --yes skips the prompt for
scripted use. --dry-run never writes.

Implements spec T2 in full. Future work (T8 — /haywire-release skill)
will wrap this CLI.

Refs spec internals/specs/versioning-and-publishing.md T2."
```

---

### Task 18: README pointer for the script

**Files:**
- Modify: `scripts/__init__.py` (we already created this; leave empty)
- Create: `scripts/README.md` *only if `scripts/` has no README yet — check first.*

- [ ] **Step 1: Check if `scripts/README.md` already exists**

```bash
test -f scripts/README.md && echo EXISTS || echo MISSING
```

- [ ] **Step 2: If MISSING, create a tiny pointer**

Create `scripts/README.md` with:

```markdown
# scripts/

Maintenance scripts run by humans or CI.

| Script                | Purpose                                                          |
| --------------------- | ---------------------------------------------------------------- |
| `bump_version.py`     | Bump every Tier 1+2 package to a new lockstep version.           |
| `generate_marketstall.py` | (planned) CI marketstall generator for the published packages.  |

## bump_version.py

```bash
# Preview what would change.
uv run python scripts/bump_version.py 0.0.2 --dry-run

# Apply with confirmation prompt.
uv run python scripts/bump_version.py 0.0.2

# Apply without prompting (CI / scripts).
uv run python scripts/bump_version.py 0.0.2 --yes
```

Reads `[tool.haywire.release]` in the workspace root `pyproject.toml` for the canonical
package list. To add or remove a publishable package, edit that block — not the script.
```

- [ ] **Step 3: If EXISTS, append the `bump_version.py` row to its existing script table or add a section for it; otherwise skip.**

(Inspect the existing file first; do not blindly overwrite.)

- [ ] **Step 4: Commit (only if a file was created or modified)**

```bash
git add scripts/README.md
git commit -m "docs(scripts): document bump_version.py usage"
```

---

### Task 19: Final verification

**Files:** read-only.

- [ ] **Step 1: Run the full fast test suite**

```bash
uv run pytest -m "not integration" -q
```

Expected: every test passes, including the 10 new bump-script tests.

- [ ] **Step 2: Run ruff across the whole repo**

```bash
uv run ruff check .
```

Expected: clean.

- [ ] **Step 3: Run mypy on the touched paths**

```bash
uv run mypy scripts/bump_version.py packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-visiongraph/haybale_visiongraph/ barn/haybale-TEST_A/haybale_test_a/
```

Expected: clean.

- [ ] **Step 4: Verify `git log` shows the planned commits in a clean line**

```bash
git log --oneline -15
```

Expected: a clean sequence of commits with messages from this plan, top to bottom matching task order.

- [ ] **Step 5: Confirm all published versions are 0.0.1 at runtime**

```bash
uv run python -c "from importlib.metadata import version; [print(f'{p}: {version(p)}') for p in ['haywire-core','haywire-studio','haybale-core','haybale-studio','haybale-graph-editor','haybale-haystack','haybale-example','haybale-visiongraph','haybale-testing','haybale-TEST_A']]"
```

Expected: every package prints `0.0.1`.

- [ ] **Step 6: Sanity-check the bump script reports "nothing to do" at the current version**

```bash
uv run python scripts/bump_version.py 0.0.1 --dry-run
```

Expected: `Nothing to do: all packages already at version 0.0.1.`

---

## Self-Review (already performed by the plan author)

### Spec coverage

- §1 lockstep model — encoded by `[tool.haywire.release].publish_order` + `lockstep_unpublished` listing all 10 packages, bumped together. ✅
- §2 pyproject is source of truth — pre-existing (T1 already shipped). ✅
- §3 first release version `0.0.1` — Tasks 3–12 patch every pyproject. ✅
- §4 `~=X.Y.Z` constraint format — Tasks 3–12 rewrite all `>=0.1.0` to `~=0.0.1`; bump script enforces going forward. ✅
- §5 `[tool.haywire.release]` canonical list — Task 2. ✅
- T2 `scripts/bump_version.py` — Tasks 14–17, with `--dry-run` and confirmation flow matching spec "Release flow" steps 3–5. ✅
- Pre-release migration table (lines 856–862 of spec) — Tasks 3–12 cover every pyproject row. The `__init__.py` row is pre-existing (T1 done). The `LIBRARY.md` → `NOTES.md` rename for haybale-visiongraph is **out of scope for this plan** (it is part of T9, the `haywire-gen-docs` skill update). Noted in the deferral list below.

### Out of scope (deferred to other plans)

- T3, T4 — CI marketstall generator and publish workflow (separate plan).
- T5, T6 — `haywire share --save` and `haywire init` updates (separate plan).
- T7 — two-tier marketplace runtime (separate plan).
- T8 — `/haywire-release` skill (separate plan, will wrap this bump script).
- T9 — `haywire-gen-docs` update; includes the `LIBRARY.md` → `NOTES.md` rename mentioned in the spec's pre-release migration table.
- T10, T12, T13 — Library Manager polish (separate plan).
- T11 — `haybale-marketplace` carve-out (separate spec).
- `docs/reference/publish_releases.md` — operational doc; will be written alongside T8.

### Placeholder scan

No "TBD", no "add appropriate error handling", no "similar to Task N" — every code step contains the actual code. ✅

### Type consistency

- `ReleaseConfig` dataclass introduced in Task 14, used in Tasks 15 and 17 with the same `publish_order` / `lockstep_unpublished` / `all_packages` API. ✅
- `MissingPackageError` introduced in Task 15, used by `locate_packages`. ✅
- `rewrite_pyproject(source, new_version, known_siblings) -> (new_text, edits)` signature in Task 16 matches the call site in `apply_bump` in Task 17. ✅
- `locate_packages` return type `dict[str, Path]` matches the dict indexing in `apply_bump`. ✅
- `apply_bump(root_pyproject, new_version, dry_run) -> (diff_text, edited_count)` signature in Task 17 matches both the tests and the `main()` call site. ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-versioning-pre-release-and-bump-script.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session, batch with checkpoints.

Which approach?
