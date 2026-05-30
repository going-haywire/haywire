# CI Publish Workflow & Marketstall Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the release CI pipeline. On a `v*.*.*` tag, build every Tier 1+2 wheel, publish them to PyPI via Trusted Publisher (idempotent + fail-fast), then regenerate the official monorepo marketplace TOML and deploy it to GitHub Pages so first-run haywire installs find published packages.

**Architecture:** Three parts. **Part 1 (pre-release readme fix):** remove the broken `readme = "../../README.md"` line from `packages/haywire-core/pyproject.toml` so `uv build` works (a Plan A follow-up flagged by the reviewers). **Part 2 (`scripts/generate_marketstall.py`):** a TDD-driven CLI that reads `[tool.haywire.release]`, walks each `publish_order` package's pyproject + `@library` decorator, and emits a marketplace TOML file with `[[packages]]` entries (`source = "pypi"`). Re-uses `read_release_config` / `locate_packages` from `scripts/bump_version.py`. Single output file format documented per spec §7. **Part 3 (`.github/workflows/publish.yml`):** GitHub Actions workflow with 4 sequential jobs — gate (test suite), build (all wheels collected as artifacts), publish (sequential `uv publish` with PyPI-API idempotent skip), deploy (run the generator, push the result to a `gh-pages` branch). PyPI Trusted Publisher (OIDC, `id-token: write` permission) — no stored tokens.

**Tech Stack:** Python 3.10+, `tomllib` (read), `tomli_w` already not present in the project — we'll generate TOML by hand (controlled format) rather than introduce a dependency for what is a fixed, narrow output schema. GitHub Actions, `astral-sh/setup-uv`, PyPI Trusted Publisher (OIDC), `peaceiris/actions-gh-pages` for the deploy.

**Spec reference:** This plan covers spec sections **§5 (canonical list — consumer side: marketstall generator + CI workflow)**, **§7 (marketstall file format)** for the producer side limited to `source = "pypi"` entries, and the Release Flow `### CI pipeline (on tag v*.*.*)` block (Job 1 → Job 4). Spec tasks **T3** (`scripts/generate_marketstall.py`) and **T4** (`.github/workflows/publish.yml`). Out of scope: `haywire share` (T5, separate plan), `haywire init` (T6, separate plan), marketstall consumption / two-tier marketplace (T7), `/haywire-release` skill (T8, separate plan).

---

## Approach Rationale (read before starting)

**Why fix `haywire-core`'s readme path here, not in a separate commit:** Plan A's reviewers flagged this as out-of-scope-for-A but blocking-for-B. Job 2 of the CI workflow runs `uv build --package haywire-core`, which fails today. Plan B can't ship until that's fixed. Single-line edit, ~30s of work, deserves a dedicated first-task commit so the bisect log is clean.

**Why remove the line rather than add a per-package README:** Hatchling accepts a pyproject with no `readme` field — the resulting wheel just has no PyPI long-description. We don't *want* the root README on PyPI for `haywire-core` (it documents the whole project, not the package). Per-package READMEs are a separate concern (likely T9 — `haywire-gen-docs` work). YAGNI says: remove the line, ship.

**Why a hand-written TOML emitter instead of `tomli_w`:** The marketstall format is *one fixed schema* (per spec §7) with 11 known keys per entry, all simple types (str + list[str]). Bringing in `tomli_w` for this is overkill — and produces output we can't easily control the formatting of (key order, comment headers). A small `_emit_packages_toml(entries)` function gives us perfect control. Already established pattern in this repo: `scripts/bump_version.py` rewrites TOML with regex rather than round-trip for the same reason.

**Why the generator reads from `[project] dependencies` (not `@library(dependencies=...)`) for the marketstall `dependencies` field:** The `@library` decorator uses Python module names with underscores (`haybale_studio`). The marketstall format requires pip distribution names with hyphens (`haybale-studio`) — spec §7 is explicit. `pyproject.toml`'s `[project] dependencies` already uses hyphens. Reading from there is one source of truth and avoids a name-conversion step. The generator filters to packages whose names start with `haybale-` (haywire-core/haywire-studio are framework, not Library-Manager-visible siblings — matches the haystack example in spec §7 line 510).

**Why we still need to read `@library` for `label` / `tags` / `description`:** Those fields don't live in `pyproject.toml`. They're authored on the decorator. The generator parses the decorator out of the package's `__init__.py` to lift them into the marketstall entry. Parsing approach: `ast` module (stdlib) — robust to whitespace and comment changes, no regex fragility.

**Why PyPI Trusted Publisher and not API tokens:** Spec mandates it. Better security (no stored secret), per-environment trust, no token-rotation burden. Setup is a one-time step in the PyPI project settings (linking GitHub Actions OIDC) — outside the scope of this plan but documented in `scripts/README.md`.

**Why `peaceiris/actions-gh-pages` for the marketplace deploy and not direct git push:** Battle-tested third-party action with known behaviour around the `gh-pages` orphan branch. Used widely; simpler than rolling our own.

---

## File Structure

### Files modified
- `packages/haywire-core/pyproject.toml` — remove the broken `readme` line.
- `pyproject.toml` (workspace root) — add the `[tool.haywire.marketstall]` block with `source_url` + `docs_url` template (avoids hard-coding the GitHub user/repo into the script). See Task 4 for the exact block. Also lifts `description`/`label`/`tags` defaults out of `@library` parsing for packages where the decorator data isn't reachable.

### Files created
- `scripts/generate_marketstall.py` — the CLI.
- `tests/scripts/test_generate_marketstall.py` — unit tests.
- `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml` — extended root pyproject fixture with `[tool.haywire.marketstall]` block.
- `tests/scripts/fixtures/sample_marketstall_package_pyproject.toml` — a sample package pyproject fixture.
- `tests/scripts/fixtures/sample_marketstall_package_init.py` — a sample package `__init__.py` with an `@library` decorator.
- `.github/workflows/publish.yml` — the publish workflow.

### Files NOT touched (out of scope for this plan)
- `scripts/bump_version.py` (Plan A) — generator reuses it as a library; no edits.
- `barn/haybale-haystack/`, `barn/haybale-studio/` — these packages have no `README.md` in the wheel today. Hatchling tolerates that. They will publish with no PyPI long-description. The author can add per-package READMEs later (likely T9). Don't expand this plan's scope to write them.
- `.github/workflows/tests.yml` — unrelated.

---

## Self-Review Plan-Time Checks (already performed by author)

- §5 canonical list consumer: ✅ generator reads `[tool.haywire.release].publish_order` via the existing `read_release_config`.
- §7 marketstall file format: ✅ Task 5–8 implement the schema for `source = "pypi"` only. `[[locals]]`/`source = "git"`/runtime-only fields are correctly out of scope.
- Release Flow Job 1 — pytest gate: ✅ Task 11.
- Release Flow Job 2 — build all wheels as artifacts: ✅ Task 11.
- Release Flow Job 3 — sequential publish, idempotent skip via PyPI API, fail-fast: ✅ Task 12.
- Release Flow Job 4 — generator + GitHub Pages deploy: ✅ Task 13.
- Recovery from partial publish: ✅ idempotent skip in Task 12 + workflow re-runnable per spec; no extra retry logic needed.

---

## Task list

### Task 1: Baseline verification

**Files:** read-only.

- [ ] **Step 1: Confirm pre-edit baseline is clean**

Run from repo root `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo`:

```bash
uv run ruff check .
uv run pytest -m "not integration" -q
uv run mypy scripts/bump_version.py
```

Expected: ruff clean, pytest "1143 passed, 1 skipped, 75 deselected" (after Plan A), mypy clean. If any fails, **stop and notify the user** before proceeding.

- [ ] **Step 2: Confirm `haywire-core` build still fails the expected way**

```bash
rm -rf dist/
uv build --package haywire-core 2>&1 | tail -5
```

Expected: ends with `OSError: Readme file does not exist: ../../README.md`. This is the issue Task 2 fixes; verifying it reproduces ensures we'll know when the fix takes effect.

```bash
rm -rf dist/
```

(Clean up build artifacts.)

---

### Task 2: Remove the broken readme line from `haywire-core`

**Files:**
- Modify: `packages/haywire-core/pyproject.toml`

- [ ] **Step 1: Remove the line**

In `packages/haywire-core/pyproject.toml`, delete the line:

```toml
readme = "../../README.md"
```

This line sits between `description = "..."` and `requires-python = ">=3.10"`. Remove it entirely (do not replace with an empty string — that's not a valid TOML value here).

After the edit, the `[project]` section should look like:

```toml
[project]
name = "haywire-core"
version = "0.0.1"
description = "Haywire Node System Framework"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Haywire Team"}
]
keywords = ["haywire", "node-editor", "visual-programming", "framework"]
```

- [ ] **Step 2: Verify the build now succeeds**

```bash
rm -rf dist/
uv build --package haywire-core 2>&1 | tail -5
```

Expected: ends with `Successfully built dist/haywire_core-0.0.1-py3-none-any.whl`. If it fails, revert and investigate.

```bash
rm -rf dist/
```

- [ ] **Step 3: Verify all 7 publishable packages build**

```bash
rm -rf dist/
for pkg in haywire-core haywire-studio haybale-core haybale-studio haybale-graph-editor haybale-haystack haybale-example; do
    echo "=== $pkg ==="
    uv build --package "$pkg" 2>&1 | tail -2
done
ls dist/
```

Expected: 14 artifacts in `dist/` (one `.whl` and one `.tar.gz` per package, all at `0.0.1`). Every `=== $pkg ===` is followed by `Successfully built ...`.

```bash
rm -rf dist/
```

- [ ] **Step 4: Re-run the pytest baseline (no test should have changed)**

```bash
uv run pytest -m "not integration" -q
```

Expected: same tally as Task 1 Step 1.

- [ ] **Step 5: Commit**

```bash
git add packages/haywire-core/pyproject.toml
git commit -m "$(cat <<'EOF'
fix(haywire-core): drop broken readme path that blocks uv build

readme = "../../README.md" pointed outside the package root and was
rejected by hatchling. The line is unnecessary — hatchling tolerates
no readme field and produces a wheel with no PyPI long-description.
A per-package README can be authored later if needed.

Refs spec internals/specs/versioning-and-publishing.md (release flow
job 2 — build all wheels).
EOF
)"
```

---

### Task 3: Add `[tool.haywire.marketstall]` config block

**Files:**
- Modify: `pyproject.toml` (workspace root)

- [ ] **Step 1: Append the marketstall config block**

The marketstall generator needs a small amount of repo-level config: the GitHub source URL of this monorepo (used for `source_url` and as the base for `docs_url`), and the marketstall output path. Append at the end of `pyproject.toml`:

```toml

[tool.haywire.marketstall]
# Configuration for scripts/generate_marketstall.py.
# Consumed by the marketplace generator (T3) and the CI publish workflow (T4).

# Repo URL used as the `source_url` for every generated [[packages]] entry.
# Also forms the base for the `docs_url` raw-githubusercontent URL.
source_url = "https://github.com/maybites/haywire"

# Default branch used in the raw-githubusercontent docs_url. Update if
# the repo's primary branch ever moves.
docs_branch = "main"

# Default author and tags applied when a package's @library decorator
# doesn't set them. Per-package values from the decorator always win.
default_author = "Haywire Team"
default_tags = []
```

- [ ] **Step 2: Verify TOML parses**

```bash
uv run python -c "
import tomllib, pathlib
d = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
print(d['tool']['haywire']['marketstall'])
"
```

Expected: dict with `source_url`, `docs_branch`, `default_author`, `default_tags`.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "$(cat <<'EOF'
chore: add [tool.haywire.marketstall] generator config

Repo-level defaults consumed by scripts/generate_marketstall.py:
source_url, docs_branch, default_author, default_tags. Per-package
@library values override the defaults; the block exists so the
generator never needs to hardcode the GitHub user/repo.

Refs spec internals/specs/versioning-and-publishing.md §7.
EOF
)"
```

---

### Task 4: Test fixtures for the generator

**Files:**
- Create: `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml`
- Create: `tests/scripts/fixtures/sample_marketstall_package_pyproject.toml`
- Create: `tests/scripts/fixtures/sample_marketstall_package_init.py`

- [ ] **Step 1: Create the root pyproject fixture**

Create `tests/scripts/fixtures/sample_marketstall_root_pyproject.toml`:

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
    "haybale-alpha",
    "haybale-beta",
]
lockstep_unpublished = [
    "haybale-internal",
]

[tool.haywire.marketstall]
source_url = "https://github.com/example/fake-workspace"
docs_branch = "main"
default_author = "Fake Team"
default_tags = []
```

- [ ] **Step 2: Create the sample package pyproject fixture**

Create `tests/scripts/fixtures/sample_marketstall_package_pyproject.toml`:

```toml
[project]
name = "haybale-alpha"
version = "0.0.3"
description = "Alpha library — does alpha things"
requires-python = ">=3.10"

dependencies = [
    "haywire-core~=0.0.3",
    "haybale-beta~=0.0.3",
    "external-lib>=1.0",
]

[project.entry-points."haywire.libraries"]
alpha = "haybale_alpha:Library"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 3: Create the sample package `__init__.py` fixture**

Create `tests/scripts/fixtures/sample_marketstall_package_init.py`:

```python
"""Sample package init used by tests for the marketstall generator's @library parser."""

from importlib.metadata import version as _pkg_version


@library(  # noqa: F821  (fake import; this file is a fixture, never imported as Python)
    label="Alpha",
    id="alpha",
    version=_pkg_version("haybale-alpha"),
    description="Alpha library — overridden in pyproject? Decorator wins.",
    url="",
    help_url="",
    author="Alpha Author",
    author_url="",
    dependencies=["haybale_beta"],
    tags=["alpha", "demo"],
    file_watcher=False,
)
class Library:
    pass
```

(Note: the fixture is parsed via `ast`, not executed, so the `@library` reference being unresolved is fine. The `# noqa: F821` suppresses any flake8/ruff complaint if the file gets accidentally linted.)

- [ ] **Step 4: Commit**

```bash
git add tests/scripts/fixtures/sample_marketstall_root_pyproject.toml \
        tests/scripts/fixtures/sample_marketstall_package_pyproject.toml \
        tests/scripts/fixtures/sample_marketstall_package_init.py
git commit -m "test(scripts): fixtures for the marketstall generator

Three fixture files used by the upcoming generate_marketstall test
suite: a workspace root pyproject with the new [tool.haywire.marketstall]
block, a sample package pyproject, and a sample package __init__.py
with an @library decorator the generator's AST parser walks.

Refs spec internals/specs/versioning-and-publishing.md T3."
```

---

### Task 5: Generator skeleton — `extract_library_metadata` (TDD red→green)

The generator parses each package's `__init__.py` for the `@library(...)` call and pulls out `label`, `description`, `author`, `tags`. We use `ast` for robustness.

**Files:**
- Create: `scripts/generate_marketstall.py`
- Create: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Write the failing test**

Create `tests/scripts/test_generate_marketstall.py`:

```python
"""Tests for scripts/generate_marketstall.py."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import generate_marketstall


FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.mark.unit
def test_extract_library_metadata_reads_decorator_fields() -> None:
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"

    meta = generate_marketstall.extract_library_metadata(init_py)

    assert meta.label == "Alpha"
    assert meta.author == "Alpha Author"
    assert meta.tags == ["alpha", "demo"]
    assert meta.description == "Alpha library — overridden in pyproject? Decorator wins."


@pytest.mark.unit
def test_extract_library_metadata_returns_none_fields_when_decorator_missing(tmp_path: Path) -> None:
    # Plain module with no @library call.
    plain = tmp_path / "plain_init.py"
    plain.write_text('"""no decorator here."""\n')

    meta = generate_marketstall.extract_library_metadata(plain)

    assert meta.label is None
    assert meta.author is None
    assert meta.tags is None
    assert meta.description is None
```

- [ ] **Step 2: Run, confirm both tests FAIL**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: `AttributeError: module 'scripts.generate_marketstall' has no attribute 'extract_library_metadata'`.

- [ ] **Step 3: Create the script skeleton + `extract_library_metadata`**

Create `scripts/generate_marketstall.py`:

```python
"""Generate the official monorepo marketplace TOML for haywire.

Reads [tool.haywire.release] (publish_order) and [tool.haywire.marketstall]
(source_url, docs_branch, defaults) from the workspace root pyproject,
walks each publishable package's pyproject + __init__.py, and emits a
TOML file with one [[packages]] entry per published package. Source =
"pypi" for every entry. Deployed by the publish CI workflow (T4) to
GitHub Pages.

Used by:
  - .github/workflows/publish.yml (job 4 — deploy marketstall)
  - manual invocation: uv run python scripts/generate_marketstall.py
"""

from __future__ import annotations

import argparse
import ast
import sys
import tomllib  # type: ignore[import-not-found]  # stdlib 3.11+; mypy config pins 3.10
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LibraryMetadata:
    """Subset of @library(...) decorator fields we use in the marketstall.

    None means "not authored on the decorator" — caller should fall back
    to pyproject description or [tool.haywire.marketstall] defaults.
    """

    label: str | None
    description: str | None
    author: str | None
    tags: list[str] | None


def extract_library_metadata(init_py: Path) -> LibraryMetadata:
    """Parse an __init__.py for an @library(...) decorator and lift label/description/author/tags."""
    tree = ast.parse(init_py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            func = dec.func
            if not (isinstance(func, ast.Name) and func.id == "library"):
                continue
            kwargs = {kw.arg: kw.value for kw in dec.keywords if kw.arg is not None}
            return LibraryMetadata(
                label=_as_str(kwargs.get("label")),
                description=_as_str(kwargs.get("description")),
                author=_as_str(kwargs.get("author")),
                tags=_as_str_list(kwargs.get("tags")),
            )
    return LibraryMetadata(label=None, description=None, author=None, tags=None)


def _as_str(node: ast.expr | None) -> str | None:
    """Return the string literal value of an AST node, or None for any non-string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _as_str_list(node: ast.expr | None) -> list[str] | None:
    """Return a list of string literals from an AST list, or None for any non-list-of-strings."""
    if not isinstance(node, ast.List):
        return None
    out: list[str] = []
    for elt in node.elts:
        s = _as_str(elt)
        if s is None:
            return None
        out.append(s)
    return out
```

- [ ] **Step 4: Run, confirm tests pass**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Lint + type-check**

```bash
uv run ruff check scripts/generate_marketstall.py tests/scripts/
uv run mypy scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py
git commit -m "$(cat <<'EOF'
feat(scripts): generate_marketstall skeleton + @library AST parser

First slice of the marketstall generator. Walks a package's
__init__.py via the ast module and extracts label/description/
author/tags from the @library(...) decorator. Returns None for
any field the author didn't set — callers fall back to pyproject
description or [tool.haywire.marketstall] defaults.

Refs spec internals/specs/versioning-and-publishing.md T3, §7.
EOF
)"
```

---

### Task 6: Build a `MarketplaceEntry` from a located package (TDD red→green)

**Files:**
- Modify: `scripts/generate_marketstall.py`
- Modify: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/scripts/test_generate_marketstall.py`:

```python
@pytest.mark.unit
def test_marketstall_config_reads_defaults_from_root_pyproject(tmp_path: Path) -> None:
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    config = generate_marketstall.read_marketstall_config(root)

    assert config.source_url == "https://github.com/example/fake-workspace"
    assert config.docs_branch == "main"
    assert config.default_author == "Fake Team"
    assert config.default_tags == []


@pytest.mark.unit
def test_build_entry_uses_decorator_values_over_pyproject() -> None:
    pkg_pyproject = FIXTURE_DIR / "sample_marketstall_package_pyproject.toml"
    init_py = FIXTURE_DIR / "sample_marketstall_package_init.py"
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_author="Fake Team",
        default_tags=[],
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="subdir-a/haybale-alpha",
        module_name="haybale_alpha",
    )

    assert entry["name"] == "haybale-alpha"
    assert entry["label"] == "Alpha"
    assert entry["min_version"] == "0.0.3"
    # Decorator overrides pyproject for description:
    assert entry["description"] == "Alpha library — overridden in pyproject? Decorator wins."
    assert entry["author"] == "Alpha Author"
    assert entry["source"] == "pypi"
    assert entry["install_spec"] == "haybale-alpha"
    assert entry["tags"] == ["alpha", "demo"]
    # Only haybale-* siblings; haywire-core and external-lib are filtered out:
    assert entry["dependencies"] == ["haybale-beta"]
    assert entry["source_url"] == "https://github.com/example/fake-workspace"
    assert entry["docs_url"] == (
        "https://raw.githubusercontent.com/example/fake-workspace/main/"
        "subdir-a/haybale-alpha/haybale_alpha/"
    )


@pytest.mark.unit
def test_build_entry_falls_back_to_pyproject_description_when_decorator_absent(tmp_path: Path) -> None:
    pkg_pyproject = tmp_path / "pyproject.toml"
    pkg_pyproject.write_text(
        '[project]\n'
        'name = "haybale-bare"\n'
        'version = "0.0.1"\n'
        'description = "Bare-bones package without an @library decorator."\n'
        'dependencies = []\n'
    )
    init_py = tmp_path / "haybale_bare" / "__init__.py"
    init_py.parent.mkdir()
    init_py.write_text('"""no decorator."""\n')
    config = generate_marketstall.MarketstallConfig(
        source_url="https://github.com/example/fake-workspace",
        docs_branch="main",
        default_author="Fake Team",
        default_tags=["default-tag"],
    )

    entry = generate_marketstall.build_entry(
        pyproject_path=pkg_pyproject,
        init_py=init_py,
        config=config,
        subdirectory="barn/haybale-bare",
        module_name="haybale_bare",
    )

    assert entry["label"] == "haybale-bare"   # falls back to name
    assert entry["description"] == "Bare-bones package without an @library decorator."
    assert entry["author"] == "Fake Team"      # config default
    assert entry["tags"] == ["default-tag"]    # config default
    assert entry["dependencies"] == []
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: the 2 prior tests pass, the 3 new tests fail with `AttributeError`.

- [ ] **Step 3: Implement `MarketstallConfig`, `read_marketstall_config`, `build_entry`**

Append to `scripts/generate_marketstall.py`:

```python
@dataclass(frozen=True)
class MarketstallConfig:
    """Repo-level config consumed by build_entry. Read from [tool.haywire.marketstall]."""

    source_url: str
    docs_branch: str
    default_author: str
    default_tags: list[str]


def read_marketstall_config(root_pyproject: Path) -> MarketstallConfig:
    data = tomllib.loads(root_pyproject.read_text(encoding="utf-8"))
    block = data["tool"]["haywire"]["marketstall"]
    return MarketstallConfig(
        source_url=block["source_url"],
        docs_branch=block.get("docs_branch", "main"),
        default_author=block.get("default_author", ""),
        default_tags=list(block.get("default_tags", [])),
    )


def build_entry(
    pyproject_path: Path,
    init_py: Path,
    config: MarketstallConfig,
    subdirectory: str,
    module_name: str,
) -> dict[str, object]:
    """Build one [[packages]] dict for a package.

    `subdirectory` is the package directory relative to the repo root (e.g. "barn/haybale-foo").
    `module_name` is the importable module dir name (e.g. "haybale_foo") inside that subdirectory.
    """
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject["project"]
    name = project["name"]
    version = project["version"]
    pyproject_description = project.get("description", "")
    pyproject_deps: list[str] = list(project.get("dependencies", []))

    meta = extract_library_metadata(init_py)

    sibling_haybale = _filter_haybale_siblings(pyproject_deps)
    docs_url = (
        f"https://raw.githubusercontent.com/{_strip_github_prefix(config.source_url)}/"
        f"{config.docs_branch}/{subdirectory}/{module_name}/"
    )

    return {
        "name": name,
        "label": meta.label or name,
        "min_version": version,
        "description": meta.description or pyproject_description,
        "author": meta.author or config.default_author,
        "source": "pypi",
        "install_spec": name,
        "tags": meta.tags if meta.tags is not None else list(config.default_tags),
        "dependencies": sibling_haybale,
        "source_url": config.source_url,
        "docs_url": docs_url,
    }


def _filter_haybale_siblings(deps: list[str]) -> list[str]:
    """Return the bare haybale-* distribution names from a list of PEP 508 dep strings.

    Marketstall `dependencies` is sibling haybale-* only (per spec §7) — framework
    haywire-* packages and external deps are excluded.
    """
    out: list[str] = []
    for dep in deps:
        # Strip any version/marker suffix: "haybale-foo~=0.0.1" → "haybale-foo".
        name = dep.split("~")[0].split(">")[0].split("<")[0].split("=")[0].split(";")[0].split("[")[0].strip()
        if name.startswith("haybale-"):
            out.append(name)
    return out


def _strip_github_prefix(url: str) -> str:
    """Turn 'https://github.com/user/repo' into 'user/repo'. Used to build raw URLs."""
    return url.rstrip("/").removeprefix("https://github.com/")
```

- [ ] **Step 4: Run, confirm GREEN**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Lint + type-check**

```bash
uv run ruff check scripts/generate_marketstall.py tests/scripts/
uv run mypy scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py
git commit -m "$(cat <<'EOF'
feat(scripts): build_entry — assemble one marketstall entry

Reads a package pyproject + __init__.py and the workspace-root
[tool.haywire.marketstall] config to produce one [[packages]] dict.
@library decorator values win over pyproject description; pyproject
description wins over an empty decorator field. Sibling deps are
filtered to bare haybale-* names (framework + external deps stripped).
docs_url is constructed via the configured GitHub source_url +
docs_branch + subdirectory/module pair.

Refs spec internals/specs/versioning-and-publishing.md T3, §7.
EOF
)"
```

---

### Task 7: TOML emitter — `emit_marketstall_toml` (TDD red→green)

We emit by hand so we control field order, comment headers, and indentation. The output must be valid TOML and round-trip via `tomllib`.

**Files:**
- Modify: `scripts/generate_marketstall.py`
- Modify: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/scripts/test_generate_marketstall.py`:

```python
@pytest.mark.unit
def test_emit_marketstall_toml_round_trips_via_tomllib() -> None:
    entries = [
        {
            "name": "haybale-alpha",
            "label": "Alpha",
            "min_version": "0.0.3",
            "description": "alpha desc",
            "author": "Alpha Author",
            "source": "pypi",
            "install_spec": "haybale-alpha",
            "tags": ["a", "b"],
            "dependencies": ["haybale-beta"],
            "source_url": "https://github.com/example/fake-workspace",
            "docs_url": "https://raw.githubusercontent.com/example/fake-workspace/main/x/y/",
        },
        {
            "name": "haybale-beta",
            "label": "Beta",
            "min_version": "0.0.3",
            "description": "beta desc",
            "author": "Beta Author",
            "source": "pypi",
            "install_spec": "haybale-beta",
            "tags": [],
            "dependencies": [],
            "source_url": "https://github.com/example/fake-workspace",
            "docs_url": "https://raw.githubusercontent.com/example/fake-workspace/main/x/z/",
        },
    ]

    out_text = generate_marketstall.emit_marketstall_toml(entries)
    import tomllib
    parsed = tomllib.loads(out_text)

    assert len(parsed["packages"]) == 2
    assert parsed["packages"][0]["name"] == "haybale-alpha"
    assert parsed["packages"][0]["dependencies"] == ["haybale-beta"]
    assert parsed["packages"][1]["tags"] == []


@pytest.mark.unit
def test_emit_marketstall_toml_starts_with_header_comment() -> None:
    out = generate_marketstall.emit_marketstall_toml([])
    assert out.startswith("# Official haywire marketplace")


@pytest.mark.unit
def test_emit_marketstall_toml_escapes_quotes_in_strings() -> None:
    entries = [
        {
            "name": "haybale-x",
            "label": 'X with "quotes"',
            "min_version": "0.0.1",
            "description": "desc",
            "author": "Author",
            "source": "pypi",
            "install_spec": "haybale-x",
            "tags": [],
            "dependencies": [],
            "source_url": "u",
            "docs_url": "d",
        }
    ]
    out = generate_marketstall.emit_marketstall_toml(entries)
    import tomllib
    parsed = tomllib.loads(out)
    assert parsed["packages"][0]["label"] == 'X with "quotes"'
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 5 prior pass, 3 new fail with `AttributeError: ... emit_marketstall_toml`.

- [ ] **Step 3: Implement `emit_marketstall_toml`**

Append to `scripts/generate_marketstall.py`:

```python
# Order of fields in every [[packages]] entry. Matches spec §7 _TOML_FIELDS.
_ENTRY_FIELD_ORDER: tuple[str, ...] = (
    "name",
    "label",
    "min_version",
    "description",
    "author",
    "source",
    "install_spec",
    "tags",
    "dependencies",
    "source_url",
    "docs_url",
)

_HEADER = """\
# Official haywire marketplace
# Generated by scripts/generate_marketstall.py on every release tag.
# Do not edit by hand — re-run the generator instead.
#
# Subscribers fetch this file from GitHub Pages:
#   https://maybites.github.io/haywire/marketplace.toml
"""


def emit_marketstall_toml(entries: list[dict[str, object]]) -> str:
    """Emit a marketplace TOML containing one [[packages]] entry per input dict.

    Field order within each entry follows spec §7. Strings are quoted with
    double quotes and embedded `"` characters are backslash-escaped (TOML basic
    string rules). Lists are emitted inline like `["a", "b"]`.
    """
    parts: list[str] = [_HEADER]
    for entry in entries:
        parts.append("")
        parts.append("[[packages]]")
        for field in _ENTRY_FIELD_ORDER:
            if field not in entry:
                continue
            parts.append(f"{field} = {_format_value(entry[field])}")
    parts.append("")
    return "\n".join(parts)


def _format_value(value: object) -> str:
    if isinstance(value, str):
        return _format_string(value)
    if isinstance(value, list):
        if not value:
            return "[]"
        return "[" + ", ".join(_format_value(v) for v in value) + "]"
    raise TypeError(f"unsupported marketstall value type: {type(value).__name__}")


def _format_string(value: str) -> str:
    """Format a string as a TOML basic string with `"` escaping."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
```

- [ ] **Step 4: Run, confirm GREEN**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Lint + type-check**

```bash
uv run ruff check scripts/generate_marketstall.py tests/scripts/
uv run mypy scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py
git commit -m "$(cat <<'EOF'
feat(scripts): emit_marketstall_toml — hand-written TOML emitter

Produces a marketplace TOML with one [[packages]] entry per input
dict. Field order matches spec §7. Strings are TOML basic strings
with backslash-escaping for embedded quotes. The output round-trips
via tomllib. A header comment makes the file source identifiable
when subscribers inspect it.

Refs spec internals/specs/versioning-and-publishing.md T3, §7.
EOF
)"
```

---

### Task 8: `generate(...)` orchestrator + CLI (TDD red→green)

**Files:**
- Modify: `scripts/generate_marketstall.py`
- Modify: `tests/scripts/test_generate_marketstall.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/scripts/test_generate_marketstall.py`:

```python
@pytest.mark.unit
def test_generate_walks_publish_order_and_returns_toml(tmp_path: Path) -> None:
    # Build a mini workspace with 2 publishable packages on disk.
    root = tmp_path / "pyproject.toml"
    root.write_text((FIXTURE_DIR / "sample_marketstall_root_pyproject.toml").read_text())

    alpha = tmp_path / "subdir-a/haybale-alpha"
    alpha.mkdir(parents=True)
    (alpha / "pyproject.toml").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_pyproject.toml").read_text()
    )
    (alpha / "haybale_alpha").mkdir()
    (alpha / "haybale_alpha" / "__init__.py").write_text(
        (FIXTURE_DIR / "sample_marketstall_package_init.py").read_text()
    )

    beta = tmp_path / "subdir-a/haybale-beta"
    beta.mkdir(parents=True)
    (beta / "pyproject.toml").write_text(
        '[project]\n'
        'name = "haybale-beta"\n'
        'version = "0.0.3"\n'
        'description = "Beta library"\n'
        'dependencies = []\n'
    )
    (beta / "haybale_beta").mkdir()
    (beta / "haybale_beta" / "__init__.py").write_text('"""beta."""\n')

    # haybale-internal is in lockstep_unpublished — must NOT appear in output.
    internal = tmp_path / "subdir-b/haybale-internal"
    internal.mkdir(parents=True)
    (internal / "pyproject.toml").write_text(
        '[project]\nname = "haybale-internal"\nversion = "0.0.3"\ndescription = "i"\ndependencies = []\n'
    )

    out_text = generate_marketstall.generate(root)

    import tomllib
    parsed = tomllib.loads(out_text)

    # Only publish_order packages appear, in publish_order:
    assert [p["name"] for p in parsed["packages"]] == ["haybale-alpha", "haybale-beta"]
    assert parsed["packages"][0]["min_version"] == "0.0.3"
    assert parsed["packages"][0]["docs_url"].endswith("/subdir-a/haybale-alpha/haybale_alpha/")


@pytest.mark.unit
def test_generate_uses_first_entry_point_module_name(tmp_path: Path) -> None:
    """When pyproject has a [project.entry-points."haywire.libraries"] block, infer module
    name from there. Otherwise fall back to the package directory name with hyphens → underscores."""
    root = tmp_path / "pyproject.toml"
    root.write_text(
        '[tool.uv.workspace]\nmembers = ["pkgs/*"]\n'
        '[tool.haywire.release]\npublish_order = ["haybale-foo"]\nlockstep_unpublished = []\n'
        '[tool.haywire.marketstall]\n'
        'source_url = "https://github.com/example/fake-workspace"\n'
        'docs_branch = "main"\n'
        'default_author = ""\n'
        'default_tags = []\n'
    )
    pkg = tmp_path / "pkgs/haybale-foo"
    pkg.mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.0.1"\ndescription = "d"\ndependencies = []\n'
        '[project.entry-points."haywire.libraries"]\nfoo = "haybale_foo_renamed:Library"\n'
    )
    (pkg / "haybale_foo_renamed").mkdir()
    (pkg / "haybale_foo_renamed" / "__init__.py").write_text('"""foo."""\n')

    import tomllib
    parsed = tomllib.loads(generate_marketstall.generate(root))
    assert parsed["packages"][0]["docs_url"].endswith("/pkgs/haybale-foo/haybale_foo_renamed/")
```

- [ ] **Step 2: Run, confirm FAIL**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 8 pass, 2 fail with `AttributeError: ... generate`.

- [ ] **Step 3: Implement `generate(...)` + `main(...)`**

Append to `scripts/generate_marketstall.py`:

```python
def generate(root_pyproject: Path) -> str:
    """Build the full marketplace TOML for the workspace.

    Reads:
      - [tool.haywire.release] publish_order (consumed via bump_version)
      - [tool.haywire.marketstall] (defaults)
      - each publishable package's pyproject + __init__.py

    Returns the rendered TOML text.
    """
    # Reuse bump_version's package-location logic — same workspace-globs scan.
    from scripts.bump_version import locate_packages, read_release_config

    release = read_release_config(root_pyproject)
    located = locate_packages(root_pyproject, release)
    config = read_marketstall_config(root_pyproject)
    root_dir = root_pyproject.parent

    entries: list[dict[str, object]] = []
    for pkg_name in release.publish_order:
        pyproject_path = located[pkg_name]
        pkg_dir = pyproject_path.parent
        module_name = _resolve_module_name(pyproject_path, pkg_dir)
        init_py = pkg_dir / module_name / "__init__.py"
        subdirectory = pkg_dir.relative_to(root_dir).as_posix()
        entries.append(
            build_entry(
                pyproject_path=pyproject_path,
                init_py=init_py,
                config=config,
                subdirectory=subdirectory,
                module_name=module_name,
            )
        )

    return emit_marketstall_toml(entries)


def _resolve_module_name(pyproject_path: Path, pkg_dir: Path) -> str:
    """Find the importable module dir name.

    Priority:
      1. [project.entry-points."haywire.libraries"] — first value before `:`.
      2. The package directory name with hyphens converted to underscores.
    """
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    entry_points = data.get("project", {}).get("entry-points", {}).get("haywire.libraries", {})
    if entry_points:
        first_target = next(iter(entry_points.values()))
        return first_target.split(":")[0]
    return pkg_dir.name.replace("-", "_")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_marketstall",
        description="Generate the official haywire marketplace TOML.",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("pyproject.toml"),
        help="Path to the workspace root pyproject.toml (default: ./pyproject.toml).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output path. If omitted, prints to stdout.",
    )
    args = parser.parse_args(argv)

    text = generate(args.root)
    if args.out is None:
        sys.stdout.write(text)
    else:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run, confirm GREEN**

```bash
uv run pytest tests/scripts/test_generate_marketstall.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Smoke-test against the real workspace**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python scripts/generate_marketstall.py
```

Expected: a TOML document on stdout with:
- The header comment.
- Exactly 7 `[[packages]]` entries (matching `publish_order`).
- Each `name` matches the release-config order: `haywire-core`, `haywire-studio`, `haybale-core`, `haybale-studio`, `haybale-graph-editor`, `haybale-haystack`, `haybale-example`.
- Each `min_version = "0.0.1"`.
- Each `source = "pypi"`.
- Each `dependencies` is bare haybale-* names only (e.g. `haybale-haystack` has `dependencies = ["haybale-studio", "haybale-graph-editor"]`; `haywire-core` has `dependencies = []`).
- Each `docs_url` is `https://raw.githubusercontent.com/maybites/haywire/main/<subdir>/<module>/`.

Pipe it through `tomllib` to verify it round-trips:

```bash
uv run python scripts/generate_marketstall.py | uv run python -c "
import sys, tomllib
parsed = tomllib.loads(sys.stdin.read())
print(f'{len(parsed[\"packages\"])} packages:')
for p in parsed['packages']:
    print(f'  {p[\"name\"]:25s} v{p[\"min_version\"]}  deps={p[\"dependencies\"]}')
"
```

Expected: `7 packages:` followed by 7 lines. Final line is `haybale-example` with `deps=['haybale-core']` (per its pyproject).

- [ ] **Step 6: Try writing to a file**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python scripts/generate_marketstall.py --out /tmp/test_marketstall.toml
cat /tmp/test_marketstall.toml | head -20
rm /tmp/test_marketstall.toml
```

Expected: stderr says `Wrote /tmp/test_marketstall.toml`, the file's first 20 lines are the header + the first `[[packages]]` block.

- [ ] **Step 7: Lint + type-check**

```bash
uv run ruff check scripts/generate_marketstall.py tests/scripts/
uv run mypy scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add scripts/generate_marketstall.py tests/scripts/test_generate_marketstall.py
git commit -m "$(cat <<'EOF'
feat(scripts): generate() + CLI for the marketstall generator

Orchestrates the pipeline: read release config (via bump_version's
read_release_config + locate_packages), read marketstall config,
walk publish_order, build one entry per package, render TOML.

The CLI accepts --root and --out flags. Default is to print to
stdout; --out writes to a file (used by the CI workflow). Module
name is inferred from [project.entry-points."haywire.libraries"]
when present, otherwise from the package directory name.

Implements spec T3 in full.

Refs spec internals/specs/versioning-and-publishing.md T3, §7.
EOF
)"
```

---

### Task 9: Update `scripts/README.md`

**Files:**
- Modify: `scripts/README.md`

- [ ] **Step 1: Replace the placeholder row + add a section**

The existing `scripts/README.md` lists `generate_marketstall.py` as `(planned)`. Update the row and add a usage section after the `bump_version.py` section.

Read the current file first to know its exact content (it was created in Plan A Task 18). Then replace the row:

```
| `generate_marketstall.py` | (planned) CI marketstall generator for the published packages.  |
```

with:

```
| `generate_marketstall.py` | CI marketstall generator for the published packages.            |
```

And append at the end of the file (after the existing `bump_version.py` section's last line `… not the script.`):

````markdown

## generate_marketstall.py

```bash
# Print the generated marketplace to stdout.
uv run python scripts/generate_marketstall.py

# Write to a file (used by the publish workflow).
uv run python scripts/generate_marketstall.py --out dist/marketplace.toml
```

Reads `[tool.haywire.release].publish_order` and `[tool.haywire.marketstall]` from
the workspace root `pyproject.toml`. For each publishable package, lifts
`label` / `description` / `author` / `tags` from the package's `@library`
decorator and falls back to the pyproject `description` and `[tool.haywire.marketstall]`
defaults when the decorator omits a field.

The output is deployed to GitHub Pages on every release tag by
`.github/workflows/publish.yml`. Subscribers fetch it from
`https://maybites.github.io/haywire/marketplace.toml`.
````

- [ ] **Step 2: Verify the file still renders sensibly**

```bash
cat scripts/README.md
```

Expected: clean markdown, table renders, both sections present.

- [ ] **Step 3: Commit**

```bash
git add scripts/README.md
git commit -m "docs(scripts): document generate_marketstall.py usage"
```

---

### Task 10: PyPI Trusted Publisher prerequisites (documentation only)

**Files:**
- Create: `docs/reference/publish_releases.md`

The workflow file in Task 11–13 assumes PyPI Trusted Publisher is configured. That setup is a one-time human action (PyPI project settings → "Add a new trusted publisher" → GitHub → fill in repo/workflow/environment). Document it here so future maintainers know the prerequisite.

- [ ] **Step 1: Create the operational doc**

Create `docs/reference/publish_releases.md`:

```markdown
# Publishing Haywire Releases

This document covers the operational side of releasing haywire — what needs to be in
place before a tag can publish, how the workflow runs end-to-end, and how to recover
from a partial publish. The spec at
`internals/specs/versioning-and-publishing.md` (§ release flow) is the canonical source
of truth for *what* the pipeline does; this doc covers *how to operate it*.

## Prerequisites (one-time)

### PyPI Trusted Publisher

Each Tier 1+2 package in `[tool.haywire.release].publish_order` must be registered as
a Trusted Publisher on PyPI before the first publish workflow run.

For each package name in `publish_order`:

1. Reserve the project on PyPI: create an account, claim the name (if not already
   present), then go to **Project → Settings → Publishing**.
2. Click **Add a new pending publisher** (for first-time projects) or **Add a new
   trusted publisher** (for already-published projects).
3. Fill in:
   - **Owner:** `maybites`
   - **Repository name:** `haywire`
   - **Workflow name:** `publish.yml`
   - **Environment name:** `pypi` (matches `.github/workflows/publish.yml`)
4. Save. Repeat for every package.

No PyPI API tokens are needed. The workflow authenticates via OIDC.

### GitHub Pages

The workflow's final job deploys the generated marketplace to GitHub Pages on the
`gh-pages` branch. Enable Pages once:

1. Repo **Settings → Pages**.
2. **Source:** Deploy from a branch.
3. **Branch:** `gh-pages` / `/ (root)`.
4. Save.

The first publish workflow run creates the `gh-pages` branch automatically. After
that, the URL `https://maybites.github.io/haywire/marketplace.toml` resolves.

## Cutting a release

The /haywire-release skill (T8 in the spec — separate plan) walks the author through
the full flow. The summary:

```sh
# 1. Run the bump script (preview + apply).
uv run python scripts/bump_version.py 0.0.2

# 2. Commit the version bump.
git add packages/*/pyproject.toml barn/*/pyproject.toml uv.lock
git commit -m "chore: release v0.0.2"

# 3. Tag and push.
git tag v0.0.2
git push origin main v0.0.2
```

CI takes over on `v0.0.2`. Job sequence (see `.github/workflows/publish.yml`):

1. **gate** — `pytest -m "not integration"`. Fails → pipeline stops.
2. **build** — `uv build --package <name>` for every package in `publish_order`,
   collected as workflow artifacts.
3. **publish** — sequential `uv publish` in `publish_order`. For each, the workflow
   first probes PyPI's JSON API (`GET /pypi/<name>/<version>/json`) to skip
   already-published versions. Trusted Publisher (OIDC) authenticates.
4. **deploy** — runs `scripts/generate_marketstall.py --out marketplace.toml` and
   pushes that file to the `gh-pages` branch via `peaceiris/actions-gh-pages`.

## Recovering from a partial publish

If job 3 fails partway (transient PyPI error, Trusted-Publisher misconfiguration for
one package), fix the underlying issue and re-run the workflow on the same tag:

```sh
gh workflow run publish.yml --ref v0.0.2
```

The idempotent skip means already-published packages are skipped; the workflow picks
up at the failed package and continues. Job 4 runs once all packages are published.

**Do not bump the version on partial failure.** PyPI versions stay monotonic;
re-running at the same tag is the canonical recovery.

If a package was rejected by PyPI for irrecoverable metadata reasons, bump and cut a
new release.

## Adding a new package to the release set

1. Add the pip distribution name to `[tool.haywire.release].publish_order` in the
   workspace root `pyproject.toml`.
2. Register the new package as a Trusted Publisher on PyPI (see prerequisites above).
3. Confirm `uv build --package <name>` works locally.
4. Confirm `uv run python scripts/generate_marketstall.py` includes the package.
5. Cut the next release; the new package will publish on the same tag as the rest.

## Moving a package between tiers

To move a package from `lockstep_unpublished` to `publish_order` (i.e., start
publishing it), do the steps above. To stop publishing a package, remove it from
`publish_order` (and consider moving it to `lockstep_unpublished` so the bump script
still keeps its version in lockstep). The PyPI registration stays in place — PyPI
does not let you "unpublish", but skipping further releases is enough.
```

- [ ] **Step 2: Commit**

```bash
git add docs/reference/publish_releases.md
git commit -m "$(cat <<'EOF'
docs: publish_releases.md — operational guide for the release flow

Covers Trusted Publisher + Pages prerequisites, the cut-a-release
recipe, recovery from partial publish, and adding/moving packages
between tiers. The spec covers what the pipeline does; this doc
covers how to operate it.

Referenced from internals/specs/versioning-and-publishing.md §5.
EOF
)"
```

---

### Task 11: Workflow — gate + build jobs

**Files:**
- Create: `.github/workflows/publish.yml`

This task lays down the first two jobs. Tasks 12 and 13 add the publish and deploy jobs.

- [ ] **Step 1: Create the workflow file with the first two jobs**

Create `.github/workflows/publish.yml`:

```yaml
name: Publish Release

on:
  push:
    tags:
      - 'v*.*.*'
  workflow_dispatch:

# Permissions: id-token for PyPI OIDC (added in the publish job below).
# Default GITHUB_TOKEN permissions are restricted; jobs that need more
# raise them explicitly.

env:
  PYTHON_VERSION: '3.12'

jobs:
  gate:
    name: Test gate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install workspace
        run: uv sync --dev

      - name: Run fast test suite (gate)
        run: uv run pytest -m "not integration" -q

  build:
    name: Build wheels
    runs-on: ubuntu-latest
    needs: gate
    outputs:
      packages: ${{ steps.read-config.outputs.packages }}
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install workspace
        run: uv sync --dev

      - name: Read publish_order from [tool.haywire.release]
        id: read-config
        run: |
          packages=$(uv run python -c "
          import json, tomllib, pathlib
          d = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
          print(json.dumps(d['tool']['haywire']['release']['publish_order']))
          ")
          echo "packages=$packages" >> "$GITHUB_OUTPUT"
          echo "Will build: $packages"

      - name: Build every wheel + sdist
        run: |
          rm -rf dist/
          uv run python -c "
          import json, subprocess, sys
          packages = json.loads('${{ steps.read-config.outputs.packages }}')
          for name in packages:
              print(f'::group::Building {name}')
              r = subprocess.run(['uv', 'build', '--package', name], check=False)
              print('::endgroup::')
              if r.returncode != 0:
                  print(f'::error::Build failed for {name}', file=sys.stderr)
                  sys.exit(1)
          "

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: wheels
          path: dist/
          retention-days: 7
          if-no-files-found: error
```

- [ ] **Step 2: Validate the YAML parses cleanly**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python -c "
import sys
try:
    import yaml
except ImportError:
    print('PyYAML not installed in the venv — installing temporarily...')
    sys.exit(0)
print(yaml.safe_load(open('.github/workflows/publish.yml').read())['name'])
"
```

If PyYAML isn't available, use a simpler check:

```bash
uv run python -c "
import json, subprocess
out = subprocess.run(['python', '-c', 'import yaml; yaml.safe_load(open(\".github/workflows/publish.yml\").read())'], capture_output=True, text=True)
print('YAML parses' if out.returncode == 0 else 'YAML parse FAILED')
print(out.stderr)
"
```

If neither works (PyYAML simply isn't in this project — it's not in `pyproject.toml`'s dev deps), use a syntactic regex check:

```bash
grep -c "^jobs:\|^name:\|^on:" .github/workflows/publish.yml
```

Expected: at least 3 (matches `name:`, `on:`, `jobs:`).

A more rigorous approach: install `pyyaml` ad-hoc:

```bash
uv run --with pyyaml python -c "
import yaml
data = yaml.safe_load(open('.github/workflows/publish.yml').read())
print('name:', data['name'])
print('jobs:', list(data['jobs'].keys()))
"
```

Expected: `name: Publish Release`, `jobs: ['gate', 'build']`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "$(cat <<'EOF'
ci(publish): add gate + build jobs of the publish workflow

Triggers on v*.*.* tags. Gate runs the fast test suite; on success
build walks [tool.haywire.release].publish_order, runs uv build for
every package, and uploads the resulting wheels and sdists as a
workflow artifact for the downstream publish job (next commit).

Refs spec internals/specs/versioning-and-publishing.md (release flow
job 1 + job 2).
EOF
)"
```

---

### Task 12: Workflow — sequential publish job

**Files:**
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Append the publish job**

Append at the end of `.github/workflows/publish.yml` (after the `build:` job, at the same indentation level — inside `jobs:`):

```yaml

  publish:
    name: Publish to PyPI
    runs-on: ubuntu-latest
    needs: build
    environment:
      name: pypi
      url: https://pypi.org/project/haywire-core/
    permissions:
      id-token: write   # required for Trusted Publisher (OIDC)
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install workspace
        run: uv sync --dev

      - name: Download wheels artifact
        uses: actions/download-artifact@v4
        with:
          name: wheels
          path: dist/

      - name: Read publish_order
        id: read-config
        run: |
          packages=$(uv run python -c "
          import json, tomllib, pathlib
          d = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
          print(json.dumps(d['tool']['haywire']['release']['publish_order']))
          ")
          echo "packages=$packages" >> "$GITHUB_OUTPUT"

      - name: Publish each package (sequential, idempotent, fail-fast)
        run: |
          uv run python <<'PY'
          import json, os, pathlib, subprocess, sys, urllib.request

          packages = json.loads(os.environ["PACKAGES"])
          dist_root = pathlib.Path("dist")

          # All artifacts live in a flat dist/ — group by package prefix.
          # uv build names them <pkg_underscore>-<version>(.tar.gz|-py3-none-any.whl).
          # Trusted Publisher's uv publish reads the dist/ root; we point it
          # at per-package globs to keep one publish call per package
          # (fail-fast semantics).
          for name in packages:
              underscore = name.replace("-", "_")
              # Read version from the workspace pyproject for this package — every
              # publishable package is at the same version (lockstep release).
              data = tomllib.loads(pathlib.Path("pyproject.toml").read_text())  # type: ignore[name-defined]
              # Locate the package's pyproject the same way generate_marketstall does:
              # via [tool.uv.workspace].members. Reuse the bump_version helper.
              from scripts.bump_version import read_release_config, locate_packages

              cfg = read_release_config(pathlib.Path("pyproject.toml"))
              located = locate_packages(pathlib.Path("pyproject.toml"), cfg)
              pkg_pyproject = located[name]
              import tomllib  # local re-import for clarity inside the heredoc
              pkg_data = tomllib.loads(pkg_pyproject.read_text())
              version = pkg_data["project"]["version"]

              # PyPI JSON API: 200 means already published.
              url = f"https://pypi.org/pypi/{name}/{version}/json"
              try:
                  with urllib.request.urlopen(url, timeout=15) as r:
                      already_published = r.status == 200
              except Exception:
                  already_published = False

              if already_published:
                  print(f"::notice::{name}=={version} already on PyPI — skipping.")
                  continue

              print(f"::group::Publishing {name}=={version}")
              files = list(dist_root.glob(f"{underscore}-{version}*"))
              if not files:
                  print(f"::error::No artifacts in dist/ for {name}=={version}", file=sys.stderr)
                  sys.exit(1)

              r = subprocess.run(
                  ["uv", "publish", "--trusted-publishing", "always", *[str(f) for f in files]],
                  check=False,
              )
              print("::endgroup::")
              if r.returncode != 0:
                  print(f"::error::Publish failed for {name}=={version}", file=sys.stderr)
                  sys.exit(1)
          PY
        env:
          PACKAGES: ${{ steps.read-config.outputs.packages }}
```

(Heredoc note: GitHub Actions `run:` interprets `${{ … }}` substitutions, so we pass `packages` via the `PACKAGES` env var rather than interpolating into the heredoc directly — keeps the inline Python clean.)

There's a bug in the heredoc above: `import tomllib` happens after first use. Rewrite the step body more cleanly:

```yaml
      - name: Publish each package (sequential, idempotent, fail-fast)
        run: |
          uv run python <<'PY'
          import json, os, pathlib, subprocess, sys, tomllib, urllib.request
          from scripts.bump_version import locate_packages, read_release_config

          packages = json.loads(os.environ["PACKAGES"])
          dist_root = pathlib.Path("dist")
          root = pathlib.Path("pyproject.toml")
          cfg = read_release_config(root)
          located = locate_packages(root, cfg)

          for name in packages:
              underscore = name.replace("-", "_")
              pkg_data = tomllib.loads(located[name].read_text())
              version = pkg_data["project"]["version"]

              url = f"https://pypi.org/pypi/{name}/{version}/json"
              try:
                  with urllib.request.urlopen(url, timeout=15) as r:
                      already_published = r.status == 200
              except Exception:
                  already_published = False

              if already_published:
                  print(f"::notice::{name}=={version} already on PyPI — skipping.")
                  continue

              files = list(dist_root.glob(f"{underscore}-{version}*"))
              if not files:
                  print(f"::error::No artifacts in dist/ for {name}=={version}", file=sys.stderr)
                  sys.exit(1)

              print(f"::group::Publishing {name}=={version}")
              r = subprocess.run(
                  ["uv", "publish", "--trusted-publishing", "always", *[str(f) for f in files]],
                  check=False,
              )
              print("::endgroup::")
              if r.returncode != 0:
                  print(f"::error::Publish failed for {name}=={version}", file=sys.stderr)
                  sys.exit(1)
          PY
        env:
          PACKAGES: ${{ steps.read-config.outputs.packages }}
```

Use this cleaner version.

- [ ] **Step 2: Validate YAML parses**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run --with pyyaml python -c "
import yaml
data = yaml.safe_load(open('.github/workflows/publish.yml').read())
print('jobs:', list(data['jobs'].keys()))
"
```

Expected: `jobs: ['gate', 'build', 'publish']`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "$(cat <<'EOF'
ci(publish): add sequential PyPI publish job (Trusted Publisher OIDC)

Runs after build. Reads [tool.haywire.release].publish_order, for
each package downloads the artifact, queries the PyPI JSON API for
prior publication (skip on 200 — idempotent), and runs uv publish
with --trusted-publishing always. Fail-fast: any non-200 from
uv publish stops the remaining packages so partial state can be
diagnosed before the next attempt.

Refs spec internals/specs/versioning-and-publishing.md (release flow
job 3).
EOF
)"
```

---

### Task 13: Workflow — marketstall deploy job

**Files:**
- Modify: `.github/workflows/publish.yml`

- [ ] **Step 1: Append the deploy job**

Append at the end of `.github/workflows/publish.yml`:

```yaml

  deploy-marketstall:
    name: Deploy marketstall to GitHub Pages
    runs-on: ubuntu-latest
    needs: publish
    permissions:
      contents: write   # required to push the gh-pages branch
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true

      - name: Set up Python ${{ env.PYTHON_VERSION }}
        run: uv python install ${{ env.PYTHON_VERSION }}

      - name: Install workspace
        run: uv sync --dev

      - name: Generate marketplace.toml
        run: |
          mkdir -p gh-pages-content
          uv run python scripts/generate_marketstall.py \
              --out gh-pages-content/marketplace.toml

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./gh-pages-content
          publish_branch: gh-pages
          force_orphan: false
          keep_files: true
          commit_message: "Deploy marketplace for ${{ github.ref_name }}"
```

(`keep_files: true` means existing files on `gh-pages` are preserved — only `marketplace.toml` is overwritten. `force_orphan: false` keeps a normal git history on the branch.)

- [ ] **Step 2: Validate YAML parses + has all 4 jobs**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run --with pyyaml python -c "
import yaml
data = yaml.safe_load(open('.github/workflows/publish.yml').read())
jobs = list(data['jobs'].keys())
print('jobs:', jobs)
assert jobs == ['gate', 'build', 'publish', 'deploy-marketstall'], f'unexpected: {jobs}'
print('OK — all 4 jobs present in the expected order.')
"
```

Expected: prints `jobs: ['gate', 'build', 'publish', 'deploy-marketstall']` and `OK ...`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "$(cat <<'EOF'
ci(publish): add marketstall deploy job → GitHub Pages

Final job in the release pipeline. Runs after publish succeeds.
Renders the official monorepo marketplace via
scripts/generate_marketstall.py and pushes it to the gh-pages
branch so subscribers can fetch
https://maybites.github.io/haywire/marketplace.toml.

Implements spec T4 in full.

Refs spec internals/specs/versioning-and-publishing.md (release flow
job 4).
EOF
)"
```

---

### Task 14: End-to-end dry-run of the generator against the live workspace

This is a verification task — no edits. Make sure the generator's output, when run against the real repo at v0.0.1, is what we'd want PyPI subscribers to see.

**Files:** read-only.

- [ ] **Step 1: Generate and inspect**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run python scripts/generate_marketstall.py --out /tmp/marketplace.toml
cat /tmp/marketplace.toml
```

Walk through the output mentally:

- **Header comment** present at top.
- **7 `[[packages]]` blocks**, in the order: `haywire-core`, `haywire-studio`, `haybale-core`, `haybale-studio`, `haybale-graph-editor`, `haybale-haystack`, `haybale-example`.
- For each entry:
  - `name` matches the directory's `[project] name`.
  - `label` lifted from `@library(label=...)` (or falls back to `name`). Expected: `"Haywire Core"`, `"Haywire Studio"` (or fall back; `haywire-*` packages don't have `@library` decorators because they're framework, not libraries — confirm this in step 2), `"Haywire Core"` for haybale-core, `"Haywire Studio"` for haybale-studio (per the `@library` decorator), `"Graph Editor"`, `"Haystack"`, `"Example"`.
  - `min_version = "0.0.1"`.
  - `source = "pypi"`.
  - `install_spec = "<name>"`.
  - `dependencies` is bare haybale-* names only.

- [ ] **Step 2: Handle the haywire-core / haywire-studio case**

`haywire-core` and `haywire-studio` are framework packages with no `@library` decorator. So `extract_library_metadata` returns all-None and `build_entry` falls back to:
- `label = name` (e.g., `"haywire-core"`)
- `description = pyproject.description` (e.g., `"Haywire Node System Framework"`)
- `author = config.default_author` (`"Haywire Team"`)
- `tags = config.default_tags` (`[]`)

Verify this in the output. If `label` shows `"haywire-core"` (the bare name), that's correct fallback behavior — there's no `@library` decorator to lift a friendlier label from.

If the result feels jarring, consider whether the spec actually wants haywire-core/haywire-studio in the marketplace at all. Re-read spec §7 `Producers` (line 488–496): the official `scripts/generate_marketstall.py` produces entries with `source = "pypi"`, and per §5 the publish_order includes them. So yes — they go in the marketplace, with their pyproject-derived label/description.

If you want fancier labels for the framework packages, the right fix is to add them via `[tool.haywire.marketstall.overrides.haywire-core]` etc. in the root pyproject. **That's out of scope for this plan.** Open a follow-up issue and move on.

- [ ] **Step 3: Verify the output round-trips**

```bash
uv run python -c "
import tomllib, sys
with open('/tmp/marketplace.toml') as f:
    parsed = tomllib.loads(f.read())
print(f'{len(parsed[\"packages\"])} packages parsed')
for p in parsed['packages']:
    keys = sorted(p.keys())
    expected = ['author', 'dependencies', 'description', 'docs_url', 'install_spec',
                'label', 'min_version', 'name', 'source', 'source_url', 'tags']
    assert keys == expected, f'unexpected keys for {p[\"name\"]}: {keys}'
print('OK — every package has exactly the 11 spec-§7 _TOML_FIELDS keys.')
"
rm /tmp/marketplace.toml
```

Expected: `7 packages parsed`, then `OK — every package has exactly the 11 spec-§7 _TOML_FIELDS keys.`

---

### Task 15: Final verification

**Files:** read-only.

- [ ] **Step 1: Run the full fast test suite**

```bash
cd /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo
uv run pytest -m "not integration" -q
```

Expected: every test passes. Baseline at start of Plan B was 1143 passed (Plan A's tally). This plan adds 10 tests for the marketstall generator (2 in T5, 3 in T6, 3 in T7, 2 in T8). Expected: 1153 passed / 1 skipped / 75 deselected.

- [ ] **Step 2: Run ruff across the whole repo**

```bash
uv run ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 3: Run mypy on the new file**

```bash
uv run mypy scripts/bump_version.py scripts/generate_marketstall.py
```

Expected: clean.

- [ ] **Step 4: Verify `git log` shows the planned commit sequence on top of the squashed Plan A commit**

```bash
git log --oneline -20
```

Expected: at the top, the sequence from this plan:

```
<sha> ci(publish): add marketstall deploy job → GitHub Pages
<sha> ci(publish): add sequential PyPI publish job (Trusted Publisher OIDC)
<sha> ci(publish): add gate + build jobs of the publish workflow
<sha> docs: publish_releases.md — operational guide for the release flow
<sha> docs(scripts): document generate_marketstall.py usage
<sha> feat(scripts): generate() + CLI for the marketstall generator
<sha> feat(scripts): emit_marketstall_toml — hand-written TOML emitter
<sha> feat(scripts): build_entry — assemble one marketstall entry
<sha> feat(scripts): generate_marketstall skeleton + @library AST parser
<sha> test(scripts): fixtures for the marketstall generator
<sha> chore: add [tool.haywire.marketstall] generator config
<sha> fix(haywire-core): drop broken readme path that blocks uv build
28537691 feat: versioning migration + bump_version.py script   <-- Plan A squashed tip
78a52a5f new versioning and publishing specs
```

- [ ] **Step 5: Confirm the YAML workflow parses with all 4 jobs**

```bash
uv run --with pyyaml python -c "
import yaml
data = yaml.safe_load(open('.github/workflows/publish.yml').read())
jobs = list(data['jobs'].keys())
print('jobs:', jobs)
assert jobs == ['gate', 'build', 'publish', 'deploy-marketstall']
print('Workflow is well-formed.')
"
```

Expected: prints the 4 job names and `Workflow is well-formed.`

- [ ] **Step 6: Confirm the bump script still works**

```bash
uv run python scripts/bump_version.py 0.0.1 --dry-run
```

Expected: `Nothing to do: all packages already at version 0.0.1.` — confirms Plan A's bump script wasn't disrupted by this plan's changes.

- [ ] **Step 7: Confirm git is clean**

```bash
git status --short
```

Expected: only `?? docs/superpowers/` (still untracked, pre-existing).

---

## Self-Review (already performed by the plan author)

### Spec coverage

- §5 canonical list (consumer side) — generator reads `[tool.haywire.release].publish_order` via the existing helpers from `bump_version.py`. ✅ Task 8.
- §7 marketstall file format — all 11 spec-§7 `_TOML_FIELDS` keys emitted, in spec order. ✅ Tasks 6–8 + Task 14 verification.
- §7 `Producers` row for `scripts/generate_marketstall.py` — every entry has `source = "pypi"`. ✅ Task 6.
- §7 `dependencies` field semantics (bare haybale-* names only) — `_filter_haybale_siblings` strips haywire-* and externals. ✅ Task 6.
- §7 `docs_url` for PyPI packages — `https://raw.githubusercontent.com/{user/repo}/{branch}/{subdir}/{module}/`. ✅ Task 6.
- Release flow Job 1 (gate) — `pytest -m "not integration"`. ✅ Task 11.
- Release flow Job 2 (build all wheels as artifacts, fail-fast) — `uv build --package` per `publish_order`, uploaded as one artifact. ✅ Task 11.
- Release flow Job 3 (sequential publish, idempotent via PyPI API skip, fail-fast, Trusted Publisher OIDC) — every property covered. ✅ Task 12.
- Release flow Job 4 (marketstall deploy to GitHub Pages, only on publish success) — `needs: publish` + `peaceiris/actions-gh-pages`. ✅ Task 13.
- Recovery from partial publish — idempotent skip is the mechanism. Documented in `publish_releases.md` Task 10. ✅
- The pre-existing readme issue (Plan A follow-up flagged by reviewers) — fixed in Task 2. ✅

### Out of scope (deferred to other plans)

- `haywire share` / `haywire init` (T5, T6) — separate plan.
- `/haywire-release` skill (T8) — separate plan.
- Two-tier marketplace runtime / `haywire-marketplace` UI (T7, T11) — separate plan(s).
- `haywire-gen-docs` update (T9) — separate plan; will also be the right time to add per-package READMEs.
- Pretty labels/descriptions for haywire-core/haywire-studio in the marketstall — pyproject-derived fallback works; nicer labels need a `[tool.haywire.marketstall.overrides]` block, separate follow-up.

### Placeholder scan

No "TBD", "implement later", "similar to Task N" — every code step contains the actual code. ✅

### Type / signature consistency

- `LibraryMetadata` introduced in Task 5, used in Task 6 (`build_entry`). Fields match. ✅
- `MarketstallConfig` introduced in Task 6, used in Task 8 (`generate`). Fields match. ✅
- `extract_library_metadata` / `read_marketstall_config` / `build_entry` / `emit_marketstall_toml` / `generate` signatures consistent across the tasks where they're defined and called. ✅
- `scripts.bump_version.read_release_config` and `locate_packages` reused in Task 8's `generate` and Task 12's publish step. Existing Plan A signatures unchanged. ✅
- Workflow job names referenced via `needs:` (Task 11 `gate` → Task 12 `publish needs: build` → Task 13 `deploy-marketstall needs: publish`). All match. ✅

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-18-ci-publish-and-marketstall-generator.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute in this session with checkpoints.

Which approach?
