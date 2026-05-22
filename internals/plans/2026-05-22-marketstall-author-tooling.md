# Marketstall Author Tooling — Slice 2 Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `haywire init` and `haywire share` to the new marketstall vocabulary, validate the `os` field, compute share URLs via host providers, write README marker blocks, and extend `haybale-gen-docs` to generate README.md with marker-pair preservation. After this slice, the author publish flow produces `marketstall.toml` files with the new `[[haybales]]` schema (including `os`) and authors get a copy-friendly share URL inserted into their READMEs.

**Architecture:** Three independent surfaces, but they meet at the README marker contract. (1) `haywire share` emits `[[haybales]]` instead of `[[packages]]`, reads `[tool.haywire].os`, derives the share URL via `HostProvider.blob_url(...)`, and updates README marker blocks. (2) `haywire init` writes README.md scaffolds with placeholder marker blocks so the author's first `haywire share` replaces them with real URLs. (3) `haybale-gen-docs` gains README.md generation AND a marker-preservation rule so the two skills compose. Built on the foundation slice (`haywire.core.marketstall.*` already exists).

**Tech Stack:** Python 3.12, `dataclasses`, `toml` library, `pytest`. `haywire.core.marketstall.host_providers.resolve_host()` for URL derivation. No new third-party deps.

**Spec reference:** [`internals/specs/marketstall-distribution.md`](../specs/marketstall-distribution.md). §2.1 (os validation), §6 (share command), §6.2 (output), §6.3 (failure modes), §6.4 (URL-only re-run), §6.5 (other share modes), §6.6 (README markers).

**Inquisition decisions this slice implements:** Q6 (os Edit dialog scope — code-side validation only; UI is slice 4), Q7 (gen-docs marker preservation — full README generation included per user choice).

---

## File Structure

### New files

- `tests/test_share_haybales.py` — share's `[[haybales]]` emission + os validation + host-provider URL derivation tests.
- `tests/test_share_readme_markers.py` — README marker rewrite roundtrip tests.
- `tests/test_init_readme_scaffold.py` — init's README scaffolding (root + barn) tests.
- `tests/test_gen_docs_readme.py` — gen-docs README generation + marker preservation tests (skill-as-library tests: small driver script that invokes the README generation logic factored out into a Python helper).

### Modified files

- `packages/haywire-studio/src/haywire_studio/share.py` — section name `[[packages]]` → `[[haybales]]`; read+validate `[tool.haywire].os` per library; derive share URL via host provider; write README marker blocks at root + each `barn/*/README.md`. New CLI flag `--no-update-readme`.
- `packages/haywire-studio/src/haywire_studio/init.py` — scaffold root `README.md` with marker-pair placeholder; scaffold `barn/haybale-<name>/README.md` with same marker-pair placeholder.
- `.claude/skills/haybale-gen-docs/SKILL.md` — add README.md generation step + marker-pair preservation rule.
- `.claude/skills/haybale-gen-docs/format-spec.md` — add README.md canonical format.
- `docs/reference/glossary.md` — update README.md/haybale-gen-docs entries to be accurate (currently aspirational).
- `tests/test_share_drift.py` and `tests/test_share_save.py` — adjust for new section name + new `os` field if asserted; minimal touches.
- `tests/test_init_scaffolding.py` — extend with marker-presence assertions.

### Files NOT touched in this slice (deferred)

- `scripts/generate_marketstall.py` — per-haybale stall generator, slice 8.
- Add Source dialog, Library Browser UI changes, install-safety modal — UI slices (3–5).
- Drift gate `min_version` lag check on haybale-* deps — slice 6.
- Update-available signal — slice 7.

---

## Pre-flight Baseline

- [ ] **Step 0.1: Confirm worktree state**

Run: `git -C /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/.worktrees/marketstall-author-tooling status`
Expected: clean working tree on `feat/marketstall-author-tooling`.

- [ ] **Step 0.2: Run the existing test suite as the baseline**

Run: `uv run pytest tests/ -m "not integration" -q` from the worktree.
Expected: `1349 passed, 1 skipped, 75 deselected`. Record any deviation.

- [ ] **Step 0.3: Run ruff and mypy as baseline**

Run from the worktree:
```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share.py packages/haywire-studio/src/haywire_studio/init.py
uv run mypy packages/haywire-studio/src/haywire_studio/share.py packages/haywire-studio/src/haywire_studio/init.py
```
Both must be clean.

---

## Task 1: `haywire share` emits `[[haybales]]` instead of `[[packages]]`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Modify: `tests/test_share_save.py` (existing) — adjust for new section name

This is the smallest possible breaking-rename task that lands the new vocabulary in the share emission. Three locations in `share.py` reference `"packages"` literally:

1. `share_library()` — prints `toml.dumps({"packages": [entry]}).strip()` for the single-library stdout snippet.
2. `share_save_repo()` — writes `toml.dumps({"packages": entries})` to `marketstall.toml`.
3. The comment header on `marketstall.toml` — currently says "marketstall.toml — share this file's raw URL…"; no section-name reference but verify.

- [ ] **Step 1.1: Locate the literal `"packages"` strings**

Run from the worktree:
```sh
grep -n '"packages"' packages/haywire-studio/src/haywire_studio/share.py
```
Expected: 2-3 matches.

- [ ] **Step 1.2: Write a failing test**

Read the existing `tests/test_share_save.py` to understand the fixture pattern. Identify any assertion that currently checks for `[[packages]]` in the generated output — those assertions will flip to `[[haybales]]`.

Add (or update) a test in `tests/test_share_save.py` that asserts the rendered `marketstall.toml` contains `[[haybales]]` and does NOT contain `[[packages]]`:

```python
@pytest.mark.unit
def test_share_save_emits_haybales_section_not_packages(tmp_path: Path) -> None:
    """Per spec §1: marketstall.toml uses [[haybales]] not [[packages]]."""
    repo = _scaffold_minimal_repo(tmp_path)  # use existing fixture helper
    from haywire_studio.share import share_save_repo

    out_path = share_save_repo(repo)
    content = out_path.read_text()
    assert "[[haybales]]" in content
    assert "[[packages]]" not in content
```

(If `_scaffold_minimal_repo` doesn't exist in the test file, write a small inline fixture or use the existing helper pattern from the file.)

- [ ] **Step 1.3: Run the test to confirm it fails**

Run: `uv run pytest tests/test_share_save.py::test_share_save_emits_haybales_section_not_packages -v`
Expected: FAIL — the rendered output contains `[[packages]]` (legacy).

- [ ] **Step 1.4: Update `share.py`**

In `packages/haywire-studio/src/haywire_studio/share.py`:

- Find `toml.dumps({"packages": [entry]}).strip()` in `share_library()` (around line 403). Change to `toml.dumps({"haybales": [entry]}).strip()`.
- Find `toml.dumps({"packages": entries})` in `share_save_repo()` (around line 505). Change to `toml.dumps({"haybales": entries})`.
- Verify no other `"packages"` literal remains (run the grep from step 1.1 again).

- [ ] **Step 1.5: Update any existing test assertions that referenced `[[packages]]`**

Run: `grep -n '\[\[packages\]\]' tests/test_share_save.py tests/test_share_drift.py 2>/dev/null` and update each to `[[haybales]]` if it's checking share's output.

- [ ] **Step 1.6: Run the test to confirm it passes**

Run: `uv run pytest tests/test_share_save.py tests/test_share_drift.py -v`
Expected: all pass.

- [ ] **Step 1.7: Run the full unit test suite to catch regressions**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass (1349 + any new tests from step 1.2).

- [ ] **Step 1.8: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_save.py tests/test_share_drift.py
git commit -m "feat(share): emit [[haybales]] section name per spec §1"
```

---

## Task 2: `haywire share` reads and validates `[tool.haywire].os`

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Create: `tests/test_share_os_field.py`

Per spec §2.1: `haywire share` reads `[tool.haywire].os` from each library's `pyproject.toml`. Declarable values are `"macos"`, `"windows"`, `"linux"` only. `"other"` is the runtime sentinel and MUST be rejected with a clear error pointing at the library and the invalid value. Absent from pyproject → absent from the marketstall entry (the dataclass defaults `os=[]`).

- [ ] **Step 2.1: Write failing tests**

Write to `tests/test_share_os_field.py`:

```python
"""haywire share reads and validates [tool.haywire].os per spec §2.1."""

from __future__ import annotations

from pathlib import Path

import pytest


_SHIPPABLE_PYPROJECT = '''[project]
name = "haybale-foo"
version = "0.1.0"
description = "x"

[tool.hatch.build.targets.wheel]
packages = ["haybale_foo"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''


def _make_lib(tmp_path: Path, *, os_decl: list[str] | None = None) -> Path:
    """Scaffold a minimal barn library with optional [tool.haywire].os declaration."""
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    pkg = lib_dir / "haybale_foo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        '"""Foo."""\n'
        'from haywire.core.library.base import BaseLibrary\n'
        'from haywire.core.library.decorator import library\n'
        '\n'
        '@library(label="Foo", id="foo", version="0.1.0", description="x",\n'
        '         url="", help_url="", author="", author_url="",\n'
        '         dependencies=[], tags=[], file_watcher=False)\n'
        'class Library(BaseLibrary):\n'
        '    def register_components(self): pass\n'
        '    def validate(self) -> bool: return True\n'
    )
    pyproject = _SHIPPABLE_PYPROJECT
    if os_decl is not None:
        os_inline = ", ".join(f'"{x}"' for x in os_decl)
        pyproject += f'\n[tool.haywire]\nos = [{os_inline}]\n'
    (lib_dir / "pyproject.toml").write_text(pyproject)
    (tmp_path / ".git").mkdir()  # so _find_git_root succeeds
    return lib_dir


@pytest.mark.unit
def test_share_reads_os_field(tmp_path: Path) -> None:
    """Declared [tool.haywire].os is copied into the haybale entry."""
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "linux"]


@pytest.mark.unit
def test_share_omits_os_when_absent(tmp_path: Path) -> None:
    """Absent [tool.haywire].os means absent from the haybale entry (= all platforms)."""
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=None)
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert "os" not in entry  # to_dict() omits empty lists


@pytest.mark.unit
def test_share_rejects_other_as_declaration(tmp_path: Path) -> None:
    """Per §2.1: 'other' is a runtime sentinel, not declarable."""
    from haywire_studio.share import InvalidOsDeclarationError, _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "other"])
    with pytest.raises(InvalidOsDeclarationError) as exc_info:
        _build_entry_for_library(lib_dir)
    assert "other" in str(exc_info.value)
    assert "macos, windows, linux" in str(exc_info.value)


@pytest.mark.unit
def test_share_rejects_unknown_value(tmp_path: Path) -> None:
    """Per §2.1: any value not in {macos, windows, linux} is rejected."""
    from haywire_studio.share import InvalidOsDeclarationError, _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["freebsd"])
    with pytest.raises(InvalidOsDeclarationError):
        _build_entry_for_library(lib_dir)


@pytest.mark.unit
def test_share_accepts_all_three_declarable_values(tmp_path: Path) -> None:
    from haywire_studio.share import _build_entry_for_library

    lib_dir = _make_lib(tmp_path, os_decl=["macos", "windows", "linux"])
    entry = _build_entry_for_library(lib_dir)
    assert entry is not None
    assert entry["os"] == ["macos", "windows", "linux"]
```

- [ ] **Step 2.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_share_os_field.py -v`
Expected: FAIL — `InvalidOsDeclarationError` doesn't exist; `_build_entry_for_library` doesn't read `[tool.haywire].os`.

- [ ] **Step 2.3: Implement `os` reading + validation**

In `packages/haywire-studio/src/haywire_studio/share.py`:

1. Add the error class near the top (after the existing imports, before `_find_git_root`):

```python
_DECLARABLE_OS_VALUES = frozenset({"macos", "windows", "linux"})


class InvalidOsDeclarationError(RuntimeError):
    """Raised when a library's [tool.haywire].os contains an invalid value.

    Per spec §2.1: only "macos", "windows", "linux" are declarable. "other" is
    a runtime sentinel for unmapped platform.system() results and must not be
    declared.
    """


def _read_os_field(data: dict, lib_dir: Path) -> list[str]:
    """Read and validate [tool.haywire].os from a parsed pyproject.toml dict."""
    tool_haywire = data.get("tool", {}).get("haywire", {})
    os_decl = tool_haywire.get("os")
    if os_decl is None:
        return []
    if not isinstance(os_decl, list):
        raise InvalidOsDeclarationError(
            f"[tool.haywire].os in {lib_dir / 'pyproject.toml'} must be a list, got {type(os_decl).__name__}."
        )
    for value in os_decl:
        if not isinstance(value, str) or value not in _DECLARABLE_OS_VALUES:
            raise InvalidOsDeclarationError(
                f"Invalid os value {value!r} in {lib_dir / 'pyproject.toml'} [tool.haywire].os. "
                f"Declarable values: macos, windows, linux."
            )
    return list(os_decl)
```

2. Update `_build_entry_for_library` to use `_read_os_field`. Find the `Haybale(...)` construction (around line 181). Add an `os=...` argument:

```python
    os_decl = _read_os_field(data, lib_dir)

    return Haybale(
        name=name,
        label=label,
        min_version=version,
        description=description,
        author=author,
        source="git",
        install_spec=install_spec,
        tags=tags,
        os=os_decl,
        dependencies=dependencies,
        source_url=https_url if remote_url else "",
        docs_url=docs_url,
    ).to_dict()
```

- [ ] **Step 2.4: Run the tests**

Run: `uv run pytest tests/test_share_os_field.py -v`
Expected: 5 passed.

- [ ] **Step 2.5: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass.

- [ ] **Step 2.6: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_os_field.py
git commit -m "feat(share): read and validate [tool.haywire].os field"
```

---

## Task 3: `haywire share` computes share URL via host providers

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Create: `tests/test_share_url_derivation.py`

Per spec §6.1: After `share_save_repo()` writes `marketstall.toml`, derive the canonical blob URL via `HostProvider.blob_url(...)`. The URL is printed to stdout (see §6.2) and used later (Task 6) to update README markers.

Algorithm:
1. Find the git root via the existing `_find_git_root` helper.
2. Get the remote URL via `_get_remote_url`. None → skip URL derivation, print warning.
3. Convert SSH→HTTPS via existing `_ssh_to_https` helper.
4. Parse hostname → `resolve_host(hostname)`. None → skip URL derivation, print warning with ready-to-paste `~/.haywire/config.toml` snippet.
5. Determine the ref: `--ref <ref>` (verbatim) → `--tag <tag>` (tag name) → `--tag latest` (most recent tag) → current branch from `git rev-parse --abbrev-ref HEAD`.
6. Call `provider.blob_url(owner, repo, ref, "marketstall.toml")` to get the share URL.
7. Return the URL alongside the written file path.

`share_save_repo` currently returns a `Path`. Extend its return signature to a small dataclass `ShareSaveResult(out_path, share_url, warning)` so the CLI layer can format output (§6.2) and Task 6 can use the URL.

- [ ] **Step 3.1: Write failing tests**

Write to `tests/test_share_url_derivation.py`:

```python
"""haywire share URL derivation via host providers — spec §6.1."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


_LIB_PYPROJECT = '''[project]
name = "haybale-foo"
version = "0.1.0"
description = "x"

[tool.hatch.build.targets.wheel]
packages = ["haybale_foo"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
'''

_LIB_INIT = (
    '"""Foo."""\n'
    'from haywire.core.library.base import BaseLibrary\n'
    'from haywire.core.library.decorator import library\n'
    '\n'
    '@library(label="Foo", id="foo", version="0.1.0", description="x",\n'
    '         url="", help_url="", author="", author_url="",\n'
    '         dependencies=[], tags=[], file_watcher=False)\n'
    'class Library(BaseLibrary):\n'
    '    def register_components(self): pass\n'
    '    def validate(self) -> bool: return True\n'
)


def _make_repo(tmp_path: Path) -> Path:
    """Scaffold a minimal repo with one barn library."""
    (tmp_path / ".git").mkdir()
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    pkg = lib_dir / "haybale_foo"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(_LIB_INIT)
    (lib_dir / "pyproject.toml").write_text(_LIB_PYPROJECT)
    return tmp_path


@pytest.mark.unit
def test_share_save_returns_share_url_for_github_remote(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert result.out_path == repo / "marketstall.toml"
    assert result.warning is None


@pytest.mark.unit
def test_share_save_returns_share_url_for_gitlab_remote(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="https://gitlab.com/alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url == "https://gitlab.com/alice/cool-libs/-/blob/main/marketstall.toml"


@pytest.mark.unit
def test_share_save_no_remote_warns(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value=None):
        result = share_save_repo(repo)

    assert result.share_url is None
    assert result.warning is not None
    assert "remote" in result.warning.lower()


@pytest.mark.unit
def test_share_save_unknown_host_warns_with_config_snippet(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="https://gitlab.zhdk.ch/alice/libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(repo)

    assert result.share_url is None
    assert result.warning is not None
    assert "gitlab.zhdk.ch" in result.warning
    assert "[[hosts]]" in result.warning  # ready-to-paste config snippet
    assert "config.toml" in result.warning


@pytest.mark.unit
def test_share_save_with_explicit_ref(tmp_path: Path) -> None:
    """--ref <ref> argument overrides the current-branch default."""
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        result = share_save_repo(repo, ref="v0.2.0")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.2.0/marketstall.toml"


@pytest.mark.unit
def test_share_save_with_tag_argument(tmp_path: Path) -> None:
    """--tag <tag> argument uses the tag name as ref."""
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        result = share_save_repo(repo, tag="v0.2.0")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.2.0/marketstall.toml"


@pytest.mark.unit
def test_share_save_with_tag_latest_resolves_to_most_recent_tag(tmp_path: Path) -> None:
    from haywire_studio.share import share_save_repo

    repo = _make_repo(tmp_path)
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_latest_tag", return_value="v0.3.0"):
            result = share_save_repo(repo, tag="latest")

    assert result.share_url == "https://github.com/alice/cool-libs/blob/v0.3.0/marketstall.toml"
```

- [ ] **Step 3.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_share_url_derivation.py -v`
Expected: FAIL — `share_save_repo` returns `Path` not `ShareSaveResult`; `_get_current_ref` and `_get_latest_tag` don't exist; `ref` and `tag` kwargs aren't accepted.

- [ ] **Step 3.3: Implement URL derivation in `share.py`**

In `packages/haywire-studio/src/haywire_studio/share.py`:

1. Add helpers near the top (after `_get_remote_url`):

```python
def _get_current_ref(git_root: Path) -> str | None:
    """Return current branch name, or None if detached HEAD or git failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(git_root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            ref = result.stdout.strip()
            if ref and ref != "HEAD":  # detached HEAD prints "HEAD"
                return ref
    except FileNotFoundError:
        pass
    return None


def _get_latest_tag(git_root: Path) -> str | None:
    """Return the most recent tag reachable from HEAD, or None."""
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--abbrev=0"],
            cwd=str(git_root),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except FileNotFoundError:
        pass
    return None
```

2. Add the result dataclass (after `NoBarnError`, before `share_save_repo`):

```python
@dataclass(frozen=True)
class ShareSaveResult:
    """Output of share_save_repo. share_url is None if URL derivation failed."""

    out_path: Path
    share_url: str | None
    warning: str | None  # User-facing warning when share_url is None
```

3. Refactor `share_save_repo` to return `ShareSaveResult`. The full new signature:

```python
def share_save_repo(
    repo_root: Path,
    *,
    strict: bool = False,
    fix: bool = False,
    ref: str | None = None,
    tag: str | None = None,
) -> ShareSaveResult:
```

The body:
- Build entries as before; write `marketstall.toml` with `[[haybales]]` (Task 1 already changed this).
- After the write, derive the share URL via this algorithm:
  1. `remote_url = _get_remote_url(repo_root)`. None → return `ShareSaveResult(out_path, None, "No git remote found. Push this repo to a supported host first, then re-run `haywire share` (without `--save`) to get the share URL.")`.
  2. `https_url = _ssh_to_https(remote_url).removesuffix(".git").rstrip("/")`.
  3. Parse host: use `urllib.parse.urlsplit(https_url).hostname`.
  4. `provider = resolve_host(hostname)`. None → return `ShareSaveResult(out_path, None, _unknown_host_warning(hostname))`. The helper formats the §6.2 unknown-host warning with the ready-to-paste snippet.
  5. Parse owner + repo from the URL path. `path = urlsplit(https_url).path.strip("/")`; owner, _, repo = path.rpartition("/").
  6. Determine the ref:
     - If `ref` is set → use it verbatim.
     - Elif `tag` == "latest" → `_get_latest_tag(repo_root)`; if None → fall through to default and emit a warning.
     - Elif `tag` is set → use `tag` as ref.
     - Else → `_get_current_ref(repo_root)`. None (detached HEAD with no `--ref/--tag`) → return `ShareSaveResult(out_path, None, "Detached HEAD with no --ref or --tag; share URL not constructed. The file has been written.")`.
  7. `share_url = provider.blob_url(owner, repo, ref_value, "marketstall.toml")`.

Add the `_unknown_host_warning` helper:

```python
def _unknown_host_warning(hostname: str) -> str:
    return (
        f"Host '{hostname}' is not recognized. To enable, add this to\n"
        f"  ~/.haywire/config.toml:\n\n"
        f"    [[hosts]]\n"
        f'    hostname = "{hostname}"\n'
        f'    provider = "gitlab"   # or one of: github, gitlab\n\n'
        f"  Then re-run `haywire share` (without `--save`) to get the share URL."
    )
```

(GitLab as the placeholder default makes sense — most self-hosted instances are GitLab.)

4. Add the import at the top: `from urllib.parse import urlsplit` and `from haywire.core.marketstall import resolve_host`.

- [ ] **Step 3.4: Update CLI callers**

`share_save_repo` is called from `packages/haywire-studio/src/haywire_studio/__main__.py` (or wherever the CLI subcommand is dispatched). Find the call site:

```sh
grep -rn "share_save_repo" packages/haywire-studio/src
```

Update the call site to handle the new `ShareSaveResult` return type. Print the share URL or the warning as appropriate (§6.2 happy path / no-remote / unknown-host).

If the CLI accepts `--ref` and `--tag` flags they may need to be added; if they already exist (under the previous Path-only signature), wire them through to the new keyword args.

If you find the CLI parsing is in `packages/haywire-studio/src/haywire_studio/__main__.py` or a similar file, add the flags. Otherwise, defer the CLI flag wiring and only update the call site to default the new args.

- [ ] **Step 3.5: Run the tests**

Run: `uv run pytest tests/test_share_url_derivation.py tests/test_share_save.py tests/test_share_drift.py -v`
Expected: all pass.

- [ ] **Step 3.6: Run the full unit suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass.

- [ ] **Step 3.7: Lint check**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/share.py`
Run: `uv run mypy packages/haywire-studio/src/haywire_studio/share.py`
Both clean.

- [ ] **Step 3.8: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_url_derivation.py
# Also any CLI-wiring file you modified, e.g.:
# git add packages/haywire-studio/src/haywire_studio/__main__.py
git commit -m "feat(share): derive share URL via host provider, return ShareSaveResult"
```

---

## Task 4: `haywire share` — URL-only re-run mode

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Modify: `tests/test_share_url_derivation.py` (add tests)

Per spec §6.4: `haywire share` without `--save` (and without a library path argument) re-derives the share URL for an existing `marketstall.toml` and prints it. Useful after pushing a repo for the first time or after updating `~/.haywire/config.toml` to recognize a self-hosted instance.

This means there are THREE modes of `haywire share`:
- `haywire share <library_path>` — single-library stdout snippet (§6.5).
- `haywire share --save [...]` — aggregate all barn libraries to `marketstall.toml`.
- `haywire share` (no args) — URL-only re-run.

The URL-only path doesn't write any file. It uses the same derivation algorithm as Task 3.

- [ ] **Step 4.1: Write failing tests**

Append to `tests/test_share_url_derivation.py`:

```python
@pytest.mark.unit
def test_derive_share_url_no_args(tmp_path: Path) -> None:
    """`haywire share` (no args) derives the URL without writing files."""
    from haywire_studio.share import ShareSaveResult, derive_share_url_only

    repo = _make_repo(tmp_path)
    (repo / "marketstall.toml").write_text("# placeholder\n")
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = derive_share_url_only(repo)

    assert isinstance(result, ShareSaveResult)
    assert result.share_url == "https://github.com/alice/cool-libs/blob/main/marketstall.toml"


@pytest.mark.unit
def test_derive_share_url_only_no_file_warns(tmp_path: Path) -> None:
    """If marketstall.toml doesn't exist, surface a helpful message."""
    from haywire_studio.share import derive_share_url_only

    repo = _make_repo(tmp_path)
    # No marketstall.toml created.
    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = derive_share_url_only(repo)

    assert result.share_url is None
    assert "marketstall.toml" in result.warning
```

- [ ] **Step 4.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_share_url_derivation.py -v -k derive_share_url`
Expected: FAIL — `derive_share_url_only` doesn't exist.

- [ ] **Step 4.3: Implement `derive_share_url_only`**

Add to `packages/haywire-studio/src/haywire_studio/share.py`:

```python
def derive_share_url_only(
    repo_root: Path,
    *,
    ref: str | None = None,
    tag: str | None = None,
) -> ShareSaveResult:
    """Re-derive the share URL for an existing marketstall.toml. Spec §6.4.

    Does NOT write any file. Returns a ShareSaveResult mirroring share_save_repo's
    output so callers can format the same way.
    """
    out_path = repo_root / "marketstall.toml"
    if not out_path.is_file():
        return ShareSaveResult(
            out_path=out_path,
            share_url=None,
            warning=(
                f"No marketstall.toml found at {out_path}. "
                f"Run `haywire share --save` first to produce it."
            ),
        )

    # Same URL-derivation algorithm as share_save_repo's URL pass — factor into
    # a private helper to avoid duplication.
    return _derive_url(repo_root, out_path, ref=ref, tag=tag)
```

Refactor the URL-derivation algorithm out of `share_save_repo` into a private `_derive_url(repo_root, out_path, *, ref, tag) -> ShareSaveResult` helper. Both `share_save_repo` (after writing the file) and `derive_share_url_only` call it.

- [ ] **Step 4.4: Update CLI dispatcher**

Find the CLI's `share` subcommand handler. The dispatch table:
- args has a `library_path` (positional) → call `share_library(library_path, ...)`.
- args has `--save` → call `share_save_repo(repo_root, ...)`.
- Neither → call `derive_share_url_only(repo_root, ...)`.

- [ ] **Step 4.5: Run the tests**

Run: `uv run pytest tests/test_share_url_derivation.py -v`
Expected: all pass (Task 3 tests + 2 new).

- [ ] **Step 4.6: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_url_derivation.py
# + CLI wiring file
git commit -m "feat(share): add URL-only re-run mode (no --save)"
```

---

## Task 5: `haywire init` scaffolds README.md with marker pairs

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py`
- Create: `tests/test_init_readme_scaffold.py`

Per spec §6.6 last paragraph: `haywire init` writes a root `README.md` AND each `barn/haybale-<name>/README.md` with placeholder marker pairs. The placeholder text says "Subscribe URL not yet published — run `haywire share --save` after pushing this repo to a git remote." The first successful `haywire share --save` (Task 6) replaces the placeholder with the real URL.

- [ ] **Step 5.1: Write failing tests**

Write to `tests/test_init_readme_scaffold.py`:

```python
"""haywire init scaffolds README.md with marker pairs — spec §6.6."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_init_writes_root_readme_with_marker_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    readme = tmp_path / "my-project" / "README.md"
    assert readme.is_file()
    content = readme.read_text()
    assert "<!-- marketstall:share-url:start -->" in content
    assert "<!-- marketstall:share-url:end -->" in content
    assert "haywire share" in content  # placeholder mentions the command


@pytest.mark.unit
def test_init_writes_barn_library_readme_with_marker_pair(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    lib_readme = tmp_path / "my-project" / "barn" / "haybale-my-project" / "README.md"
    assert lib_readme.is_file()
    content = lib_readme.read_text()
    assert "<!-- marketstall:share-url:start -->" in content
    assert "<!-- marketstall:share-url:end -->" in content


@pytest.mark.unit
def test_init_readme_mentions_project_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("my-project", auto_sync=False)

    readme = tmp_path / "my-project" / "README.md"
    assert "my-project" in readme.read_text() or "My Project" in readme.read_text()
```

- [ ] **Step 5.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_init_readme_scaffold.py -v`
Expected: FAIL — no `README.md` is being created by `init_project`.

- [ ] **Step 5.3: Implement README scaffolding**

In `packages/haywire-studio/src/haywire_studio/init.py`:

1. Add the README template helpers (before `init_project`):

```python
_README_MARKER_START = "<!-- marketstall:share-url:start -->"
_README_MARKER_END = "<!-- marketstall:share-url:end -->"
_README_PLACEHOLDER = (
    "*Subscribe URL not yet published — run `haywire share --save` "
    "after pushing this repo to a git remote.*"
)


def _generate_root_readme(name: str, label: str) -> str:
    """Generate the root README.md for a haywire-init scaffolded project.

    Includes the marketstall:share-url marker pair with placeholder, so the
    author's first `haywire share --save` replaces it with the real URL.
    """
    return (
        f"# {label}\n"
        f"\n"
        f"A haywire project.\n"
        f"\n"
        f"## Subscribe\n"
        f"\n"
        f"{_README_MARKER_START}\n"
        f"{_README_PLACEHOLDER}\n"
        f"{_README_MARKER_END}\n"
        f"\n"
        f"## Getting started\n"
        f"\n"
        f"```sh\n"
        f"uv sync\n"
        f"uv run haywire\n"
        f"```\n"
    )


def _generate_library_readme(name: str, label: str) -> str:
    """Generate the barn library README.md with marker pair."""
    return (
        f"# {label}\n"
        f"\n"
        f"Local haybale library for the {name} project.\n"
        f"\n"
        f"## Subscribe\n"
        f"\n"
        f"{_README_MARKER_START}\n"
        f"{_README_PLACEHOLDER}\n"
        f"{_README_MARKER_END}\n"
    )
```

2. In `init_project`, after the library scaffolding loop and before `ensure_project_config`, add:

```python
    # README.md at repo root (with marketstall share-url marker pair)
    (project_dir / "README.md").write_text(_generate_root_readme(name, label))

    # README.md inside the scaffolded barn library (with marker pair)
    (lib_dir / "README.md").write_text(_generate_library_readme(name, label))
```

- [ ] **Step 5.4: Run the tests**

Run: `uv run pytest tests/test_init_readme_scaffold.py tests/test_init_scaffolding.py -v`
Expected: all pass (including existing tests, which shouldn't break).

- [ ] **Step 5.5: Lint check**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/init.py tests/test_init_readme_scaffold.py`
Expected: clean.

- [ ] **Step 5.6: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_readme_scaffold.py
git commit -m "feat(init): scaffold README.md with marketstall:share-url marker pair"
```

---

## Task 6: `haywire share --save` updates README marker blocks

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Create: `tests/test_share_readme_markers.py`

Per spec §6.6: After `share_save_repo` derives the share URL, scan READMEs in this order: repo root `README.md` (case-insensitive: `Readme.md`, `readme.md` — first hit wins), then each `<repo>/barn/*/README.md`. For each file with the marker pair, rewrite the block between markers to contain a single inline-code line with the share URL.

Behavior table:
- File present + markers present → rewrite the block.
- File present + markers absent → leave file untouched.
- File absent → skip silently.
- Multiple marker pairs in one file → update all to the same URL.

Suppressed by `--no-update-readme` CLI flag.

- [ ] **Step 6.1: Write failing tests**

Write to `tests/test_share_readme_markers.py`:

```python
"""haywire share --save updates README marker blocks — spec §6.6."""

from __future__ import annotations

from pathlib import Path

import pytest


_MARKER_START = "<!-- marketstall:share-url:start -->"
_MARKER_END = "<!-- marketstall:share-url:end -->"


@pytest.mark.unit
def test_update_readme_markers_rewrites_block() -> None:
    """Block between markers replaced with inline-code line containing the URL."""
    from haywire_studio.share import _update_readme_markers

    content = (
        f"# Foo\n\n## Subscribe\n\n"
        f"{_MARKER_START}\n*placeholder text*\n{_MARKER_END}\n\nMore content."
    )
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content != content
    assert f"`{url}`" in new_content
    assert "placeholder text" not in new_content
    assert _MARKER_START in new_content
    assert _MARKER_END in new_content
    assert "More content." in new_content  # surrounding content preserved


@pytest.mark.unit
def test_update_readme_markers_no_markers_returns_unchanged() -> None:
    """File without marker pair is returned untouched."""
    from haywire_studio.share import _update_readme_markers

    content = "# Foo\n\nNo markers here.\n"
    assert _update_readme_markers(content, "https://example.com/x.toml") == content


@pytest.mark.unit
def test_update_readme_markers_multiple_blocks_all_updated() -> None:
    """Per spec §6.6: multiple marker pairs in one file are all updated to the same URL."""
    from haywire_studio.share import _update_readme_markers

    content = (
        f"{_MARKER_START}\nA\n{_MARKER_END}\n"
        f"some text\n"
        f"{_MARKER_START}\nB\n{_MARKER_END}\n"
    )
    url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    new_content = _update_readme_markers(content, url)

    assert new_content.count(f"`{url}`") == 2
    assert "A" not in new_content
    assert "B" not in new_content


@pytest.mark.unit
def test_share_save_updates_root_readme(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """End-to-end: share_save_repo rewrites the root README's marker block."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    # Scaffold: root README + one barn library.
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(
        f"# Project\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert result.share_url == expected_url
    assert f"`{expected_url}`" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_updates_barn_library_readme(tmp_path: Path) -> None:
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )
    (lib_dir / "README.md").write_text(
        f"# Foo\n\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            result = share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert f"`{expected_url}`" in (lib_dir / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_update_readme_flag_suppresses(tmp_path: Path) -> None:
    """--no-update-readme leaves all READMEs untouched."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(
        f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            share_save_repo(tmp_path, update_readme=False)

    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_no_share_url_skips_readme_update(tmp_path: Path) -> None:
    """When share URL can't be derived (no remote), READMEs are not touched."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text(
        f"{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value=None):
        result = share_save_repo(tmp_path)

    assert result.share_url is None
    assert "placeholder" in (tmp_path / "README.md").read_text()


@pytest.mark.unit
def test_share_save_finds_case_insensitive_readme(tmp_path: Path) -> None:
    """Per spec §6.6: 'Readme.md' (case variant) is found if README.md is absent."""
    from unittest.mock import patch
    from haywire_studio.share import share_save_repo

    (tmp_path / ".git").mkdir()
    (tmp_path / "Readme.md").write_text(  # lowercase 'e', capital 'R'
        f"# x\n{_MARKER_START}\n*placeholder*\n{_MARKER_END}\n"
    )
    lib_dir = tmp_path / "barn" / "haybale-foo"
    lib_dir.mkdir(parents=True)
    (lib_dir / "pyproject.toml").write_text(
        '[project]\nname = "haybale-foo"\nversion = "0.1.0"\ndescription = "x"\n'
    )

    with patch("haywire_studio.share._get_remote_url", return_value="git@github.com:alice/cool-libs.git"):
        with patch("haywire_studio.share._get_current_ref", return_value="main"):
            share_save_repo(tmp_path)

    expected_url = "https://github.com/alice/cool-libs/blob/main/marketstall.toml"
    assert f"`{expected_url}`" in (tmp_path / "Readme.md").read_text()
```

- [ ] **Step 6.2: Run the tests to confirm they fail**

Run: `uv run pytest tests/test_share_readme_markers.py -v`
Expected: FAIL — `_update_readme_markers` doesn't exist; `update_readme` kwarg doesn't exist.

- [ ] **Step 6.3: Implement marker-block rewriting**

In `packages/haywire-studio/src/haywire_studio/share.py`:

1. Add the marker helpers (near the top, after imports):

```python
_README_MARKER_START = "<!-- marketstall:share-url:start -->"
_README_MARKER_END = "<!-- marketstall:share-url:end -->"
_README_NAMES = ("README.md", "Readme.md", "readme.md")  # case-insensitive search


def _update_readme_markers(content: str, share_url: str) -> str:
    """Rewrite every <!-- marketstall:share-url:start --> ... :end --> block.

    The new block content is a single inline-code line containing the URL.
    Files without the marker pair are returned unchanged.
    """
    pattern = re.compile(
        re.escape(_README_MARKER_START) + r"\n.*?\n" + re.escape(_README_MARKER_END),
        re.DOTALL,
    )
    replacement = f"{_README_MARKER_START}\n`{share_url}`\n{_README_MARKER_END}"
    return pattern.sub(replacement, content)


def _find_readme(directory: Path) -> Path | None:
    """Find README.md (case-insensitive variants) in directory. None if absent."""
    for name in _README_NAMES:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    return None


def _update_repo_readmes(repo_root: Path, share_url: str) -> list[Path]:
    """Update marker blocks in the root README and each barn/*/README.md.

    Returns the list of README paths that were updated (had markers AND were rewritten).
    """
    updated: list[Path] = []
    candidates: list[Path] = []

    root_readme = _find_readme(repo_root)
    if root_readme is not None:
        candidates.append(root_readme)

    barn = repo_root / "barn"
    if barn.is_dir():
        for lib_dir in sorted(barn.iterdir()):
            if not lib_dir.is_dir():
                continue
            lib_readme = _find_readme(lib_dir)
            if lib_readme is not None:
                candidates.append(lib_readme)

    for readme in candidates:
        old = readme.read_text(encoding="utf-8")
        new = _update_readme_markers(old, share_url)
        if new != old:
            readme.write_text(new, encoding="utf-8")
            updated.append(readme)
    return updated
```

2. Update `share_save_repo`'s signature to add `update_readme: bool = True`. After the URL derivation, call `_update_repo_readmes` when `share_url is not None and update_readme`:

```python
def share_save_repo(
    repo_root: Path,
    *,
    strict: bool = False,
    fix: bool = False,
    ref: str | None = None,
    tag: str | None = None,
    update_readme: bool = True,
) -> ShareSaveResult:
    # ... existing body ...
    result = _derive_url(repo_root, out_path, ref=ref, tag=tag)
    if result.share_url is not None and update_readme:
        _update_repo_readmes(repo_root, result.share_url)
    return result
```

3. Wire `--no-update-readme` into the CLI parser (set `update_readme=False` when the flag is present). The CLI lives in `__main__.py` (or wherever the share subcommand is dispatched).

- [ ] **Step 6.4: Run the tests**

Run: `uv run pytest tests/test_share_readme_markers.py tests/test_share_url_derivation.py -v`
Expected: all pass.

- [ ] **Step 6.5: Run the full suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all pass.

- [ ] **Step 6.6: Lint check**

Run: `uv run ruff check packages/haywire-studio/src/haywire_studio/share.py`
Run: `uv run mypy packages/haywire-studio/src/haywire_studio/share.py`
Both clean.

- [ ] **Step 6.7: Commit**

```sh
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_readme_markers.py
# + CLI wiring file
git commit -m "feat(share): update README marker blocks with derived share URL"
```

---

## Task 7: `haybale-gen-docs` skill — README.md generation + marker preservation

**Files:**
- Modify: `.claude/skills/haybale-gen-docs/SKILL.md`
- Modify: `.claude/skills/haybale-gen-docs/format-spec.md`

The gen-docs skill is a Markdown procedure executed by Claude, not Python code. We're adding TWO rules to it:

1. **README.md generation**: a new step that writes `module_path/README.md` (note: at the package root, not inside the python module — re-read §6.6 carefully). Content per the glossary: `NOTES.md` verbatim (if present) followed by the OVERVIEW.md component catalog. Lives at `library_path/README.md` (the package root containing `pyproject.toml`), not in the Python module directory.

   Wait — re-reading the spec and glossary more carefully:
   - Glossary says README.md "lives at the package root (not shipped in wheel)."
   - The "package root" = library's directory containing `pyproject.toml` = `library_path` in gen-docs's vocabulary.
   - OVERVIEW.md lives at `module_path/OVERVIEW.md` (inside the Python module).
   - So gen-docs writes README.md at `library_path/README.md` (one level above where OVERVIEW.md lives).

2. **Marker-pair preservation rule**: when writing README.md, if the existing file contains a `<!-- marketstall:share-url:start -->` ... `<!-- marketstall:share-url:end -->` block, preserve it verbatim in the new content. This ensures gen-docs and `haywire share` don't fight over the README.

- [ ] **Step 7.1: Add a README.md section to SKILL.md**

Edit `.claude/skills/haybale-gen-docs/SKILL.md`. After section "4a. OVERVIEW.md (always regenerate)" and before "4b. QUICKREF.md", insert a new section:

```markdown
### 4a-bis. README.md (always regenerate; preserve marker blocks)

Write to `library_path/README.md` (the package root, one level above `module_path` — same directory as `pyproject.toml`). This file is the universal pre-install discovery document: PyPI renders it as `info.description`, git platforms render it on the repo page.

**Content structure**:
1. If `module_path/NOTES.md` exists, its full contents prepended verbatim (no transformation).
2. The component catalog — same content as `OVERVIEW.md` (the catalog only, NOT the "Additional Notes" section).

**Marker-pair preservation rule (critical — spec §6.6)**:

If the existing `library_path/README.md` contains one or more blocks delimited by:

```
<!-- marketstall:share-url:start -->
... any content ...
<!-- marketstall:share-url:end -->
```

then each block must be preserved verbatim in the regenerated README. The blocks are managed by `haywire share --save`, which writes the canonical share URL between the markers. Erasing them would silently break the share-URL discovery flow.

**Algorithm for preservation**:
1. Read the existing `library_path/README.md` if present.
2. Extract all `<!-- marketstall:share-url:start --> ... <!-- marketstall:share-url:end -->` blocks (use a regex with `re.DOTALL`).
3. Build the new README content: NOTES.md (if present) + catalog.
4. If the original had marker blocks, append them at the end of the new content as a "## Subscribe" section — OR, if you can detect their original section header in the prior content, insert under that header. Simplest correct behavior: append a "## Subscribe" section listing each preserved block in order at the end of the new content.
5. If the original had no marker blocks, do not invent one — leave the README clean.

**Rules**:
- Always overwrite `library_path/README.md` completely (with marker blocks preserved per above).
- Never modify or overwrite `module_path/NOTES.md`.
- The README is NOT shipped in the wheel; it's a discovery artifact at the repo level.
```

- [ ] **Step 7.2: Add the README.md canonical format to format-spec.md**

Edit `.claude/skills/haybale-gen-docs/format-spec.md`. Append a new section:

```markdown
## README.md

Lives at `library_path/README.md` (package root, sibling to `pyproject.toml`).

**Structure**:

```markdown
{NOTES_MD_VERBATIM_IF_PRESENT}

# {label}

{description}

## Components

{COMPONENT_CATALOG_FROM_OVERVIEW_MD}

## Subscribe

<!-- marketstall:share-url:start -->
... preserved verbatim from original README ...
<!-- marketstall:share-url:end -->
```

**Notes**:
- The component catalog is the SAME content as the "Components" section of `OVERVIEW.md` — both are derived from the same source data.
- The "## Subscribe" section only appears if the prior README had marker blocks. The skill never invents new marker blocks.
- NOTES.md is prepended verbatim before the auto-generated content; it can contain any markdown the author wants.
```

- [ ] **Step 7.3: Update the existing references in SKILL.md**

Search SKILL.md for any place that lists the outputs ("OVERVIEW.md, QUICKREF.md, and per-component docs") and update to include README.md. Search for "Generate Haybale Library Documentation" — the opening sentence around line 9.

- [ ] **Step 7.4: Skill changes don't have automated tests, but write a small assertion script**

Write to `tests/test_gen_docs_readme_contract.py`:

```python
"""Sanity-check that the haybale-gen-docs skill's contract is documented."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_skill_md_documents_readme_generation() -> None:
    """SKILL.md must include a section about README.md generation."""
    skill_md = Path(__file__).parent.parent / ".claude" / "skills" / "haybale-gen-docs" / "SKILL.md"
    content = skill_md.read_text(encoding="utf-8")
    assert "README.md" in content
    # The marker-pair contract MUST be documented (spec §6.6).
    assert "marketstall:share-url:start" in content
    assert "marketstall:share-url:end" in content


@pytest.mark.unit
def test_format_spec_md_includes_readme() -> None:
    """format-spec.md must include a README.md canonical format section."""
    format_spec = Path(__file__).parent.parent / ".claude" / "skills" / "haybale-gen-docs" / "format-spec.md"
    content = format_spec.read_text(encoding="utf-8")
    assert "## README.md" in content
```

- [ ] **Step 7.5: Run the test to confirm SKILL.md changes are detected**

Run: `uv run pytest tests/test_gen_docs_readme_contract.py -v`
Expected: pass if your SKILL.md edits include both marker strings.

- [ ] **Step 7.6: Commit**

```sh
git add .claude/skills/haybale-gen-docs/SKILL.md .claude/skills/haybale-gen-docs/format-spec.md tests/test_gen_docs_readme_contract.py
git commit -m "docs(skill): add README.md generation + marketstall marker preservation to haybale-gen-docs"
```

---

## Task 8: Update glossary to reflect README/gen-docs reality

**Files:**
- Modify: `docs/reference/glossary.md`

The glossary's existing entries for `README.md` and `haywire-gen-docs` claim README generation is implemented. After Task 7, that claim becomes true (the skill documents the contract). But verify the wording is accurate now, and add a brief mention of the marker-preservation rule in the README.md row.

- [ ] **Step 8.1: Read the relevant glossary rows**

Run: `grep -n "README.md\|haywire-gen-docs" docs/reference/glossary.md | head -10`

Locate the rows (they're in the "Library & Plugin System" table).

- [ ] **Step 8.2: Update the README.md row**

Find this row in `docs/reference/glossary.md`:

```
| **README.md** | Fully generated landing page for a haybale package. Lives at the package root (not shipped in wheel). Content: `NOTES.md` verbatim (if present) followed by the component catalog (identical to `OVERVIEW.md`). Rendered by PyPI (`info.description`) and git platforms — the universal pre-install discovery document reachable via every distribution method. Generated by `haywire-gen-docs` in the same pass as `OVERVIEW.md`. | — |
```

Replace with:

```
| **README.md** | Fully generated landing page for a haybale package. Lives at the package root (not shipped in wheel). Content: `NOTES.md` verbatim (if present) followed by the component catalog (identical to `OVERVIEW.md`), plus any `<!-- marketstall:share-url -->` marker blocks preserved verbatim. Rendered by PyPI (`info.description`) and git platforms — the universal pre-install discovery document reachable via every distribution method. Generated by `haywire-gen-docs` in the same pass as `OVERVIEW.md`. The marker blocks are managed by `haywire share --save` (spec §6.6); gen-docs preserves them so the two skills compose. | — |
```

- [ ] **Step 8.3: Verify the haywire-gen-docs entry mentions marker preservation**

Find the `haywire-gen-docs` row. Update its description to mention marker preservation:

```
| **haywire-gen-docs** | The Claude skill that generates `README.md`, `OVERVIEW.md`, `QUICKREF.md`, and per-component `docs/` for a haybale package in one pass. Syncs docstrings first. Uses sha256 hashes to skip unchanged per-component docs. Preserves `<!-- marketstall:share-url -->` marker blocks in the README verbatim (spec §6.6). Never modifies `NOTES.md`. | — |
```

- [ ] **Step 8.4: Commit**

```sh
git add docs/reference/glossary.md
git commit -m "docs(glossary): note marker-pair preservation in README/gen-docs entries"
```

---

## Task 9: Final verification sweep

- [ ] **Step 9.1: Run the full test suite**

Run: `uv run pytest tests/ -m "not integration" -q`
Expected: all unit tests pass; new total = baseline 1349 + tests added in tasks 1-7 (approximately 1380-1390).

- [ ] **Step 9.2: Run ruff across all changed packages**

Run:
```sh
uv run ruff check \
    packages/haywire-studio/src/haywire_studio/share.py \
    packages/haywire-studio/src/haywire_studio/init.py \
    tests/test_share_os_field.py \
    tests/test_share_url_derivation.py \
    tests/test_share_readme_markers.py \
    tests/test_init_readme_scaffold.py \
    tests/test_gen_docs_readme_contract.py
```
Expected: clean.

- [ ] **Step 9.3: Run mypy on the modified source files**

Run:
```sh
uv run mypy \
    packages/haywire-studio/src/haywire_studio/share.py \
    packages/haywire-studio/src/haywire_studio/init.py
```
Expected: clean.

- [ ] **Step 9.4: Manual smoke test of `haywire init` + `haywire share`**

In a tmp directory:

```sh
cd /tmp
rm -rf smoke-marketstall-init
uv run --project /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/.worktrees/marketstall-author-tooling \
    haywire init smoke-marketstall-init --no-sync
cat smoke-marketstall-init/README.md  # Confirm marker pair present
cat smoke-marketstall-init/barn/haybale-smoke-marketstall-init/README.md  # Same
cat smoke-marketstall-init/.haywire/marketplace.toml  # Confirm [[heaps]] section
```

Confirm each output is shape-correct (markers present, `[[heaps]]` section in project marketplace, no `[[locals]]` or `[[packages]]`).

- [ ] **Step 9.5: Manual smoke test of `haywire share --save`**

In the same tmp directory (or a fresh git repo), set up a git remote, then run `haywire share --save`. Confirm:
- `marketstall.toml` written with `[[haybales]]` (not `[[packages]]`).
- The barn library entry includes the new `os` field if `[tool.haywire].os` is set in pyproject.
- The README marker block is updated with the canonical blob URL.
- Stdout shows the URL.

- [ ] **Step 9.6: Review the diff and tidy up**

Run: `git log --oneline c2617444..HEAD` to see the commit list.
Run: `git diff c2617444 --stat | tail -10` for a file-level summary.

Look for stray TODOs, debug prints, or imports that became unused. Fix inline with a small cleanup commit if needed.

---

## Spec coverage check

This plan covers the **Slice 2 (Author tooling)** portion of the marketstall-distribution spec. Specifically:

| Spec § | Covered by | Notes |
|---|---|---|
| §1 Vocabulary | Task 1 | `[[packages]]` → `[[haybales]]` in share emission |
| §2 Marketstall format | Task 1, 2 | Section name + `os` field |
| §2.1 `os` field validation | Task 2 | Reject `"other"` and unknown values; absent → empty list |
| §6 `haywire share` | Tasks 1-6 | All three modes + URL derivation + marker writes |
| §6.1 Share URL via host provider | Task 3 | `provider.blob_url(...)` |
| §6.2 Output happy/no-remote/unknown-host | Task 3 | Warning text per spec |
| §6.3 Failure modes | Task 3 | Detached HEAD warning |
| §6.4 URL-only re-run | Task 4 | `derive_share_url_only` |
| §6.5 Single-library snippet | Task 1 | `share_library()` updated to `[[haybales]]` |
| §6.6 README markers | Tasks 5, 6 | Init scaffolds; share rewrites |
| Gen-docs README + marker preservation | Tasks 7, 8 | Skill + format-spec + glossary |

**Not covered (deferred to later slices):**

| Spec § | Deferred to slice |
|---|---|
| §2.1 OS Edit dialog UI | 4 |
| §4 Add Source dialog | 3 |
| §7 Library Manager UI | 3-5 |
| §10 Update-available signal | 7 |
| §11 Per-haybale stall generator | 8 |
| §12 Drift-gate lag check on haybale-* deps | 6 |

---

## Self-Review notes

- ✅ Every step has a complete code block; no "TBD".
- ✅ Method/function names referenced across tasks: `_build_entry_for_library` (Task 2), `share_save_repo` (Tasks 3, 6), `derive_share_url_only` (Task 4), `_update_readme_markers` (Task 6), `_update_repo_readmes` (Task 6), `ShareSaveResult` (Tasks 3, 4), `InvalidOsDeclarationError` (Task 2) — all defined where they're first used and referenced consistently.
- ✅ Test fixtures use `tmp_path` consistently.
- ✅ TDD discipline: failing test before implementation in each task.
- ✅ Commits are small and feature-focused.
- ✅ Cross-skill contract (gen-docs preserving marker pair, share writing the marker block) is documented at BOTH skill ends, not just one.

---

## Execution Handoff

Plan complete and saved to `internals/plans/2026-05-22-marketstall-author-tooling.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
