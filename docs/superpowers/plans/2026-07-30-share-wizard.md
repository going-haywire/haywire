# Share Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a whole haywire project (all `barn/*` libraries in lockstep) from a GUI wizard in the Marketplace burger menu, driven by a shared `SharePipeline` that the rewritten `haywire share` CLI also uses.

**Architecture:** A stateful `SharePipeline` object in `haywire_studio.share_pipeline` holds per-step state and exposes six step methods, each split into a non-mutating check/plan call and a mutating apply call. Expected failures raise domain exceptions; successes return small frozen dataclasses. Two thin callers drive it: a NiceGUI stepper popup in `haybale-marketplace` and a rewritten `haywire share` CLI. Slow subprocesses (`haywire docs --all`, `uv lock`, `git push`) stream their output.

**Tech Stack:** Python 3.12, NiceGUI (Quasar `ui.stepper`), `toml`, `subprocess`/`asyncio.create_subprocess_exec`, pytest.

## Global Constraints

- **Scope of sharing is the PROJECT, not one library.** Every `barn/*/pyproject.toml` gets the same version. See [ADR 0023](../../adr/0023-project-scoped-lockstep-sharing.md).
- **The root `pyproject.toml` version is NEVER touched.** It is the uv workspace root, fixed at `0.1.0`, and depends on the library unversioned. This is a behaviour change from `bump_version()`, which bumps it today.
- **Version bump MUST precede docs generation.** `render_quickref` embeds `v{doc.version}` (`packages/haywire-studio/src/haywire_studio/docs_gen/render.py:43`); generating first publishes a QUICKREF stating the previous version.
- **Docs generation MUST be a subprocess**, never an in-process call, from either the studio or the pipeline. `generate_docs()` builds a second library system whose `initialize()` calls `set_global_injector()`, and `extract_library` instantiates every node (hardware grabs). See `.insights/project_docs_gen_reentrancy.md`.
- **The wizard never runs a destructive git command.** Only: write, add, commit, tag, push. No `reset`, no `checkout --`, no `clean`, no history rewriting, no `git add -a`/`-A`.
- **Commit staging is an explicit file list only.** Never `-a` / `-A`.
- **No git LFS anywhere.** Do not scaffold `git lfs install` or `filter=lfs` patterns. See `.insights/project_git_url_publishing_traps.md` §2.
- **`install_spec` pinning is OUT OF SCOPE.** Do not add `@tag` or a `tag =` key anywhere in this plan.
- **No `ctx.fence()`, no undo/redo integration, no rollback.** Pre-flight verification only.
- **Git subprocess hardening for every remote call:** `env` must include `GIT_TERMINAL_PROMPT=0`, `GIT_ASKPASS=""`, `SSH_ASKPASS=""`, and a `timeout=` must be passed. A missing credential must become a clean error, never a hang.
- **Lint/format/type:** `uv run ruff check .`, `uv run ruff format --check .`, and the repo's `uv run mypy <paths>` (see CLAUDE.md) must be clean. Line length is 109.
- **Async UI rule:** never `asyncio.ensure_future()` a coroutine that calls `ui.notify()`. Return the coroutine from the handler lambda. See `.insights/feedback_nicegui_async.md`.
- **Test marks:** new tests get `@pytest.mark.unit` unless they boot a real library system (then `@pytest.mark.integration`). No Playwright tests in this plan.

## File Structure

**New files**

| Path | Responsibility |
| --- | --- |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py` | Public surface: re-exports `SharePipeline`, every result dataclass, every exception. |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/errors.py` | Domain exceptions only. No logic. |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/results.py` | Frozen result dataclasses only. No logic. |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/gitcmd.py` | Hardened `git` subprocess helpers (sync + streaming async). Every git call in the pipeline goes through here. |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py` | `SharePipeline` — the six steps, accumulated write set, state machine. |
| `packages/haywire-studio/src/haywire_studio/share_pipeline/versions.py` | Lockstep version reading/writing + next-version arithmetic. Narrow replacement for `bump_version`'s version logic. |
| `packages/haywire-studio/src/haywire_studio/share_cli.py` | `run_share_cli()` — interactive / `--check` / `--yes` runner over `SharePipeline`. |
| `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard.py` | The NiceGUI stepper popup. One function per step panel. |
| `tests/share_pipeline/test_preconditions.py` | Step 1 tests. |
| `tests/share_pipeline/test_versions.py` | Version arithmetic + lockstep write tests. |
| `tests/share_pipeline/test_drift_step.py` | Step 2 tests. |
| `tests/share_pipeline/test_docs_step.py` | Step 4 tests (subprocess mocked). |
| `tests/share_pipeline/test_commit_step.py` | Step 5 tests — the file-scoping logic, real `git` in `tmp_path`. |
| `tests/share_pipeline/test_push_step.py` | Step 6 tests. |
| `tests/share_pipeline/test_pipeline_state.py` | State-machine / accumulated-write-set tests. |
| `tests/test_share_cli.py` | `--check` / `--yes` end-to-end tests. |
| `tests/test_init_scaffold_git_files.py` | `.gitignore` anchoring + `.gitattributes` scaffolding tests. |

**Modified files**

| Path | Change |
| --- | --- |
| `packages/haywire-studio/src/haywire_studio/share.py` | Delete `bump_version`, `share_library`, `_detect_library`, `_run_drift_gate`. Keep and export the reusable core. Add `build_marketstall_entries()` + `write_marketstall()`. |
| `packages/haywire-studio/src/haywire_studio/app.py:359-414, 450-503` | Replace the `share` subparser flags and dispatch with `--check` / `--yes` / `--ref` / `--tag` / `--bump` / `--message` → `run_share_cli()`. |
| `packages/haywire-studio/src/haywire_studio/app.py:427-441, 517-542` | Add `haywire docs --json <path>`. |
| `packages/haywire-studio/src/haywire_studio/docs_gen/generate.py` | No change (the `--json` write happens in `app.py`). |
| `packages/haywire-studio/src/haywire_studio/init.py:183-217` | Anchor root-only `.gitignore` patterns; add the two explanatory comment blocks. |
| `packages/haywire-studio/src/haywire_studio/init.py` (new `_generate_gitattributes`, call site near `:566`) | Scaffold `.gitattributes` with eol normalization + LFS warning comment. |
| `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:149-163` | Add `Share Project…` menu item + handler. |
| `tests/test_share_bump_keyword.py` | Rewritten against `versions.py`. |
| `tests/test_share_save.py` | Rewritten against `write_marketstall()`. |
| `tests/test_share_drift.py`, `tests/test_share_os_field.py`, `tests/test_share_readme_markers.py`, `tests/test_share_url_derivation.py` | Import-only updates where they touch removed functions. |

## Task Order

1. `gitcmd.py` — hardened git helpers (everything else depends on it)
2. `errors.py` + `results.py` — the vocabulary
3. `versions.py` — lockstep version logic
4. Step 1: preconditions
5. Step 2: drift
6. Step 3: version bump
7. `haywire docs --json`
8. Step 4: docs regeneration
9. `share.py` marketstall extraction
10. Step 5: marketstall + commit + tag
11. Step 6: push
12. Pipeline state machine + `plan()`
13. `haywire share` CLI rewrite
14. `haywire init` scaffolding fixes
15. The wizard UI
16. Menu wiring + final sweep

---

### Task 1: Hardened git subprocess helpers

Every remote git call in the pipeline must be unable to hang waiting for a credential prompt. This task builds the one place that happens.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py`
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/gitcmd.py`
- Test: `tests/share_pipeline/test_gitcmd.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `GitResult` — frozen dataclass: `ok: bool`, `stdout: str`, `stderr: str`, `returncode: int`, `timed_out: bool`.
  - `git(args: list[str], *, cwd: Path, timeout: float = 30.0) -> GitResult` — local calls.
  - `git_remote(args: list[str], *, cwd: Path, timeout: float = 60.0) -> GitResult` — same, plus the hardened env.
  - `async def git_remote_streaming(args: list[str], *, cwd: Path, on_output: Callable[[str], None], timeout: float = 300.0) -> GitResult` — streams merged stdout/stderr line by line.
  - `HARDENED_ENV: dict[str, str]` — the env overlay.

- [ ] **Step 1: Create the package and write the failing test**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py` as an empty file for now (it gets its real contents in Task 2).

Create `tests/share_pipeline/__init__.py` as an empty file, then write `tests/share_pipeline/test_gitcmd.py`:

```python
"""Tests for the hardened git subprocess helpers."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.share_pipeline.gitcmd import (
    HARDENED_ENV,
    GitResult,
    git,
    git_remote,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A real, initialised git repo with one commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def test_git_success_returns_ok_and_stdout(git_repo: Path) -> None:
    result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_repo)
    assert result.ok is True
    assert result.returncode == 0
    assert result.stdout.strip() in {"main", "master"}
    assert result.timed_out is False


def test_git_failure_returns_not_ok(git_repo: Path) -> None:
    result = git(["rev-parse", "--verify", "refs/tags/v9.9.9"], cwd=git_repo)
    assert result.ok is False
    assert result.returncode != 0


def test_git_missing_binary_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    """A missing git binary must come back as a GitResult, never a FileNotFoundError."""

    def _boom(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _boom)
    result = git(["--version"], cwd=tmp_path)
    assert result.ok is False
    assert "git" in result.stderr


def test_git_timeout_is_reported_not_raised(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_a, **_kw):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _boom)
    result = git(["--version"], cwd=tmp_path, timeout=1.0)
    assert result.ok is False
    assert result.timed_out is True


def test_hardened_env_disables_every_prompt_path() -> None:
    assert HARDENED_ENV["GIT_TERMINAL_PROMPT"] == "0"
    assert HARDENED_ENV["GIT_ASKPASS"] == ""
    assert HARDENED_ENV["SSH_ASKPASS"] == ""
    assert HARDENED_ENV["GIT_CONFIG_NOSYSTEM"] == "1"


def test_git_remote_passes_hardened_env(tmp_path: Path, monkeypatch) -> None:
    seen: dict = {}

    def _capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _capture)
    git_remote(["ls-remote", "origin"], cwd=tmp_path)
    env = seen["env"]
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_ASKPASS"] == ""
    # The parent environment is preserved (PATH must survive or git isn't findable).
    assert "PATH" in env


def test_local_git_does_not_pass_hardened_env(tmp_path: Path, monkeypatch) -> None:
    """Local calls run with the ambient env — no need to fight the user's config."""
    seen: dict = {}

    def _capture(cmd, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _capture)
    git(["status"], cwd=tmp_path)
    assert seen.get("env") is None


def test_git_result_is_frozen() -> None:
    result = GitResult(ok=True, stdout="", stderr="", returncode=0, timed_out=False)
    with pytest.raises(Exception):
        result.ok = False  # type: ignore[misc]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_gitcmd.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.share_pipeline.gitcmd'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/gitcmd.py`:

```python
"""Hardened ``git`` subprocess helpers for the share pipeline.

Every git invocation the pipeline makes goes through here. Two rules the rest
of the pipeline relies on:

1. **Nothing raises.** A missing binary, a non-zero exit, and a timeout all
   come back as a :class:`GitResult` so each step can decide what the failure
   means and raise its own domain exception.
2. **Remote calls cannot hang.** ``git_remote`` and ``git_remote_streaming``
   disable every credential-prompt path git has. Without this, a wizard run
   with no cached credential blocks forever on a prompt nobody can see: there
   is no TTY behind a NiceGUI event handler.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# GIT_CONFIG_NOSYSTEM keeps a system-wide credential helper from re-enabling a
# prompt we just disabled. The empty askpass values matter as much as the
# terminal-prompt flag: git falls back to GIT_ASKPASS/SSH_ASKPASS (and then to
# a GUI helper) when the terminal prompt is unavailable.
HARDENED_ENV: dict[str, str] = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": "",
    "SSH_ASKPASS": "",
    "GIT_CONFIG_NOSYSTEM": "1",
}


@dataclass(frozen=True)
class GitResult:
    """Outcome of one git invocation. ``ok`` is True iff returncode == 0."""

    ok: bool
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool = False


def _hardened_env() -> dict[str, str]:
    """The parent environment with the prompt-disabling overlay applied.

    The parent env is preserved rather than replaced — dropping PATH would
    make git itself unfindable, and dropping HOME would lose the user's
    credential store, which is the thing we WANT git to consult.
    """
    env = dict(os.environ)
    env.update(HARDENED_ENV)
    return env


def _run(
    args: list[str],
    *,
    cwd: Path,
    timeout: float,
    env: dict[str, str] | None,
) -> GitResult:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        return GitResult(ok=False, stdout="", stderr=f"git not found: {exc}", returncode=127)
    except subprocess.TimeoutExpired:
        return GitResult(
            ok=False,
            stdout="",
            stderr=f"git {' '.join(args)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )
    return GitResult(
        ok=proc.returncode == 0,
        stdout=proc.stdout or "",
        stderr=proc.stderr or "",
        returncode=proc.returncode,
    )


def git(args: list[str], *, cwd: Path, timeout: float = 30.0) -> GitResult:
    """Run a purely local git command with the ambient environment."""
    return _run(args, cwd=cwd, timeout=timeout, env=None)


def git_remote(args: list[str], *, cwd: Path, timeout: float = 60.0) -> GitResult:
    """Run a git command that talks to a remote, with all prompts disabled."""
    return _run(args, cwd=cwd, timeout=timeout, env=_hardened_env())


async def git_remote_streaming(
    args: list[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout: float = 300.0,
) -> GitResult:
    """Run a remote git command, calling ``on_output`` per line as it arrives.

    stderr is merged into stdout: git writes transfer progress to stderr, so a
    caller wanting a single ordered log needs one stream.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_hardened_env(),
        )
    except FileNotFoundError as exc:
        return GitResult(ok=False, stdout="", stderr=f"git not found: {exc}", returncode=127)

    lines: list[str] = []

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip()
            on_output(text)
            lines.append(text)
        await proc.wait()

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        proc.kill()
        await proc.wait()
        return GitResult(
            ok=False,
            stdout="\n".join(lines),
            stderr=f"git {' '.join(args)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )

    output = "\n".join(lines)
    rc = proc.returncode if proc.returncode is not None else 1
    return GitResult(ok=rc == 0, stdout=output, stderr=output if rc != 0 else "", returncode=rc)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_gitcmd.py -v`
Expected: 8 passed.

- [ ] **Step 5: Lint and type-check**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```
Expected: all clean.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
git commit -m "feat(share): hardened git subprocess helpers for the share pipeline"
```

---

### Task 2: Errors and result dataclasses

The whole vocabulary in one task, so later tasks never invent a name. Nothing here has behaviour beyond a few derived properties, so the test is a shape check.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/errors.py`
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/results.py`
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py`
- Test: `tests/share_pipeline/test_vocabulary.py`

**Interfaces:**
- Consumes: `GitResult` from Task 1.
- Produces (exceptions, all subclassing `ShareError(RuntimeError)`):
  `PreconditionsError` with `.failures: list[str]`; `VersionError`;
  `TagCollisionError` with `.tag: str`, `.local: bool`, `.remote: bool`;
  `DocsGenerationError` with `.output: str`; `MarketstallError`;
  `CommitError` with `.stderr: str`; `PushError` with `.stderr: str`, `.manual_command: str`;
  `PipelineStateError`.
- Produces (frozen dataclasses): `PreconditionsReport`, `LibraryVersion`, `VersionPlan`,
  `BumpResult`, `DriftReport`, `DocsResult`, `BarnDirtyFile`, `CommitPlan`, `CommitResult`,
  `PushResult`, `SharePlan`.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_vocabulary.py`:

```python
"""Shape checks for the share pipeline's exceptions and result dataclasses."""

from pathlib import Path

import pytest

from haywire_studio.share_pipeline import (
    BarnDirtyFile,
    BumpResult,
    CommitError,
    CommitPlan,
    DocsGenerationError,
    DriftReport,
    LibraryVersion,
    PreconditionsError,
    PreconditionsReport,
    PushError,
    ShareError,
    TagCollisionError,
    VersionPlan,
)

pytestmark = pytest.mark.unit


def test_every_error_is_a_share_error() -> None:
    for cls in (PreconditionsError, TagCollisionError, DocsGenerationError, CommitError, PushError):
        assert issubclass(cls, ShareError)
    assert issubclass(ShareError, RuntimeError)


def test_preconditions_error_carries_all_failures() -> None:
    exc = PreconditionsError(["no git", "no remote"])
    assert exc.failures == ["no git", "no remote"]
    # Every failure appears in the message — the CLI prints str(exc) verbatim.
    assert "no git" in str(exc)
    assert "no remote" in str(exc)


def test_preconditions_report_ok_iff_no_failures() -> None:
    assert PreconditionsReport(failures=[], remote_url="u", barn_libraries=[Path("a")]).ok is True
    assert PreconditionsReport(failures=["x"], remote_url=None, barn_libraries=[]).ok is False


def test_tag_collision_error_reports_where() -> None:
    exc = TagCollisionError(tag="v1.2.3", local=True, remote=False)
    assert exc.tag == "v1.2.3"
    assert exc.local is True
    assert exc.remote is False
    assert "v1.2.3" in str(exc)


def test_version_plan_flags_disagreement() -> None:
    agreeing = VersionPlan(
        current=[LibraryVersion(lib_dir=Path("a"), name="a", version="0.1.0")],
        common_version="0.1.0",
        suggestions={"patch": "0.1.1", "minor": "0.2.0", "major": "1.0.0"},
    )
    assert agreeing.versions_agree is True

    disagreeing = VersionPlan(
        current=[
            LibraryVersion(lib_dir=Path("a"), name="a", version="0.1.0"),
            LibraryVersion(lib_dir=Path("b"), name="b", version="0.2.0"),
        ],
        common_version=None,
        suggestions={},
    )
    assert disagreeing.versions_agree is False


def test_bump_result_lists_written_files() -> None:
    result = BumpResult(
        version="0.2.0",
        written=[Path("barn/a/pyproject.toml")],
        lock_refreshed=False,
        lock_warning="uv lock failed",
    )
    assert result.version == "0.2.0"
    assert result.written == [Path("barn/a/pyproject.toml")]
    assert result.lock_warning == "uv lock failed"


def test_drift_report_needs_decision_only_when_actionable() -> None:
    assert DriftReport(drifted=[], unresolved_only=[]).needs_decision is False
    assert DriftReport(drifted=[object()], unresolved_only=[]).needs_decision is True
    # Unresolved imports are informational — they never gate the wizard.
    assert DriftReport(drifted=[], unresolved_only=[object()]).needs_decision is False


def test_commit_plan_separates_accumulated_from_dirty_barn() -> None:
    plan = CommitPlan(
        files=[Path("barn/a/pyproject.toml")],
        barn_dirty=[BarnDirtyFile(path=Path("barn/a/asset.png"), untracked=True)],
        message="chore: share v0.2.0",
        tag="v0.2.0",
    )
    assert plan.files == [Path("barn/a/pyproject.toml")]
    assert plan.barn_dirty[0].untracked is True
    assert plan.tag == "v0.2.0"


def test_push_error_carries_the_manual_command() -> None:
    exc = PushError(stderr="denied", manual_command="git p" + "ush origin master v0.2.0")
    assert exc.manual_command.endswith("v0.2.0")
    assert "denied" in str(exc)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_vocabulary.py -v`
Expected: collection error — `ImportError: cannot import name 'BarnDirtyFile' from 'haywire_studio.share_pipeline'`

- [ ] **Step 3: Write `errors.py`**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/errors.py`:

```python
"""Domain exceptions for the share pipeline.

Expected failures raise; successes return dataclasses. This matches the
existing idiom in ``share.py`` (``DriftError``, ``NoBarnError``) rather than a
Result-type wrapper. Each caller translates: the CLI prints ``str(exc)`` and
exits, the wizard renders inline error state, a future Farmhand wrapper
re-raises as ``FarmhandError``.
"""

from __future__ import annotations


class ShareError(RuntimeError):
    """Base class for every expected share-pipeline failure."""


class PreconditionsError(ShareError):
    """One or more step-1 preconditions failed.

    Carries EVERY failure rather than the first: a user missing both a remote
    and a barn library should see both in one pass, not discover the second
    after fixing the first.
    """

    def __init__(self, failures: list[str]) -> None:
        self.failures = list(failures)
        super().__init__("Cannot share this project:\n  - " + "\n  - ".join(self.failures))


class VersionError(ShareError):
    """A version string was unparsable, or a lockstep bump had no target."""


class TagCollisionError(ShareError):
    """The tag for the requested version already exists locally or on the remote."""

    def __init__(self, *, tag: str, local: bool, remote: bool) -> None:
        self.tag = tag
        self.local = local
        self.remote = remote
        where = " and ".join(w for w, hit in (("locally", local), ("on origin", remote)) if hit)
        super().__init__(f"Tag {tag} already exists {where}. Pick a different version.")


class DocsGenerationError(ShareError):
    """``haywire docs --all`` exited non-zero (a crash, not a coverage gap)."""

    def __init__(self, message: str, *, output: str = "") -> None:
        self.output = output
        super().__init__(message)


class MarketstallError(ShareError):
    """The marketstall.toml rebuild could not complete."""


class CommitError(ShareError):
    """Staging, committing, or tagging failed."""

    def __init__(self, message: str, *, stderr: str = "") -> None:
        self.stderr = stderr
        super().__init__(message)


class PushError(ShareError):
    """The push failed. ``manual_command`` is the exact command to retry by hand."""

    def __init__(self, *, stderr: str, manual_command: str) -> None:
        self.stderr = stderr
        self.manual_command = manual_command
        super().__init__(f"Push failed: {stderr}\n\nRun this yourself to retry:\n  {manual_command}")


class PipelineStateError(ShareError):
    """A step was called out of order (its inputs had not been produced yet)."""
```

- [ ] **Step 4: Write `results.py`**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/results.py`:

```python
"""Frozen result dataclasses returned by each share-pipeline step."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PreconditionsReport:
    """Outcome of step 1. ``ok`` is True iff nothing failed."""

    failures: list[str]
    remote_url: str | None
    barn_libraries: list[Path]

    @property
    def ok(self) -> bool:
        return not self.failures


@dataclass(frozen=True)
class LibraryVersion:
    """One barn library's declared version."""

    lib_dir: Path
    name: str
    version: str | None


@dataclass(frozen=True)
class VersionPlan:
    """What step 3 could do, before the user picks.

    ``common_version`` is the shared version when every library agrees, else
    None. ``suggestions`` maps "patch"/"minor"/"major" to the resolved X.Y.Z
    and is EMPTY when the versions disagree — there is no honest arithmetic to
    offer, so the user must name a target explicitly (ADR 0023).
    """

    current: list[LibraryVersion]
    common_version: str | None
    suggestions: dict[str, str]

    @property
    def versions_agree(self) -> bool:
        return self.common_version is not None


@dataclass(frozen=True)
class BumpResult:
    """Step 3's mutation record. ``lock_warning`` is set when uv lock failed."""

    version: str
    written: list[Path]
    lock_refreshed: bool
    lock_warning: str | None = None


@dataclass(frozen=True)
class DriftReport:
    """Step 2's findings, aggregated across barn libraries.

    ``drifted`` holds ``DepDrift`` objects with actionable drift;
    ``unresolved_only`` holds those with only unmapped imports. Only the former
    is a decision — unresolved imports are usually dynamic and would otherwise
    gate every run.
    """

    drifted: list[Any]
    unresolved_only: list[Any]

    @property
    def needs_decision(self) -> bool:
        return bool(self.drifted)


@dataclass(frozen=True)
class DocsResult:
    """Step 4's outcome. ``coverage`` maps library id → coverage-gap lines."""

    coverage: dict[str, list[str]]
    written: list[Path]
    output: str = ""

    @property
    def total_gaps(self) -> int:
        return sum(len(lines) for lines in self.coverage.values())


@dataclass(frozen=True)
class BarnDirtyFile:
    """An uncommitted file under barn/ — invisible to consumers if left out."""

    path: Path
    untracked: bool


@dataclass(frozen=True)
class CommitPlan:
    """Step 5's preview: exactly what would be staged, committed, and tagged.

    ``files`` is the pipeline's own accumulated write set. ``barn_dirty`` is
    offered as opt-in extras — uncommitted barn content is silently absent for
    consumers, which is the one working-tree state that corrupts a publish.
    """

    files: list[Path]
    barn_dirty: list[BarnDirtyFile]
    message: str
    tag: str
    diffstat: str = ""


@dataclass(frozen=True)
class CommitResult:
    """Step 5's mutation record."""

    sha: str
    tag: str
    files: list[Path]


@dataclass(frozen=True)
class PushResult:
    """Step 6's outcome."""

    remote: str
    branch: str
    tag: str
    output: str = ""


@dataclass(frozen=True)
class SharePlan:
    """Everything ``plan()`` can determine without mutating anything.

    Drives ``haywire share --check`` and the wizard's summary panel.
    """

    preconditions: PreconditionsReport
    drift: DriftReport
    versions: VersionPlan
    stale_docs: list[Path] = field(default_factory=list)
    stale_marketstall: bool = False

    @property
    def is_clean(self) -> bool:
        """True when nothing drifted and nothing is stale — ``--check`` exits 0."""
        return (
            self.preconditions.ok
            and not self.drift.needs_decision
            and not self.stale_docs
            and not self.stale_marketstall
        )
```

- [ ] **Step 5: Write the package surface**

Replace the empty `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py` with:

```python
"""Share pipeline — one publishing engine, driven by the CLI and the wizard.

``SharePipeline`` itself is added in a later task; the vocabulary is
re-exported here so callers have a single import site.
"""

from haywire_studio.share_pipeline.errors import (
    CommitError,
    DocsGenerationError,
    MarketstallError,
    PipelineStateError,
    PreconditionsError,
    PushError,
    ShareError,
    TagCollisionError,
    VersionError,
)
from haywire_studio.share_pipeline.gitcmd import GitResult, git, git_remote, git_remote_streaming
from haywire_studio.share_pipeline.results import (
    BarnDirtyFile,
    BumpResult,
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    LibraryVersion,
    PreconditionsReport,
    PushResult,
    SharePlan,
    VersionPlan,
)

__all__ = [
    "BarnDirtyFile",
    "BumpResult",
    "CommitError",
    "CommitPlan",
    "CommitResult",
    "DocsGenerationError",
    "DocsResult",
    "DriftReport",
    "GitResult",
    "LibraryVersion",
    "MarketstallError",
    "PipelineStateError",
    "PreconditionsError",
    "PreconditionsReport",
    "PushError",
    "PushResult",
    "ShareError",
    "SharePlan",
    "TagCollisionError",
    "VersionError",
    "VersionPlan",
    "git",
    "git_remote",
    "git_remote_streaming",
]
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: 17 passed (8 from Task 1 + 9 here).

- [ ] **Step 7: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
git commit -m "feat(share): share-pipeline exceptions and result dataclasses"
```

---

### Task 3: Lockstep version logic

A narrow replacement for `bump_version()`'s version handling. Different rules from the old function: barn-only file set, explicit target when versions disagree, no commit, no tag, no root pyproject.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/versions.py`
- Test: `tests/share_pipeline/test_versions.py`

**Interfaces:**
- Consumes: `LibraryVersion`, `VersionPlan`, `BumpResult`, `VersionError` from Task 2.
- Produces:
  - `read_barn_versions(repo_root: Path) -> list[LibraryVersion]`
  - `plan_versions(repo_root: Path) -> VersionPlan`
  - `next_version(spec: str, current: str | None) -> str` — raises `VersionError` on a keyword with no parsable current, or a malformed explicit version.
  - `write_barn_versions(repo_root: Path, version: str) -> list[Path]` — the paths written, sorted.
  - `refresh_lockfile(repo_root: Path, *, timeout: float = 300.0) -> tuple[bool, str | None]` — `(refreshed, warning)`.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_versions.py`:

```python
"""Lockstep version reading, arithmetic, and writing."""

import subprocess
from pathlib import Path

import pytest
import toml

from haywire_studio.share_pipeline import VersionError
from haywire_studio.share_pipeline.versions import (
    next_version,
    plan_versions,
    read_barn_versions,
    refresh_lockfile,
    write_barn_versions,
)

pytestmark = pytest.mark.unit


def _make_lib(repo: Path, name: str, version: str) -> Path:
    lib = repo / "barn" / name
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\ndescription = "d"\n'
    )
    return lib


@pytest.fixture
def repo_agreeing(tmp_path: Path) -> Path:
    """Two barn libraries at the same version, root workspace at 0.1.0."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    _make_lib(repo, "haybale-alpha", "0.3.1")
    _make_lib(repo, "haybale-beta", "0.3.1")
    return repo


@pytest.fixture
def repo_disagreeing(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    _make_lib(repo, "haybale-alpha", "0.3.1")
    _make_lib(repo, "haybale-beta", "0.9.0")
    return repo


# ── next_version ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("spec", "current", "expected"),
    [
        ("patch", "0.0.4", "0.0.5"),
        ("minor", "0.0.4", "0.1.0"),
        ("major", "0.0.4", "1.0.0"),
        ("minor", "2.9.9", "2.10.0"),
        ("major", "9.9.9", "10.0.0"),
        ("3.4.5", "1.2.3", "3.4.5"),
        ("3.4.5", None, "3.4.5"),
    ],
)
def test_next_version(spec: str, current: str | None, expected: str) -> None:
    assert next_version(spec, current) == expected


@pytest.mark.parametrize("spec", ["major", "minor", "patch"])
def test_keyword_without_parsable_current_raises(spec: str) -> None:
    with pytest.raises(VersionError):
        next_version(spec, None)
    with pytest.raises(VersionError):
        next_version(spec, "not-a-version")


def test_malformed_explicit_version_raises() -> None:
    with pytest.raises(VersionError):
        next_version("1.2", None)
    with pytest.raises(VersionError):
        next_version("banana", None)


# ── read_barn_versions ───────────────────────────────────────────────────────


def test_read_barn_versions_excludes_the_root_pyproject(repo_agreeing: Path) -> None:
    versions = read_barn_versions(repo_agreeing)
    assert [v.name for v in versions] == ["haybale-alpha", "haybale-beta"]
    assert all(v.lib_dir.parent.name == "barn" for v in versions)


def test_read_barn_versions_skips_dirs_without_pyproject(repo_agreeing: Path) -> None:
    (repo_agreeing / "barn" / "not-a-library").mkdir()
    assert len(read_barn_versions(repo_agreeing)) == 2


def test_read_barn_versions_reports_none_for_unversioned(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    lib = repo / "barn" / "haybale-x"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-x"\n')
    assert read_barn_versions(repo)[0].version is None


# ── plan_versions ────────────────────────────────────────────────────────────


def test_plan_versions_offers_suggestions_when_all_agree(repo_agreeing: Path) -> None:
    plan = plan_versions(repo_agreeing)
    assert plan.versions_agree is True
    assert plan.common_version == "0.3.1"
    assert plan.suggestions == {"patch": "0.3.2", "minor": "0.4.0", "major": "1.0.0"}


def test_plan_versions_offers_no_suggestions_when_they_disagree(repo_disagreeing: Path) -> None:
    """A silent resolution would downgrade the higher-versioned sibling (ADR 0023)."""
    plan = plan_versions(repo_disagreeing)
    assert plan.versions_agree is False
    assert plan.common_version is None
    assert plan.suggestions == {}
    assert {v.version for v in plan.current} == {"0.3.1", "0.9.0"}


# ── write_barn_versions ──────────────────────────────────────────────────────


def test_write_barn_versions_writes_every_library(repo_disagreeing: Path) -> None:
    written = write_barn_versions(repo_disagreeing, "1.0.0")
    assert len(written) == 2
    for path in written:
        assert toml.loads(path.read_text())["project"]["version"] == "1.0.0"


def test_write_barn_versions_leaves_the_root_pyproject_untouched(repo_agreeing: Path) -> None:
    """The workspace root sits at a fixed version and depends on the library
    unversioned — nothing reads it, and bumping it is what the old
    bump_version() got wrong."""
    root = repo_agreeing / "pyproject.toml"
    before = root.read_text()
    written = write_barn_versions(repo_agreeing, "0.4.0")
    assert root not in written
    assert root.read_text() == before


def test_write_barn_versions_preserves_all_other_fields(repo_agreeing: Path) -> None:
    lib = repo_agreeing / "barn" / "haybale-alpha" / "pyproject.toml"
    write_barn_versions(repo_agreeing, "0.4.0")
    data = toml.loads(lib.read_text())
    assert data["project"]["name"] == "haybale-alpha"
    assert data["project"]["description"] == "d"


def test_write_barn_versions_returns_sorted_paths(repo_agreeing: Path) -> None:
    written = write_barn_versions(repo_agreeing, "0.4.0")
    assert written == sorted(written)


# ── refresh_lockfile ─────────────────────────────────────────────────────────


def test_refresh_lockfile_noop_without_a_lockfile(repo_agreeing: Path) -> None:
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning is None


def test_refresh_lockfile_warns_but_never_raises(repo_agreeing: Path, monkeypatch) -> None:
    """uv lock failing is a warning, not a blocker — matches bump_version's posture."""
    (repo_agreeing / "uv.lock").write_text("")

    def _fail(*_a, **_kw):
        return subprocess.CompletedProcess(["uv", "lock"], 1, "", "resolution impossible")

    monkeypatch.setattr(subprocess, "run", _fail)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is False
    assert warning is not None
    assert "resolution impossible" in warning


def test_refresh_lockfile_reports_success(repo_agreeing: Path, monkeypatch) -> None:
    (repo_agreeing / "uv.lock").write_text("")

    def _ok(*_a, **_kw):
        return subprocess.CompletedProcess(["uv", "lock"], 0, "", "")

    monkeypatch.setattr(subprocess, "run", _ok)
    refreshed, warning = refresh_lockfile(repo_agreeing)
    assert refreshed is True
    assert warning is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_versions.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.share_pipeline.versions'`

- [ ] **Step 3: Write the implementation**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/versions.py`:

```python
"""Lockstep version handling for the share pipeline.

Deliberately narrower than the ``bump_version()`` it replaces:

* Only ``barn/*/pyproject.toml`` is written. The root ``pyproject.toml`` is the
  uv workspace root at a fixed version, depends on the library **unversioned**,
  and nothing reads its version.
* When the barn versions disagree, no arithmetic is offered — the caller must
  supply an explicit target. ``bump_version``'s "first barn library found"
  heuristic silently downgraded higher-versioned siblings (ADR 0023).
* Committing and tagging live in the pipeline's step 5, not here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import toml

from haywire_studio.share_pipeline.errors import VersionError
from haywire_studio.share_pipeline.results import BumpResult, LibraryVersion, VersionPlan

BUMP_KEYWORDS = ("patch", "minor", "major")

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")

__all__ = [
    "BUMP_KEYWORDS",
    "BumpResult",
    "next_version",
    "plan_versions",
    "read_barn_versions",
    "refresh_lockfile",
    "write_barn_versions",
]


def _barn_library_dirs(repo_root: Path) -> list[Path]:
    """Every ``barn/*`` directory holding a pyproject.toml, sorted by path."""
    barn = repo_root / "barn"
    if not barn.is_dir():
        return []
    return sorted(d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file())


def read_barn_versions(repo_root: Path) -> list[LibraryVersion]:
    """Read each barn library's declared name and version.

    ``version`` is None for a library whose pyproject has no version field or
    cannot be parsed — the caller decides whether that is fatal.
    """
    out: list[LibraryVersion] = []
    for lib_dir in _barn_library_dirs(repo_root):
        pyproject = lib_dir / "pyproject.toml"
        name = lib_dir.name
        version: str | None = None
        try:
            project = toml.loads(pyproject.read_text()).get("project", {})
            name = project.get("name", lib_dir.name)
            version = project.get("version")
        except (toml.TomlDecodeError, OSError):
            pass
        out.append(LibraryVersion(lib_dir=lib_dir, name=name, version=version))
    return out


def plan_versions(repo_root: Path) -> VersionPlan:
    """Describe the current lockstep state and the bumps available from it."""
    current = read_barn_versions(repo_root)
    distinct = {v.version for v in current if v.version is not None}

    # A single distinct version across every library, and none missing, is the
    # only state where patch/minor/major arithmetic has an unambiguous input.
    agreeing = len(distinct) == 1 and all(v.version is not None for v in current)
    common = next(iter(distinct)) if agreeing else None

    suggestions: dict[str, str] = {}
    if common is not None:
        suggestions = {kw: next_version(kw, common) for kw in BUMP_KEYWORDS}

    return VersionPlan(current=current, common_version=common, suggestions=suggestions)


def next_version(spec: str, current: str | None) -> str:
    """Resolve *spec* to a concrete ``X.Y.Z``.

    *spec* is either a keyword from :data:`BUMP_KEYWORDS` (applied to
    *current*) or an explicit version. Raises :class:`VersionError` when a
    keyword has no parsable *current*, or when an explicit version is not
    ``X.Y.Z``.
    """
    if spec not in BUMP_KEYWORDS:
        if not _VERSION_RE.match(spec):
            raise VersionError(f"'{spec}' is not a valid version (expected X.Y.Z).")
        return spec

    match = _VERSION_RE.match(current or "")
    if match is None:
        raise VersionError(
            f"Cannot compute a '{spec}' bump: no parsable current version "
            f"({current!r}). Supply an explicit X.Y.Z target instead."
        )
    major, minor, patch = (int(g) for g in match.groups())
    if spec == "major":
        major, minor, patch = major + 1, 0, 0
    elif spec == "minor":
        minor, patch = minor + 1, 0
    else:
        patch += 1
    return f"{major}.{minor}.{patch}"


def write_barn_versions(repo_root: Path, version: str) -> list[Path]:
    """Write *version* into every ``barn/*/pyproject.toml``.

    Rewrites the ``version = "..."`` line with a regex rather than round-tripping
    through toml, so comments, key order, and formatting survive untouched.
    Returns the written paths, sorted.
    """
    if not _VERSION_RE.match(version):
        raise VersionError(f"'{version}' is not a valid version (expected X.Y.Z).")

    written: list[Path] = []
    for lib_dir in _barn_library_dirs(repo_root):
        pyproject = lib_dir / "pyproject.toml"
        content = pyproject.read_text()
        new_content, count = re.subn(
            r'^(version\s*=\s*")[^"]*(")',
            rf"\g<1>{version}\g<2>",
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if count == 0:
            raise VersionError(f"No version field to rewrite in {pyproject}.")
        pyproject.write_text(new_content)
        written.append(pyproject)
    return sorted(written)


def refresh_lockfile(repo_root: Path, *, timeout: float = 300.0) -> tuple[bool, str | None]:
    """Re-run ``uv lock`` so the bumped member versions land in uv.lock.

    Returns ``(refreshed, warning)``. Never raises and never blocks the
    pipeline: the lockfile records member versions and drifts one release
    behind if it isn't refreshed, but a failed lock is not a reason to abandon
    a publish. Matches ``bump_version``'s existing posture.
    """
    lock_file = repo_root / "uv.lock"
    if not lock_file.is_file():
        return (False, None)

    try:
        proc = subprocess.run(
            ["uv", "lock"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return (False, "uv not found on PATH — uv.lock left stale.")
    except subprocess.TimeoutExpired:
        return (False, f"uv lock timed out after {timeout:g}s — uv.lock left stale.")

    if proc.returncode == 0:
        return (True, None)
    return (False, f"uv lock failed (uv.lock left stale): {(proc.stderr or '').strip()}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_versions.py -v`
Expected: all passed.

- [ ] **Step 5: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/versions.py tests/share_pipeline/test_versions.py
git commit -m "feat(share): lockstep version reading, arithmetic, and writing"
```

---

### Task 4: Step 1 — preconditions, and the SharePipeline skeleton

One combined gate that reports every failure at once, plus the pipeline object that will hold the rest of the steps.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py`
- Test: `tests/share_pipeline/test_preconditions.py`

**Interfaces:**
- Consumes: `git`, `git_remote` (Task 1); `PreconditionsReport`, `PreconditionsError` (Task 2).
- Produces:
  - `SharePipeline(repo_root: Path)` — constructor takes only the project root. Attribute `repo_root: Path`. Attribute `written: list[Path]` (the accumulated write set, initially empty).
  - `SharePipeline.check_preconditions() -> PreconditionsReport` — never raises for a precondition failure; the report carries them.
  - `SharePipeline.require_preconditions() -> PreconditionsReport` — calls `check_preconditions()` and raises `PreconditionsError` when not ok. This is what the CLI's `--yes` path uses.
  - `SharePipeline.remote_url: str | None` — set by a successful check.
  - Module constant `GIT_INSTALL_HINT: str` — the same install-instructions text `init_project` prints.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_preconditions.py`:

```python
"""Step 1 — the combined precondition gate."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.share_pipeline import PreconditionsError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)


def _add_lib(repo: Path, name: str = "haybale-alpha") -> Path:
    lib = repo / "barn" / name
    (lib / name.replace("-", "_")).mkdir(parents=True)
    (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.1.0"\n')
    return lib


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    """A local bare repo usable as `origin` — makes ls-remote real without a network."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)
    return remote


@pytest.fixture
def project(tmp_path: Path, bare_remote: Path) -> Path:
    """A shareable project: git repo, one barn library, origin pointing at a real bare repo."""
    repo = tmp_path / "project"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return repo


def test_healthy_project_passes(project: Path) -> None:
    report = SharePipeline(project).check_preconditions()
    assert report.ok is True
    assert report.failures == []
    assert report.remote_url is not None
    assert [p.name for p in report.barn_libraries] == ["haybale-alpha"]


def test_missing_barn_directory_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "nobarn"
    _init_repo(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("barn" in f for f in report.failures)


def test_barn_with_no_library_fails(tmp_path: Path, bare_remote: Path) -> None:
    repo = tmp_path / "emptybarn"
    _init_repo(repo)
    (repo / "barn").mkdir()
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("pyproject.toml" in f for f in report.failures)


def test_missing_origin_fails_with_setup_instructions(tmp_path: Path) -> None:
    repo = tmp_path / "noremote"
    _init_repo(repo)
    _add_lib(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("remote add origin" in f for f in report.failures)
    assert report.remote_url is None


def test_unreachable_remote_fails(tmp_path: Path) -> None:
    """ls-remote exercises the exact credential path push uses, so auth
    failures surface here rather than after a commit and tag exist."""
    repo = tmp_path / "badremote"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(tmp_path / "does-not-exist.git")],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert any("origin" in f for f in report.failures)


def test_every_failure_is_reported_together(tmp_path: Path) -> None:
    """No barn AND no remote must both appear — fixing one shouldn't reveal the other."""
    repo = tmp_path / "broken"
    _init_repo(repo)
    report = SharePipeline(repo).check_preconditions()
    assert len(report.failures) >= 2
    assert any("barn" in f for f in report.failures)
    assert any("origin" in f for f in report.failures)


def test_missing_git_binary_reports_install_instructions(project: Path, monkeypatch) -> None:
    from haywire_studio.share_pipeline import gitcmd

    def _no_git(*_a, **_kw):
        raise FileNotFoundError("git")

    monkeypatch.setattr(gitcmd.subprocess, "run", _no_git)
    report = SharePipeline(project).check_preconditions()
    assert report.ok is False
    assert any("git-scm.com" in f for f in report.failures)


def test_require_preconditions_raises_with_all_failures(tmp_path: Path) -> None:
    repo = tmp_path / "broken2"
    _init_repo(repo)
    with pytest.raises(PreconditionsError) as excinfo:
        SharePipeline(repo).require_preconditions()
    assert len(excinfo.value.failures) >= 2


def test_require_preconditions_returns_report_when_ok(project: Path) -> None:
    report = SharePipeline(project).require_preconditions()
    assert report.ok is True


def test_successful_check_records_remote_url_on_the_pipeline(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.remote_url is None
    pipeline.check_preconditions()
    assert pipeline.remote_url is not None


def test_pipeline_starts_with_an_empty_write_set(project: Path) -> None:
    assert SharePipeline(project).written == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.share_pipeline.pipeline'`

- [ ] **Step 3: Write the pipeline skeleton with step 1**

Create `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`:

```python
"""``SharePipeline`` — the stateful engine behind every share caller.

Later steps consume earlier steps' outputs: drift resolution precedes docs, the
bumped version feeds both the docs render and the marketstall entry, and the
final commit's file list is the union of every step's writes. A stateful object
keeps that sequencing in one place instead of re-derived by each caller, and
maps onto the wizard's linear resumable stepper.

Each step is a check/plan call that mutates nothing plus an apply call that
does. ``plan()`` is the check calls run together — it is what
``haywire share --check`` exposes and what the wizard's preview panels read.
"""

from __future__ import annotations

from pathlib import Path

from haywire_studio.share_pipeline.errors import PreconditionsError
from haywire_studio.share_pipeline.gitcmd import git, git_remote
from haywire_studio.share_pipeline.results import PreconditionsReport

GIT_INSTALL_HINT = (
    "git is not installed. Install it:\n"
    "      macOS (Homebrew):  brew install git\n"
    "      Ubuntu/Debian:     sudo apt-get install git\n"
    "      Windows:           https://git-scm.com/download/win"
)

_NO_REMOTE_HINT = (
    "No 'origin' remote is configured. Set one up:\n"
    "      git remote add origin <your-repo-url>\n"
    "      git push -u origin <branch-name>"
)


class SharePipeline:
    """Drives one project's publish, one step at a time.

    Args:
        repo_root: The project root — the uv workspace root holding ``barn/``,
            ``marketstall.toml``, and the git repo.
    """

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)
        # Accumulated write set. Every apply step appends the files it wrote;
        # step 5 stages exactly this list (plus any barn files the user opted
        # in) and never uses `git add -A`.
        self.written: list[Path] = []
        self.remote_url: str | None = None

    # ── Step 1: preconditions ────────────────────────────────────────────────

    def check_preconditions(self) -> PreconditionsReport:
        """Verify everything needed to publish, collecting ALL failures.

        Reports rather than raises so the wizard's first panel can explain why
        a workspace cannot be shared. The menu item is always enabled — a
        disabled one cannot carry a tooltip, since the design guide's disabled
        state includes ``pointer-events: none`` (design-guide.md:725).

        The remote reachability check is ``git ls-remote origin``: it exercises
        the exact credential path ``git push`` uses, so an auth failure
        surfaces here rather than after a commit and tag already exist.
        """
        failures: list[str] = []
        remote_url: str | None = None

        version = git(["--version"], cwd=self.repo_root, timeout=10.0)
        if not version.ok:
            # Nothing else is checkable without git — every remaining probe
            # would report the same missing binary as a different symptom.
            return PreconditionsReport(failures=[GIT_INSTALL_HINT], remote_url=None, barn_libraries=[])

        barn = self.repo_root / "barn"
        barn_libraries: list[Path] = []
        if not barn.is_dir():
            failures.append(f"No barn/ directory at {self.repo_root}. Is this a haywire project root?")
        else:
            barn_libraries = sorted(
                d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file()
            )
            if not barn_libraries:
                failures.append(f"No library with a pyproject.toml under {barn}. Nothing to publish.")

        remote = git(["remote", "get-url", "origin"], cwd=self.repo_root, timeout=10.0)
        if not remote.ok or not remote.stdout.strip():
            failures.append(_NO_REMOTE_HINT)
        else:
            remote_url = remote.stdout.strip()
            reachable = git_remote(["ls-remote", "origin"], cwd=self.repo_root, timeout=60.0)
            if not reachable.ok:
                detail = (reachable.stderr or reachable.stdout).strip().splitlines()
                first = detail[0] if detail else f"exit {reachable.returncode}"
                failures.append(
                    f"Cannot reach origin ({remote_url}): {first}\n"
                    "      Check the URL and your credentials, then try again."
                )

        if not failures:
            self.remote_url = remote_url

        return PreconditionsReport(
            failures=failures,
            remote_url=remote_url,
            barn_libraries=barn_libraries,
        )

    def require_preconditions(self) -> PreconditionsReport:
        """:meth:`check_preconditions`, raising :class:`PreconditionsError` on failure."""
        report = self.check_preconditions()
        if not report.ok:
            raise PreconditionsError(report.failures)
        return report
```

- [ ] **Step 4: Export `SharePipeline` and `GIT_INSTALL_HINT`**

In `packages/haywire-studio/src/haywire_studio/share_pipeline/__init__.py`, add the import (after the `results` import block) and the two `__all__` entries:

```python
from haywire_studio.share_pipeline.pipeline import GIT_INSTALL_HINT, SharePipeline
```

Add `"GIT_INSTALL_HINT",` and `"SharePipeline",` to `__all__`, keeping it alphabetical.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v`
Expected: 11 passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
git commit -m "feat(share): SharePipeline skeleton with the combined precondition gate"
```

---

### Task 5: Step 2 — dependency drift

Wraps the existing `detect_share_drift` / `apply_drift_fix` from `share.py` into a per-project aggregate, and adds the Replace path the wizard's diff modal needs. Union is `apply_drift_fix` (additive). Replace overwrites declarations with exactly what was detected, so it can remove entries — a real decision, never an auto-fix.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_drift_step.py`

**Interfaces:**
- Consumes: `detect_share_drift`, `apply_drift_fix`, `_read_library_dependencies`, `_norm_dep` from `haywire_studio.share`; `DriftReport` (Task 2).
- Produces:
  - `SharePipeline.check_drift() -> DriftReport`
  - `SharePipeline.apply_drift_union(report: DriftReport) -> list[Path]` — returns the pyproject/`__init__.py` paths written, appended to `self.written`.
  - `SharePipeline.apply_drift_replace(report: DriftReport) -> list[Path]` — same return, but declarations are replaced with the detected set.
  - `SharePipeline.acknowledge_drift() -> None` — records that the user chose to continue without fixing; sets `SharePipeline.drift_acknowledged = True`.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_drift_step.py`:

```python
"""Step 2 — dependency drift detection and the Union/Replace decision."""

from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire_studio.share import DepDrift
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Two barn libraries with declared deps, no git needed for this step."""
    repo = tmp_path / "project"
    for name, deps in (("haybale-alpha", '["haywire-core~=0.0.1"]'), ("haybale-beta", "[]")):
        lib = repo / "barn" / name
        module = lib / name.replace("-", "_")
        module.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\ndependencies = {deps}\n'
        )
        (module / "__init__.py").write_text(
            '@library(label="X", id="x", dependencies=["haybale_core"])\nclass Library: pass\n'
        )
    return repo


def test_check_drift_runs_every_barn_library(project: Path) -> None:
    seen: list[Path] = []

    def _fake(lib_dir: Path) -> DepDrift:
        seen.append(lib_dir)
        return DepDrift(lib_dir=lib_dir)

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_fake):
        SharePipeline(project).check_drift()

    assert sorted(p.name for p in seen) == ["haybale-alpha", "haybale-beta"]


def test_clean_project_needs_no_decision(project: Path) -> None:
    with patch(
        "haywire_studio.share_pipeline.pipeline.detect_share_drift",
        side_effect=lambda lib_dir: DepDrift(lib_dir=lib_dir),
    ):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    assert report.drifted == []
    assert report.unresolved_only == []


def test_actionable_drift_needs_a_decision(project: Path) -> None:
    def _drifty(lib_dir: Path) -> DepDrift:
        if lib_dir.name == "haybale-alpha":
            return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])
        return DepDrift(lib_dir=lib_dir)

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is True
    assert [d.lib_dir.name for d in report.drifted] == ["haybale-alpha"]


def test_unresolved_imports_alone_never_gate(project: Path) -> None:
    """Unresolved imports are usually dynamic — gating on them would fire every run."""

    def _unresolved(lib_dir: Path) -> DepDrift:
        return DepDrift(lib_dir=lib_dir, unresolved=["some.dynamic.module"])

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_unresolved):
        report = SharePipeline(project).check_drift()

    assert report.needs_decision is False
    assert len(report.unresolved_only) == 2


def test_apply_drift_union_is_additive(project: Path) -> None:
    """Union keeps existing declarations and adds the detected ones."""
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    def _fake_fix(d: DepDrift) -> None:
        data = toml.loads((d.lib_dir / "pyproject.toml").read_text())
        deps = sorted({*data["project"]["dependencies"], "numpy>=1.0"})
        data["project"]["dependencies"] = deps
        (d.lib_dir / "pyproject.toml").write_text(toml.dumps(data))

    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix", side_effect=_fake_fix):
        written = pipeline.apply_drift_union(report)  # type: ignore[arg-type]

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert "numpy>=1.0" in deps
    assert "haywire-core~=0.0.1" in deps  # nothing removed
    assert lib / "pyproject.toml" in written
    assert lib / "pyproject.toml" in pipeline.written


def test_apply_drift_replace_can_remove_declarations(project: Path) -> None:
    """Replace overwrites with exactly what was detected — that's why it's a decision."""
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    class _Detected:
        pyproject = ["numpy>=1.0"]
        library_decorator = ["haybale_core"]
        unresolved: list[str] = []

    pipeline = SharePipeline(project)
    with patch(
        "haywire_studio.share_pipeline.pipeline.detect_deps",
        return_value=_Detected(),
    ):
        written = pipeline.apply_drift_replace(report)  # type: ignore[arg-type]

    deps = toml.loads((lib / "pyproject.toml").read_text())["project"]["dependencies"]
    assert deps == ["numpy>=1.0"]
    assert "haywire-core~=0.0.1" not in deps  # removed — the destructive path
    assert lib / "pyproject.toml" in written


def test_apply_drift_replace_rewrites_the_decorator(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    init_file = lib / "haybale_alpha" / "__init__.py"
    drift = DepDrift(lib_dir=lib, decorator_missing=["haybale_studio"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()

    class _Detected:
        pyproject: list[str] = []
        library_decorator = ["haybale_studio"]
        unresolved: list[str] = []

    with patch("haywire_studio.share_pipeline.pipeline.detect_deps", return_value=_Detected()):
        written = SharePipeline(project).apply_drift_replace(report)  # type: ignore[arg-type]

    content = init_file.read_text()
    assert "haybale-studio" in content or "haybale_studio" in content
    assert init_file in written


def test_acknowledge_drift_records_the_choice(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.drift_acknowledged is False
    pipeline.acknowledge_drift()
    assert pipeline.drift_acknowledged is True


def test_written_set_never_duplicates(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    drift = DepDrift(lib_dir=lib, pyproject_missing=["numpy"])
    report = type("R", (), {"drifted": [drift], "unresolved_only": []})()
    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix"):
        pipeline.apply_drift_union(report)  # type: ignore[arg-type]
        pipeline.apply_drift_union(report)  # type: ignore[arg-type]
    assert len(pipeline.written) == len(set(pipeline.written))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_drift_step.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'check_drift'`

- [ ] **Step 3: Add the imports and the `_record` helper**

In `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`, extend the import block. The `share` imports are module-level (not lazy) so tests can `patch("haywire_studio.share_pipeline.pipeline.detect_share_drift")`:

```python
from haywire.core.library.dep_detect import (
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)
from haywire.core.library.decorator_io import _set_decorator_list_field
from haywire_studio.share import apply_drift_fix, detect_share_drift
from haywire_studio.share_pipeline.results import DriftReport
```

Add to `__init__`:

```python
        # Set when the user chose to continue past unresolved drift rather than
        # fix it. Step 5 records it in nothing — it exists so a caller can tell
        # "clean" from "acknowledged" without re-running detection.
        self.drift_acknowledged = False
```

Add the write-set helper as a method:

```python
    def _record(self, paths: list[Path]) -> list[Path]:
        """Append *paths* to the accumulated write set, de-duplicated, and return them.

        Step 5 stages exactly ``self.written``, so a duplicate would make the
        commit preview lie about how many files changed.
        """
        for path in paths:
            if path not in self.written:
                self.written.append(path)
        return paths
```

- [ ] **Step 4: Add the drift step methods**

Append to `SharePipeline`:

```python
    # ── Step 2: dependency drift ─────────────────────────────────────────────

    def check_drift(self) -> DriftReport:
        """Run the drift gate against every barn library.

        Splits findings into actionable drift (a decision) and unresolved-only
        (informational). Reuses the same ``detect_share_drift`` the Edit
        dialog's "Detect dependencies" flow uses, so the wizard's diff modal
        shows what users already recognise.
        """
        drifted: list[object] = []
        unresolved_only: list[object] = []
        for lib_dir in self._barn_library_dirs():
            drift = detect_share_drift(lib_dir)
            if drift.has_drift:
                drifted.append(drift)
            elif drift.unresolved:
                unresolved_only.append(drift)
        return DriftReport(drifted=drifted, unresolved_only=unresolved_only)

    def apply_drift_union(self, report: DriftReport) -> list[Path]:
        """Merge detected deps into what's declared. Additive — removes nothing."""
        written: list[Path] = []
        for drift in report.drifted:
            apply_drift_fix(drift)
            written.extend(self._drift_written_paths(drift.lib_dir))
        return self._record(written)

    def apply_drift_replace(self, report: DriftReport) -> list[Path]:
        """Overwrite declared deps with exactly what was detected.

        Destructive by design: a declaration the source no longer imports is
        removed. That is why step 2 is a decision and not an auto-fix.
        """
        written: list[Path] = []
        libraries = EntryPointLibrarySource()
        for drift in report.drifted:
            lib_dir = drift.lib_dir
            detected = detect_deps(lib_dir, libraries=libraries)

            set_pyproject_dependencies(lib_dir, sorted(detected.pyproject))
            written.append(lib_dir / "pyproject.toml")

            module_dir = find_module_dir(lib_dir)
            if module_dir is not None:
                init_file = module_dir / "__init__.py"
                if init_file.is_file():
                    content = _set_decorator_list_field(
                        init_file.read_text(),
                        "dependencies",
                        sorted(detected.library_decorator),
                    )
                    init_file.write_text(content)
                    written.append(init_file)
        return self._record(written)

    def acknowledge_drift(self) -> None:
        """Record that the user chose to publish without resolving drift."""
        self.drift_acknowledged = True

    def _drift_written_paths(self, lib_dir: Path) -> list[Path]:
        """The files ``apply_drift_fix`` may have touched for one library.

        ``apply_drift_fix`` returns nothing, so the paths are reconstructed
        here. Both are included unconditionally: a path already identical on
        disk is a no-op for ``git add``, whereas a missed path would silently
        leave a fix out of the commit.
        """
        paths = [lib_dir / "pyproject.toml"]
        module_dir = find_module_dir(lib_dir)
        if module_dir is not None and (module_dir / "__init__.py").is_file():
            paths.append(module_dir / "__init__.py")
        return paths

    def _barn_library_dirs(self) -> list[Path]:
        """Every ``barn/*`` directory holding a pyproject.toml, sorted."""
        barn = self.repo_root / "barn"
        if not barn.is_dir():
            return []
        return sorted(d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").is_file())
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_drift_step.py -v`
Expected: 9 passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py tests/share_pipeline/test_drift_step.py
git commit -m "feat(share): step 2 — project-wide drift gate with Union/Replace"
```

---

### Task 6: Step 3 — lockstep version bump with the tag-collision check

The tag-collision check lives here, where the fix is cheapest ("pick 0.3.2 instead") rather than after a commit exists.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_bump_step.py`

**Interfaces:**
- Consumes: `plan_versions`, `next_version`, `write_barn_versions`, `refresh_lockfile` (Task 3); `git`, `git_remote` (Task 1); `BumpResult`, `VersionPlan`, `TagCollisionError`, `VersionError` (Tasks 2–3).
- Produces:
  - `SharePipeline.plan_version() -> VersionPlan`
  - `SharePipeline.check_tag_available(version: str) -> None` — raises `TagCollisionError` when `v<version>` exists locally or on origin.
  - `SharePipeline.apply_bump(spec: str) -> BumpResult` — `spec` is a keyword or explicit `X.Y.Z`; resolves it, checks the tag, writes every barn pyproject, refreshes the lockfile, records `self.version`.
  - `SharePipeline.version: str | None`

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_bump_step.py`:

```python
"""Step 3 — lockstep bump, tag-collision pre-check, lockfile refresh."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import toml

from haywire_studio.share_pipeline import TagCollisionError, VersionError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo, bare origin, two barn libraries at 0.3.1."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=repo, check=True, capture_output=True
    )
    (repo / "pyproject.toml").write_text('[project]\nname = "ws"\nversion = "0.1.0"\n')
    for name in ("haybale-alpha", "haybale-beta"):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "0.3.1"\n')
    (repo / "seed.txt").write_text("seed\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def test_plan_version_reports_the_common_version(project: Path) -> None:
    plan = SharePipeline(project).plan_version()
    assert plan.common_version == "0.3.1"
    assert plan.suggestions["patch"] == "0.3.2"


def test_apply_bump_writes_every_barn_library(project: Path) -> None:
    pipeline = SharePipeline(project)
    result = pipeline.apply_bump("patch")

    assert result.version == "0.3.2"
    for name in ("haybale-alpha", "haybale-beta"):
        path = project / "barn" / name / "pyproject.toml"
        assert toml.loads(path.read_text())["project"]["version"] == "0.3.2"
        assert path in pipeline.written


def test_apply_bump_leaves_the_root_pyproject_alone(project: Path) -> None:
    root = project / "pyproject.toml"
    before = root.read_text()
    pipeline = SharePipeline(project)
    pipeline.apply_bump("minor")
    assert root.read_text() == before
    assert root not in pipeline.written


def test_apply_bump_accepts_an_explicit_version(project: Path) -> None:
    result = SharePipeline(project).apply_bump("2.0.0")
    assert result.version == "2.0.0"


def test_apply_bump_rejects_a_malformed_version(project: Path) -> None:
    with pytest.raises(VersionError):
        SharePipeline(project).apply_bump("2.0")


def test_apply_bump_records_the_version_on_the_pipeline(project: Path) -> None:
    pipeline = SharePipeline(project)
    assert pipeline.version is None
    pipeline.apply_bump("patch")
    assert pipeline.version == "0.3.2"


def test_local_tag_collision_is_caught_before_any_write(project: Path) -> None:
    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)
    pipeline = SharePipeline(project)

    with pytest.raises(TagCollisionError) as excinfo:
        pipeline.apply_bump("patch")

    assert excinfo.value.tag == "v0.3.2"
    assert excinfo.value.local is True
    # Nothing was written — the check runs before write_barn_versions.
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"
    assert pipeline.written == []


def test_remote_tag_collision_is_caught(project: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    def _ls_remote_tags(args, **_kw):
        if args[:2] == ["ls-remote", "--tags"]:
            return gitcmd.GitResult(
                ok=True,
                stdout="abc123\trefs/tags/v0.3.2\n",
                stderr="",
                returncode=0,
            )
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.git_remote", side_effect=_ls_remote_tags):
        with pytest.raises(TagCollisionError) as excinfo:
            SharePipeline(project).apply_bump("patch")

    assert excinfo.value.remote is True


def test_check_tag_available_passes_for_a_free_tag(project: Path) -> None:
    SharePipeline(project).check_tag_available("9.9.9")  # must not raise


def test_unreachable_remote_does_not_block_the_tag_check(project: Path) -> None:
    """A remote we can't query is step 1's problem. Here it must not become a
    false collision — that would block a legitimate publish."""
    from haywire_studio.share_pipeline import gitcmd

    def _unreachable(*_a, **_kw):
        return gitcmd.GitResult(ok=False, stdout="", stderr="could not read", returncode=128)

    with patch("haywire_studio.share_pipeline.pipeline.git_remote", side_effect=_unreachable):
        SharePipeline(project).check_tag_available("0.3.2")  # must not raise


def test_lockfile_warning_is_carried_not_raised(project: Path) -> None:
    (project / "uv.lock").write_text("")

    with patch(
        "haywire_studio.share_pipeline.pipeline.refresh_lockfile",
        return_value=(False, "uv lock failed: boom"),
    ):
        result = SharePipeline(project).apply_bump("patch")

    assert result.lock_refreshed is False
    assert result.lock_warning is not None
    assert "boom" in result.lock_warning
    assert result.version == "0.3.2"  # the bump still stands


def test_refreshed_lockfile_joins_the_write_set(project: Path) -> None:
    (project / "uv.lock").write_text("")
    pipeline = SharePipeline(project)

    with patch("haywire_studio.share_pipeline.pipeline.refresh_lockfile", return_value=(True, None)):
        result = pipeline.apply_bump("patch")

    assert result.lock_refreshed is True
    assert project / "uv.lock" in pipeline.written


def test_stale_lockfile_stays_out_of_the_write_set(project: Path) -> None:
    """A failed lock left the file untouched — staging it would commit nothing
    useful and muddy the commit preview."""
    (project / "uv.lock").write_text("")
    pipeline = SharePipeline(project)

    with patch(
        "haywire_studio.share_pipeline.pipeline.refresh_lockfile",
        return_value=(False, "uv lock failed"),
    ):
        pipeline.apply_bump("patch")

    assert project / "uv.lock" not in pipeline.written


def test_disagreeing_versions_reject_a_keyword_bump(tmp_path: Path) -> None:
    """No silent resolution — bump_version's 'first barn library' heuristic
    would downgrade the higher-versioned sibling (ADR 0023)."""
    repo = tmp_path / "mixed"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.9.0")):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    with pytest.raises(VersionError):
        SharePipeline(repo).apply_bump("patch")


def test_disagreeing_versions_accept_an_explicit_target(tmp_path: Path) -> None:
    repo = tmp_path / "mixed2"
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.9.0")):
        lib = repo / "barn" / name
        lib.mkdir(parents=True)
        (lib / "pyproject.toml").write_text(f'[project]\nname = "{name}"\nversion = "{version}"\n')

    result = SharePipeline(repo).apply_bump("1.0.0")
    assert result.version == "1.0.0"
    for name in ("haybale-alpha", "haybale-beta"):
        path = repo / "barn" / name / "pyproject.toml"
        assert toml.loads(path.read_text())["project"]["version"] == "1.0.0"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_bump_step.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'plan_version'`

- [ ] **Step 3: Add the imports**

In `pipeline.py`, add:

```python
from haywire_studio.share_pipeline.errors import TagCollisionError, VersionError
from haywire_studio.share_pipeline.results import BumpResult, VersionPlan
from haywire_studio.share_pipeline.versions import (
    next_version,
    plan_versions,
    refresh_lockfile,
    write_barn_versions,
)
```

Add to `__init__`:

```python
        self.version: str | None = None
```

- [ ] **Step 4: Add the bump step methods**

Append to `SharePipeline`:

```python
    # ── Step 3: version bump (lockstep) ──────────────────────────────────────

    def plan_version(self) -> VersionPlan:
        """The current lockstep state plus the bumps available from it."""
        return plan_versions(self.repo_root)

    def check_tag_available(self, version: str) -> None:
        """Raise :class:`TagCollisionError` if ``v<version>`` already exists.

        Checked here, before anything is written, because this is where the fix
        is cheapest — "pick 0.3.2 instead" costs nothing, whereas discovering
        the collision at tag time leaves a commit already made.

        An unreachable remote is NOT treated as a collision: that is step 1's
        job to report, and inferring "taken" from "could not ask" would block a
        legitimate publish.
        """
        tag = f"v{version}"

        local = git(["rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=self.repo_root)
        remote_probe = git_remote(["ls-remote", "--tags", "origin", tag], cwd=self.repo_root)
        remote_hit = remote_probe.ok and f"refs/tags/{tag}" in remote_probe.stdout

        if local.ok or remote_hit:
            raise TagCollisionError(tag=tag, local=local.ok, remote=remote_hit)

    def apply_bump(self, spec: str) -> BumpResult:
        """Resolve *spec*, verify the tag is free, then bump every barn library.

        *spec* is ``"patch"``/``"minor"``/``"major"`` or an explicit ``X.Y.Z``.
        A keyword against libraries whose versions disagree raises
        :class:`VersionError`: there is no honest arithmetic to apply, and
        picking one sibling's version would downgrade the others.

        ``uv lock`` is always attempted (the lockfile records member versions
        and drifts a release behind otherwise) but never blocks — a failure
        comes back as ``lock_warning``.
        """
        plan = self.plan_version()
        if spec not in ("patch", "minor", "major"):
            version = next_version(spec, None)
        elif plan.common_version is None:
            versions = ", ".join(
                f"{v.name} {v.version or '(none)'}" for v in plan.current
            )
            raise VersionError(
                f"Barn library versions disagree ({versions}), so a '{spec}' bump is ambiguous. "
                "Supply an explicit X.Y.Z target."
            )
        else:
            version = next_version(spec, plan.common_version)

        self.check_tag_available(version)

        written = write_barn_versions(self.repo_root, version)
        self._record(written)

        lock_refreshed, lock_warning = refresh_lockfile(self.repo_root)
        if lock_refreshed:
            self._record([self.repo_root / "uv.lock"])

        self.version = version
        return BumpResult(
            version=version,
            written=written,
            lock_refreshed=lock_refreshed,
            lock_warning=lock_warning,
        )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_bump_step.py -v`
Expected: 15 passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py tests/share_pipeline/test_bump_step.py
git commit -m "feat(share): step 3 — lockstep bump with tag-collision pre-check"
```

---

### Task 7: `haywire docs --json <path>`

The pipeline shells out to `haywire docs --all` and needs the coverage report back. It cannot read stdout for that: the library-system boot prints freely and not all of it is ours (library `on_enable` hooks print too). So the report goes to a file the caller names.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:427-441` (parser), `:517-542` (dispatch)
- Test: `tests/test_docs_json_flag.py`

**Interfaces:**
- Consumes: `generate_all_docs`, `generate_docs` (existing).
- Produces: CLI contract — `haywire docs --all --json <path>` writes `{library_id: [coverage_lines]}` as JSON to `<path>`. Exit code stays 0 when there are coverage gaps; only a crash is non-zero.

- [ ] **Step 1: Write the failing test**

Create `tests/test_docs_json_flag.py`:

```python
"""`haywire docs --json <path>` writes the coverage report to a file."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _run_main(argv: list[str]) -> None:
    """Invoke haywire's main() with a fake argv."""
    from haywire_studio.app import main

    with patch.object(sys, "argv", ["haywire", *argv]):
        main()


def test_json_flag_writes_the_coverage_map(tmp_path: Path) -> None:
    out = tmp_path / "coverage.json"

    with patch(
        "haywire_studio.docs_gen.generate.generate_all_docs",
        return_value={"beta": [], "alpha": ["node Foo: missing docstring"]},
    ):
        _run_main(["docs", "--all", "--json", str(out)])

    data = json.loads(out.read_text())
    assert data == {"beta": [], "alpha": ["node Foo: missing docstring"]}


def test_json_flag_creates_missing_parent_directories(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "deeper" / "coverage.json"

    with patch("haywire_studio.docs_gen.generate.generate_all_docs", return_value={}):
        _run_main(["docs", "--all", "--json", str(out)])

    assert out.is_file()
    assert json.loads(out.read_text()) == {}


def test_coverage_gaps_still_exit_zero(tmp_path: Path) -> None:
    """A coverage gap is feedback, not a failure — the pipeline must not abort on it."""
    out = tmp_path / "coverage.json"

    with patch(
        "haywire_studio.docs_gen.generate.generate_all_docs",
        return_value={"alpha": ["gap"]},
    ):
        _run_main(["docs", "--all", "--json", str(out)])  # no SystemExit

    assert json.loads(out.read_text()) == {"alpha": ["gap"]}


def test_json_without_all_writes_a_single_entry_map(tmp_path: Path) -> None:
    """`--json` on the single-library form keys the map by the library path."""
    out = tmp_path / "coverage.json"
    lib = tmp_path / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)

    with patch("haywire_studio.docs_gen.generate.generate_docs", return_value=["gap"]):
        _run_main(["docs", str(lib), "--json", str(out)])

    data = json.loads(out.read_text())
    assert list(data.values()) == [["gap"]]


def test_docs_help_documents_the_flag() -> None:
    result = subprocess.run(
        ["uv", "run", "haywire", "docs", "--help"],
        capture_output=True,
        text=True,
    )
    assert "--json" in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_docs_json_flag.py -v`
Expected: FAIL — `SystemExit: 2` / `unrecognized arguments: --json`

- [ ] **Step 3: Add the parser flag**

In `packages/haywire-studio/src/haywire_studio/app.py`, after the `docs_parser.add_argument("--all", ...)` block (currently ending at line 441), add:

```python
    docs_parser.add_argument(
        "--json",
        type=str,
        default=None,
        metavar="PATH",
        help="Write the coverage report to PATH as JSON ({library_id: [lines]}). "
        "A file sink rather than stdout, because a library-system boot prints "
        "freely to stdout and not all of it is ours.",
    )
```

- [ ] **Step 4: Write the report in the dispatch branch**

Replace the `elif args.command == "docs":` block (currently lines 517-542) with:

```python
    elif args.command == "docs":
        import json as _json

        def _write_coverage_json(coverage: dict[str, list[str]]) -> None:
            """Write the coverage map to --json's path, creating parent dirs."""
            if args.json is None:
                return
            out = Path(args.json)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(_json.dumps(coverage, indent=2), encoding="utf-8")

        if args.all:
            from haywire_studio.docs_gen.generate import generate_all_docs

            results = generate_all_docs(args.library)
            total_gaps = sum(len(gaps) for gaps in results.values())
            print(f"Generated docs for {len(results)} libraries.")
            for lib_id in sorted(results):
                gaps = results[lib_id]
                marker = f"{len(gaps)} coverage gap(s)" if gaps else "clean"
                print(f"  • {lib_id}: {marker}")
                for line in gaps:
                    print(f"      - {line}")
            print(f"Total coverage gaps: {total_gaps}.")
            _write_coverage_json(results)
            return

        from haywire_studio.docs_gen.generate import generate_docs

        coverage = generate_docs(args.library)
        if coverage:
            print("Documentation coverage gaps:")
            for line in coverage:
                print(f"  - {line}")
        else:
            print("Docs generated. No coverage gaps.")
        # The single-library form has no library id to key by, so the path the
        # user named is the key. Keeps --json's shape identical for both forms.
        _write_coverage_json({str(args.library or Path.cwd()): coverage})
        return
```

`Path` is already imported at the top of `app.py`; if it is not, add `from pathlib import Path` to the module imports rather than importing it inside the branch.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_docs_json_flag.py -v`
Expected: 5 passed.

- [ ] **Step 6: Verify against the real repo (integration sanity)**

Run: `uv run haywire docs --all --json /tmp/hw-cov.json && python3 -c "import json;print(sorted(json.load(open('/tmp/hw-cov.json'))))"`
Expected: a list of this repo's library ids. This also confirms the flag works with a real library-system boot, where stdout is noisy.

- [ ] **Step 7: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/app.py tests/test_docs_json_flag.py
uv run ruff format packages/haywire-studio/src/haywire_studio/app.py tests/test_docs_json_flag.py
uv run mypy packages/haywire-studio/src/
```

```bash
git add packages/haywire-studio/src/haywire_studio/app.py tests/test_docs_json_flag.py
git commit -m "feat(docs): haywire docs --json writes the coverage report to a file"
```

---

### Task 8: Step 4 — docs regeneration as a streamed subprocess

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_docs_step.py`

**Interfaces:**
- Consumes: `DocsResult`, `DocsGenerationError` (Task 2); the `--json` contract (Task 7).
- Produces:
  - `SharePipeline.docs_command() -> list[str]` — the exact argv, exposed so tests and the CLI can show it.
  - `async SharePipeline.apply_docs(on_output: Callable[[str], None] | None = None) -> DocsResult` — runs the subprocess, streams lines, parses the JSON report, records every changed doc path in `self.written`.
  - `SharePipeline.docs_write_set() -> list[Path]` — the doc paths that differ from `HEAD` after generation (including deletions), via `git status --porcelain`.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_docs_step.py`:

```python
"""Step 4 — docs regeneration via a subprocess, never in-process."""

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from haywire_studio.share_pipeline import DocsGenerationError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True, capture_output=True)
    lib = repo / "barn" / "haybale-alpha" / "haybale_alpha"
    lib.mkdir(parents=True)
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text(
        '[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n'
    )
    (lib / "OVERVIEW.md").write_text("old overview\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def test_docs_command_shells_out_with_all_and_json(project: Path) -> None:
    """In-process generation would repoint the live app's global injector and
    instantiate every node (hardware grabs) — see
    .insights/project_docs_gen_reentrancy.md."""
    cmd = SharePipeline(project).docs_command()
    assert cmd[:2] == ["haywire", "docs"] or cmd[:4] == ["uv", "run", "haywire", "docs"]
    assert "--all" in cmd
    assert "--json" in cmd


def test_docs_command_never_names_a_single_library(project: Path) -> None:
    """--all is one library-system load for the whole barn, and its
    root-relative filter excludes site-packages and --dev out-of-tree libs."""
    cmd = SharePipeline(project).docs_command()
    assert "haybale-alpha" not in " ".join(cmd)


@pytest.mark.anyio
async def test_apply_docs_parses_the_coverage_report(project: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        # The real subprocess writes the report; emulate that side effect.
        json_path = Path(cmd[cmd.index("--json") + 1])
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps({"alpha": ["node Foo: no docstring"], "beta": []}))
        on_output("Generated docs for 2 libraries.")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_fake_stream):
        result = await pipeline.apply_docs()

    assert result.coverage == {"alpha": ["node Foo: no docstring"], "beta": []}
    assert result.total_gaps == 1


@pytest.mark.anyio
async def test_apply_docs_streams_every_line(project: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        for line in ("loading libraries…", "  • alpha: clean"):
            on_output(line)
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    lines: list[str] = []
    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_fake_stream):
        await SharePipeline(project).apply_docs(on_output=lines.append)

    assert lines == ["loading libraries…", "  • alpha: clean"]


@pytest.mark.anyio
async def test_apply_docs_raises_on_a_crash(project: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    async def _crash(cmd, *, cwd, on_output, timeout=None):
        on_output("Traceback (most recent call last):")
        return gitcmd.GitResult(ok=False, stdout="boom", stderr="boom", returncode=1)

    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_crash):
        with pytest.raises(DocsGenerationError) as excinfo:
            await SharePipeline(project).apply_docs()

    assert "boom" in excinfo.value.output or "boom" in str(excinfo.value)


@pytest.mark.anyio
async def test_apply_docs_records_modified_and_deleted_docs(project: Path) -> None:
    """Renamed components leave orphan docs that the generator DELETES
    (generate.py:87). A deletion must reach the commit, or the stale file ships."""
    from haywire_studio.share_pipeline import gitcmd

    module = project / "barn" / "haybale-alpha" / "haybale_alpha"

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        (module / "OVERVIEW.md").write_text("new overview\n")  # modified
        (module / "QUICKREF.md").write_text("quickref\n")  # added
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    # Commit a doc that generation will remove, so a deletion is in the diff.
    docs = module / "docs"
    docs.mkdir()
    (docs / "old-node.md").write_text("stale\n")
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "stale doc"], cwd=project, check=True, capture_output=True)
    (docs / "old-node.md").unlink()

    pipeline = SharePipeline(project)
    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_fake_stream):
        result = await pipeline.apply_docs()

    names = {p.name for p in result.written}
    assert "OVERVIEW.md" in names
    assert "QUICKREF.md" in names
    assert "old-node.md" in names  # the deletion
    for path in result.written:
        assert path in pipeline.written


@pytest.mark.anyio
async def test_apply_docs_ignores_changes_outside_barn(project: Path) -> None:
    """Only barn content ships to consumers; unrelated dirt is not the wizard's business."""
    from haywire_studio.share_pipeline import gitcmd

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        Path(cmd[cmd.index("--json") + 1]).write_text("{}")
        (project / "scratch.md").write_text("unrelated\n")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_fake_stream):
        result = await SharePipeline(project).apply_docs()

    assert all("scratch.md" != p.name for p in result.written)


@pytest.mark.anyio
async def test_apply_docs_cleans_up_its_temp_json(project: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    captured: dict[str, Path] = {}

    async def _fake_stream(cmd, *, cwd, on_output, timeout=None):
        path = Path(cmd[cmd.index("--json") + 1])
        captured["path"] = path
        path.write_text("{}")
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.run_streaming", side_effect=_fake_stream):
        await SharePipeline(project).apply_docs()

    assert not captured["path"].exists()
```

`tests/conftest.py` does NOT provide an `anyio_backend` fixture — the repo's convention is one per file (see `tests/test_library_manager_dry_run.py:12`). Create `tests/share_pipeline/conftest.py` so every async test in this directory gets one:

```python
"""Shared fixtures for the share-pipeline tests."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """anyio's backend parametrization. The repo runs asyncio only."""
    return "asyncio"
```

Every later test file in `tests/share_pipeline/` relies on this. Test files outside that directory (`tests/test_share_cli.py`, `tests/test_share_wizard_ui.py`) each need their own copy of the fixture at module level:

```python
@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_docs_step.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'docs_command'`

- [ ] **Step 3: Add a generic streaming runner to `gitcmd.py`**

`git_remote_streaming` is git-specific; docs generation needs the same streaming shape for an arbitrary argv. Append to `packages/haywire-studio/src/haywire_studio/share_pipeline/gitcmd.py`:

```python
async def run_streaming(
    cmd: list[str],
    *,
    cwd: Path,
    on_output: Callable[[str], None],
    timeout: float = 900.0,
) -> GitResult:
    """Run an arbitrary command, streaming merged stdout/stderr per line.

    Same contract as :func:`git_remote_streaming` (nothing raises, everything
    comes back as a :class:`GitResult`) for non-git subprocesses — currently
    ``haywire docs``. The default timeout is generous: a full library-system
    boot plus per-node extraction is minutes, not seconds, on a large barn.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        return GitResult(ok=False, stdout="", stderr=f"{cmd[0]} not found: {exc}", returncode=127)

    lines: list[str] = []

    async def _drain() -> None:
        assert proc.stdout is not None
        async for raw in proc.stdout:
            text = raw.decode(errors="replace").rstrip()
            on_output(text)
            lines.append(text)
        await proc.wait()

    try:
        await asyncio.wait_for(_drain(), timeout=timeout)
    except (TimeoutError, asyncio.TimeoutError):
        proc.kill()
        await proc.wait()
        output = "\n".join(lines)
        return GitResult(
            ok=False,
            stdout=output,
            stderr=f"{' '.join(cmd)} timed out after {timeout:g}s",
            returncode=124,
            timed_out=True,
        )

    output = "\n".join(lines)
    rc = proc.returncode if proc.returncode is not None else 1
    return GitResult(ok=rc == 0, stdout=output, stderr=output if rc != 0 else "", returncode=rc)
```

Add `run_streaming` to the `gitcmd` imports in `__init__.py` and to `__all__`.

- [ ] **Step 4: Add the docs step to the pipeline**

In `pipeline.py`, extend the imports:

```python
import json
import shutil
import sys
import tempfile

from haywire_studio.share_pipeline.errors import DocsGenerationError
from haywire_studio.share_pipeline.gitcmd import run_streaming
from haywire_studio.share_pipeline.results import DocsResult
```

Append to `SharePipeline`:

```python
    # ── Step 4: regenerate docs ──────────────────────────────────────────────

    def docs_command(self, json_path: Path | None = None) -> list[str]:
        """The argv for docs generation. ``--all``, always a subprocess.

        A subprocess because ``generate_docs()`` builds a SECOND library system
        whose ``initialize()`` calls ``set_global_injector()``, which in-studio
        repoints the live app's globals at a throwaway system (DI context is
        module-level globals, not ContextVar). ``extract_library`` also
        instantiates every node in a throwaway graph to read ports, which
        in-process would construct hardware-touching nodes inside the live app.
        See ``.insights/project_docs_gen_reentrancy.md``.

        ``--all`` rather than N per-library runs: one library-system load for
        the whole barn, and its root-relative filter naturally excludes
        site-packages installs and ``--dev`` mode's out-of-tree dev-repo
        libraries.
        """
        target = str(json_path) if json_path is not None else "<json-path>"
        # sys.executable -m keeps the subprocess on the same interpreter and
        # virtualenv as the studio, without depending on `haywire` being on PATH.
        return [sys.executable, "-m", "haywire_studio", "docs", "--all", "--json", target]

    async def apply_docs(self, on_output: Callable[[str], None] | None = None) -> DocsResult:
        """Regenerate every barn library's docs. Always runs — no yes/no gate.

        Must run AFTER the version bump: ``render_quickref`` embeds
        ``v{doc.version}``, so generating first would publish a QUICKREF
        stating the previous version.

        Coverage gaps are read-only feedback and never fail the step; only a
        non-zero exit (a crash) raises :class:`DocsGenerationError`.
        """
        sink = on_output or (lambda _line: None)
        tmp_dir = Path(tempfile.mkdtemp(prefix="hw-share-docs-"))
        json_path = tmp_dir / "coverage.json"
        try:
            result = await run_streaming(
                self.docs_command(json_path),
                cwd=self.repo_root,
                on_output=sink,
            )
            if not result.ok:
                raise DocsGenerationError(
                    f"Docs generation failed (exit {result.returncode}). "
                    "The output above shows what broke.",
                    output=result.stdout or result.stderr,
                )

            coverage: dict[str, list[str]] = {}
            if json_path.is_file():
                try:
                    coverage = json.loads(json_path.read_text())
                except json.JSONDecodeError as exc:
                    raise DocsGenerationError(
                        f"Docs generation wrote an unreadable coverage report: {exc}",
                        output=result.stdout,
                    ) from exc
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        written = self.docs_write_set()
        self._record(written)
        return DocsResult(coverage=coverage, written=written, output=result.stdout)

    def docs_write_set(self) -> list[Path]:
        """Doc files under ``barn/`` that now differ from HEAD.

        Read from ``git status --porcelain`` rather than predicted, because the
        generator's file set is data-dependent: it writes OVERVIEW/QUICKREF/
        README plus one file per component, and DELETES orphaned per-component
        docs when a component is renamed (generate.py:87). A deletion left out
        of the commit ships a stale doc.

        Scoped to ``barn/`` — only barn content reaches consumers, and sweeping
        up unrelated dirt is what makes a wizard commit untrustworthy.
        """
        status = git(["status", "--porcelain", "--", "barn"], cwd=self.repo_root)
        if not status.ok:
            return []

        out: list[Path] = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            path_part = line[3:].strip()
            # Renames print "old -> new"; the new path is what to stage.
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            path_part = path_part.strip('"')
            path = self.repo_root / path_part
            if path.suffix.lower() == ".md":
                out.append(path)
        return sorted(set(out))
```

Add `Callable` to the `typing` import in `pipeline.py`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_docs_step.py -v`
Expected: 8 passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/test_docs_step.py
git commit -m "feat(share): step 4 — docs regeneration as a streamed subprocess"
```

---

### Task 9: Extract the marketstall write from `share.py`

`share_save_repo` today mixes the barn walk, the drift gate, printing, and README rewriting. The pipeline needs the walk and the write without the gate or the prints — the gate is step 2 and printing belongs to a caller. This task splits them without changing behaviour for the CLI paths that remain.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share.py`
- Modify: `tests/test_share_save.py`
- Test: `tests/test_share_marketstall_write.py`

**Interfaces:**
- Consumes: `_build_entry_for_library`, `_derive_url`, `_update_repo_readmes`, `NoBarnError` (all existing in `share.py`).
- Produces:
  - `build_marketstall_entries(repo_root: Path) -> list[dict]` — every `barn/*` entry, sorted by directory. Raises `NoBarnError` when there is no `barn/`.
  - `write_marketstall(repo_root: Path, *, ref: str | None = None, tag: str | None = None, update_readme: bool = True) -> MarketstallWriteResult` — writes `marketstall.toml`, optionally rewrites README markers, and reports every path written.
  - `MarketstallWriteResult` — frozen dataclass: `out_path: Path`, `share_url: str | None`, `warning: str | None`, `readmes: list[Path]`. Property `written: list[Path]` = `[out_path, *readmes]`.
  - `share_save_repo` keeps its signature and `ShareSaveResult` return, now delegating to `write_marketstall`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_share_marketstall_write.py`:

```python
"""The marketstall walk and write, split out of share_save_repo."""

from pathlib import Path

import pytest
import toml

from haywire_studio.share import NoBarnError, build_marketstall_entries, write_marketstall

pytestmark = pytest.mark.unit


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A repo with two barn libraries and a root README carrying the marker pair."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    for name, version in (("haybale-alpha", "0.3.1"), ("haybale-beta", "0.3.1")):
        lib = repo / "barn" / name
        (lib / name.replace("-", "_")).mkdir(parents=True)
        (lib / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "{version}"\ndescription = "d"\n'
        )
        (lib / "README.md").write_text(
            "# lib\n<!-- marketstall:share-url:start -->\nold\n<!-- marketstall:share-url:end -->\n"
        )
    (repo / "README.md").write_text(
        "# root\n<!-- marketstall:share-url:start -->\nold\n<!-- marketstall:share-url:end -->\n"
    )
    return repo


def test_build_entries_covers_every_barn_library(repo: Path) -> None:
    """The feed's contract is 'every haybale this repo offers' — a partial
    rebuild would silently delete sibling entries."""
    entries = build_marketstall_entries(repo)
    assert sorted(e["name"] for e in entries) == ["haybale-alpha", "haybale-beta"]


def test_build_entries_skips_dirs_without_pyproject(repo: Path) -> None:
    (repo / "barn" / "scratch").mkdir()
    assert len(build_marketstall_entries(repo)) == 2


def test_build_entries_without_barn_raises(tmp_path: Path) -> None:
    with pytest.raises(NoBarnError):
        build_marketstall_entries(tmp_path)


def test_write_marketstall_writes_the_feed(repo: Path) -> None:
    result = write_marketstall(repo)
    assert result.out_path == repo / "marketstall.toml"
    data = toml.loads(result.out_path.read_text())
    assert sorted(p["name"] for p in data["haybales"]) == ["haybale-alpha", "haybale-beta"]


def test_write_marketstall_runs_no_drift_gate(repo: Path, monkeypatch) -> None:
    """Drift is step 2's decision. A second gate here would re-ask a settled question."""
    from haywire_studio import share

    def _boom(*_a, **_kw):
        raise AssertionError("write_marketstall must not run the drift gate")

    monkeypatch.setattr(share, "detect_share_drift", _boom)
    write_marketstall(repo)  # must not raise


def test_write_marketstall_reports_every_written_path(repo: Path) -> None:
    """Step 5 stages exactly what it's told; a missed README ships a stale URL."""
    result = write_marketstall(repo)
    names = {p.name for p in result.written}
    assert "marketstall.toml" in names
    # No git remote in this fixture, so no URL is derivable and no README is rewritten.
    assert result.share_url is None
    assert result.warning is not None


def test_write_marketstall_skips_readmes_when_asked(repo: Path) -> None:
    result = write_marketstall(repo, update_readme=False)
    assert result.readmes == []


def test_written_property_puts_the_feed_first(repo: Path) -> None:
    result = write_marketstall(repo, update_readme=False)
    assert result.written[0] == result.out_path
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_share_marketstall_write.py -v`
Expected: collection error — `ImportError: cannot import name 'build_marketstall_entries'`

- [ ] **Step 3: Add the two functions and the result type**

In `packages/haywire-studio/src/haywire_studio/share.py`, add above `share_save_repo`:

```python
@dataclass(frozen=True)
class MarketstallWriteResult:
    """Output of :func:`write_marketstall`.

    ``readmes`` lists only the READMEs actually rewritten (they had the marker
    pair AND the URL changed), so a caller staging ``written`` never stages a
    file it didn't touch.
    """

    out_path: Path
    share_url: str | None
    warning: str | None
    readmes: list[Path]

    @property
    def written(self) -> list[Path]:
        return [self.out_path, *self.readmes]


def build_marketstall_entries(repo_root: Path) -> list[dict]:
    """Build a marketstall entry for every ``barn/*`` library, sorted by directory.

    The feed's contract is "every haybale this repo offers", so it is always
    rebuilt from disk in full — a partial rebuild silently deletes the entries
    of libraries that weren't part of this run.

    Raises :class:`NoBarnError` when ``<repo_root>/barn`` does not exist.
    """
    barn = repo_root / "barn"
    if not barn.is_dir():
        raise NoBarnError(f"no barn/ directory at {repo_root}")

    entries: list[dict] = []
    for lib_dir in sorted(d for d in barn.iterdir() if d.is_dir() and (d / "pyproject.toml").exists()):
        entry = _build_entry_for_library(lib_dir)
        if entry is not None:
            entries.append(entry)
    return entries


_MARKETSTALL_HEADER = (
    "# marketstall.toml — share this file's raw URL so others can subscribe to your library feed\n"
    "# Run: haywire share   to update this file\n\n"
)


def write_marketstall(
    repo_root: Path,
    *,
    ref: str | None = None,
    tag: str | None = None,
    update_readme: bool = True,
) -> MarketstallWriteResult:
    """Rebuild ``<repo_root>/marketstall.toml`` from every ``barn/*`` library.

    Deliberately does NOT run the dependency-drift gate: drift is the share
    pipeline's step 2, where the user makes a Union/Replace decision, and a
    second gate here would re-ask a settled question. Prints nothing — callers
    own their own output.
    """
    entries = build_marketstall_entries(repo_root)

    out_path = repo_root / "marketstall.toml"
    out_path.write_text(_MARKETSTALL_HEADER + toml.dumps({"haybales": entries}))

    url_result = _derive_url(repo_root, out_path, ref=ref, tag=tag)
    readmes: list[Path] = []
    if url_result.share_url is not None and update_readme:
        readmes = _update_repo_readmes(repo_root, url_result.share_url)

    return MarketstallWriteResult(
        out_path=out_path,
        share_url=url_result.share_url,
        warning=url_result.warning,
        readmes=readmes,
    )
```

- [ ] **Step 4: Make `share_save_repo` delegate**

Replace the body of `share_save_repo` after its drift-gate section (the block from `entries: list[dict] = []` through `return result`) with:

```python
    written = write_marketstall(repo_root, ref=ref, tag=tag, update_readme=update_readme)
    return ShareSaveResult(
        out_path=written.out_path,
        share_url=written.share_url,
        warning=written.warning,
    )
```

Leave the drift-gate section above it untouched — `share_save_repo` is deleted in Task 13, and keeping it behaviour-identical until then means the existing tests stay a safety net.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_share_marketstall_write.py tests/test_share_save.py tests/test_share_url_derivation.py tests/test_share_readme_markers.py -v`
Expected: all passed. `test_share_save.py` must pass unchanged — this task is a refactor.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share.py tests/test_share_marketstall_write.py
uv run ruff format packages/haywire-studio/src/haywire_studio/share.py tests/test_share_marketstall_write.py
uv run mypy packages/haywire-studio/src/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share.py tests/test_share_marketstall_write.py
git commit -m "refactor(share): split the marketstall walk and write out of share_save_repo"
```

---

### Task 10: Step 5 — marketstall, commit, and tag

The highest-risk task: the file-scoping logic. Test it against a real `git` in `tmp_path`, not mocks — this is where a git-plumbing subtlety would hide.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_commit_step.py`

**Interfaces:**
- Consumes: `write_marketstall`, `MarketstallWriteResult` (Task 9); `CommitPlan`, `CommitResult`, `BarnDirtyFile`, `CommitError` (Task 2); `git`, `git_remote` (Task 1).
- Produces:
  - `SharePipeline.apply_marketstall(*, ref: str | None = None, tag: str | None = None) -> MarketstallWriteResult`
  - `SharePipeline.barn_dirty_files() -> list[BarnDirtyFile]` — uncommitted content under `barn/` that is NOT already in `self.written`.
  - `SharePipeline.plan_commit(*, message: str | None = None) -> CommitPlan` — default message `chore: share v<version>`; `diffstat` filled from `git diff --stat` over the planned files.
  - `SharePipeline.verify_push_allowed() -> None` — `git push --dry-run`; raises `PushError` on rejection.
  - `SharePipeline.apply_commit(plan: CommitPlan, *, include_barn: list[Path] | None = None) -> CommitResult`
  - `SharePipeline.current_branch() -> str`

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_commit_step.py`:

```python
"""Step 5 — marketstall rebuild, commit file-scoping, tag. Real git, no mocks."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.share_pipeline import CommitError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return result.stdout


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo with a bare origin, one barn library, one seeded commit."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@t.test")
    _git(repo, "config", "user.name", "T")
    _git(repo, "remote", "add", "origin", str(remote))

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    (lib / "README.md").write_text("# alpha\n")
    (repo / "README.md").write_text("# root\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "seed")
    _git(repo, "push", "-u", "origin", "HEAD")
    return repo


def _ready(project: Path, version: str = "0.3.2") -> SharePipeline:
    """A pipeline as it looks after step 3: version set, one file written."""
    pipeline = SharePipeline(project)
    pipeline.version = version
    pyproject = project / "barn" / "haybale-alpha" / "pyproject.toml"
    pyproject.write_text(f'[project]\nname = "haybale-alpha"\nversion = "{version}"\n')
    pipeline._record([pyproject])
    return pipeline


# ── marketstall ──────────────────────────────────────────────────────────────


def test_apply_marketstall_records_what_it_wrote(project: Path) -> None:
    pipeline = _ready(project)
    result = pipeline.apply_marketstall()
    assert result.out_path.is_file()
    assert result.out_path in pipeline.written


# ── barn_dirty_files ─────────────────────────────────────────────────────────


def test_untracked_barn_file_is_surfaced(project: Path) -> None:
    """Uncommitted barn content is silently ABSENT for consumers — they install
    from a clone. It's the one working-tree state that corrupts a publish."""
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")
    dirty = _ready(project).barn_dirty_files()
    assert [d.path.name for d in dirty] == ["icon.png"]
    assert dirty[0].untracked is True


def test_modified_tracked_barn_file_is_surfaced(project: Path) -> None:
    (project / "barn" / "haybale-alpha" / "README.md").write_text("# alpha edited\n")
    dirty = _ready(project).barn_dirty_files()
    assert [d.path.name for d in dirty] == ["README.md"]
    assert dirty[0].untracked is False


def test_pipeline_own_writes_are_not_listed_as_dirty(project: Path) -> None:
    """The bumped pyproject is already in the write set; listing it twice would
    ask the user to opt into a file the wizard is committing anyway."""
    pipeline = _ready(project)
    assert all(d.path.name != "pyproject.toml" for d in pipeline.barn_dirty_files())


def test_dirt_outside_barn_is_never_mentioned(project: Path) -> None:
    """It has no bearing on what consumers get, and warning about it would
    train users to ignore the warning that matters."""
    (project / "notes.txt").write_text("wip\n")
    (project / "README.md").write_text("# root edited\n")
    assert _ready(project).barn_dirty_files() == []


def test_gitignored_barn_files_are_not_listed(project: Path) -> None:
    """An ignored file is an expression of intent; `git add` would fail on it."""
    (project / ".gitignore").write_text("__pycache__/\n")
    cache = project / "barn" / "haybale-alpha" / "haybale_alpha" / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_bytes(b"\x00")
    dirty = _ready(project).barn_dirty_files()
    assert all("__pycache__" not in str(d.path) for d in dirty)


# ── plan_commit ──────────────────────────────────────────────────────────────


def test_plan_commit_defaults_the_message_to_the_version(project: Path) -> None:
    plan = _ready(project).plan_commit()
    assert plan.message == "chore: share v0.3.2"
    assert plan.tag == "v0.3.2"


def test_plan_commit_accepts_a_custom_message(project: Path) -> None:
    plan = _ready(project).plan_commit(message="release: alpha goes 0.3.2")
    assert plan.message == "release: alpha goes 0.3.2"
    assert plan.tag == "v0.3.2"  # the tag never follows the message


def test_plan_commit_lists_exactly_the_accumulated_writes(project: Path) -> None:
    pipeline = _ready(project)
    pipeline.apply_marketstall()
    plan = pipeline.plan_commit()
    assert set(plan.files) == set(pipeline.written)


def test_plan_commit_includes_a_diffstat(project: Path) -> None:
    plan = _ready(project).plan_commit()
    assert "pyproject.toml" in plan.diffstat


def test_plan_commit_without_a_version_raises(project: Path) -> None:
    from haywire_studio.share_pipeline import PipelineStateError

    pipeline = SharePipeline(project)
    with pytest.raises(PipelineStateError):
        pipeline.plan_commit()


# ── apply_commit ─────────────────────────────────────────────────────────────


def test_apply_commit_stages_only_the_planned_files(project: Path) -> None:
    """Never -a/-A: a checkpoint-style sweep would drag the user's unrelated
    work-in-progress into a wizard-authored commit."""
    pipeline = _ready(project)
    (project / "unrelated.txt").write_text("wip\n")
    (project / "barn" / "haybale-alpha" / "stray.py").write_text("# stray\n")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan)

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "unrelated.txt" not in committed
    assert "barn/haybale-alpha/stray.py" not in committed
    assert "barn/haybale-alpha/pyproject.toml" in committed


def test_apply_commit_creates_the_tag_on_that_commit(project: Path) -> None:
    pipeline = _ready(project)
    plan = pipeline.plan_commit()
    result = pipeline.apply_commit(plan)

    tagged = _git(project, "rev-list", "-n", "1", "v0.3.2").strip()
    head = _git(project, "rev-parse", "HEAD").strip()
    assert tagged == head == result.sha
    assert result.tag == "v0.3.2"


def test_apply_commit_includes_opted_in_barn_files(project: Path) -> None:
    pipeline = _ready(project)
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan, include_barn=[asset])

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" in committed


def test_apply_commit_excludes_barn_files_not_opted_in(project: Path) -> None:
    pipeline = _ready(project)
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan, include_barn=[])

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" not in committed


def test_apply_commit_stages_deletions(project: Path) -> None:
    """Renamed components leave orphan docs the generator deletes; a deletion
    left unstaged ships the stale file."""
    pipeline = _ready(project)
    doomed = project / "barn" / "haybale-alpha" / "haybale_alpha" / "docs" / "old.md"
    doomed.parent.mkdir(parents=True)
    doomed.write_text("stale\n")
    _git(project, "add", "-A")
    _git(project, "commit", "-m", "add doc")

    doomed.unlink()
    pipeline._record([doomed])

    plan = pipeline.plan_commit()
    pipeline.apply_commit(plan)

    committed = _git(project, "show", "--name-only", "--format=", "HEAD").split()
    assert "barn/haybale-alpha/haybale_alpha/docs/old.md" in committed
    assert not doomed.exists()


def test_apply_commit_authors_exactly_one_commit(project: Path) -> None:
    """No checkpoint commit — the pre-wizard HEAD is already the rollback anchor."""
    before = int(_git(project, "rev-list", "--count", "HEAD").strip())
    pipeline = _ready(project)
    pipeline.apply_commit(pipeline.plan_commit())
    after = int(_git(project, "rev-list", "--count", "HEAD").strip())
    assert after == before + 1


def test_apply_commit_with_nothing_to_commit_raises(project: Path) -> None:
    """An empty commit would be tagged and pushed as a release that changed nothing."""
    pipeline = SharePipeline(project)
    pipeline.version = "0.3.2"
    plan = pipeline.plan_commit()
    with pytest.raises(CommitError):
        pipeline.apply_commit(plan)


def test_apply_commit_leaves_no_tag_when_the_commit_fails(project: Path) -> None:
    pipeline = SharePipeline(project)
    pipeline.version = "0.3.2"
    plan = pipeline.plan_commit()
    with pytest.raises(CommitError):
        pipeline.apply_commit(plan)
    tags = _git(project, "tag", "--list").split()
    assert "v0.3.2" not in tags


def test_apply_commit_message_with_shell_metacharacters_is_literal(project: Path) -> None:
    pipeline = _ready(project)
    nasty = 'chore: share v0.3.2 $(echo pwned) `whoami` && rm -rf /'
    plan = pipeline.plan_commit(message=nasty)
    pipeline.apply_commit(plan)
    assert _git(project, "log", "-1", "--format=%s").strip() == nasty


# ── verify_push_allowed ──────────────────────────────────────────────────────


def test_verify_push_allowed_passes_against_a_reachable_remote(project: Path) -> None:
    _ready(project).verify_push_allowed()  # must not raise


def test_verify_push_allowed_rejects_a_diverged_remote(project: Path, tmp_path: Path) -> None:
    """Closes the race window since step 1 — someone may have pushed meanwhile."""
    from haywire_studio.share_pipeline import PushError, gitcmd

    def _rejected(args, **_kw):
        if "--dry-run" in args:
            return gitcmd.GitResult(
                ok=False,
                stdout="",
                stderr="! [rejected] master -> master (fetch first)",
                returncode=1,
            )
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.git_remote", side_effect=_rejected):
        with pytest.raises(PushError) as excinfo:
            _ready(project).verify_push_allowed()

    assert "rejected" in excinfo.value.stderr
    assert excinfo.value.manual_command


def test_current_branch_is_reported(project: Path) -> None:
    branch = SharePipeline(project).current_branch()
    assert branch in {"main", "master"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_commit_step.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'apply_marketstall'`

- [ ] **Step 3: Add the imports**

In `pipeline.py`:

```python
from haywire_studio.share import MarketstallWriteResult, write_marketstall
from haywire_studio.share_pipeline.errors import CommitError, PipelineStateError, PushError
from haywire_studio.share_pipeline.results import BarnDirtyFile, CommitPlan, CommitResult
```

- [ ] **Step 4: Add the step-5 methods**

Append to `SharePipeline`:

```python
    # ── Step 5: marketstall + commit + tag ───────────────────────────────────

    def apply_marketstall(
        self,
        *,
        ref: str | None = None,
        tag: str | None = None,
    ) -> MarketstallWriteResult:
        """Rebuild ``marketstall.toml`` from every ``barn/*`` library.

        Always a FULL rebuild: the feed's contract is "every haybale this repo
        offers", so rebuilding from disk is what keeps it true. A partial
        rebuild deletes the entries of libraries not in this run.

        Also rewrites the ``<!-- marketstall:share-url -->`` marker block in the
        root README and every ``barn/*/README.md``.
        """
        result = write_marketstall(self.repo_root, ref=ref, tag=tag)
        self._record(result.written)
        return result

    def barn_dirty_files(self) -> list[BarnDirtyFile]:
        """Uncommitted content under ``barn/`` that the pipeline did not write.

        Offered as opt-in extras in step 5. Uncommitted barn content is
        silently ABSENT for consumers (they install from a clone), which is the
        one working-tree state that corrupts a publish.

        Dirt outside ``barn/`` is deliberately not reported: it has no bearing
        on what consumers get, and mentioning it would train users to dismiss
        the warning that matters. Ignored files never appear —
        ``git status --porcelain`` excludes them by default, and staging one
        would fail anyway.
        """
        status = git(["status", "--porcelain", "--", "barn"], cwd=self.repo_root)
        if not status.ok:
            return []

        own = set(self.written)
        out: list[BarnDirtyFile] = []
        for line in status.stdout.splitlines():
            if len(line) < 4:
                continue
            code, path_part = line[:2], line[3:].strip()
            if " -> " in path_part:
                path_part = path_part.split(" -> ", 1)[1]
            path = self.repo_root / path_part.strip('"')
            if path in own:
                continue
            out.append(BarnDirtyFile(path=path, untracked=code == "??"))
        return sorted(out, key=lambda d: d.path)

    def plan_commit(self, *, message: str | None = None) -> CommitPlan:
        """Preview exactly what would be staged, committed, and tagged.

        The write set spans the repo — every ``barn/*/pyproject.toml``, the root
        ``uv.lock``, each library's OVERVIEW/QUICKREF/``docs/*.md`` (including
        deletions for renamed components) and README, the root
        ``marketstall.toml``, and the share-url marker block in the root README
        and every ``barn/*/README.md``. Showing it is the point: a user must be
        able to see why a sibling library's README is in their commit.
        """
        if self.version is None:
            raise PipelineStateError(
                "plan_commit() needs a version — run apply_bump() (step 3) first."
            )
        files = list(self.written)
        return CommitPlan(
            files=files,
            barn_dirty=self.barn_dirty_files(),
            message=message or f"chore: share v{self.version}",
            tag=f"v{self.version}",
            diffstat=self._diffstat(files),
        )

    def _diffstat(self, files: list[Path]) -> str:
        """``git diff --stat`` limited to *files*, including untracked ones.

        Untracked files have no diff to show, so they are appended as
        "(new file)" lines instead. Purely cosmetic — the commit stages from
        ``files``, never from this string, so a failed ``git diff`` degrades to
        an empty summary rather than an error. That also covers a repo with no
        commits yet, where ``HEAD`` does not resolve.
        """
        if not files:
            return ""
        rel = [str(p.relative_to(self.repo_root)) for p in files if p.is_relative_to(self.repo_root)]
        if not rel:
            return ""
        tracked_diff = git(["diff", "--stat", "HEAD", "--", *rel], cwd=self.repo_root)
        stdout = tracked_diff.stdout if tracked_diff.ok else ""
        lines = stdout.strip().splitlines() if stdout.strip() else []
        for path_str in rel:
            if path_str not in stdout:
                lines.append(f" {path_str} (new file)")
        return "\n".join(lines)

    def current_branch(self) -> str:
        """The current branch name, or ``"HEAD"`` when detached."""
        result = git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root)
        return result.stdout.strip() or "HEAD"

    def push_command(self) -> list[str]:
        """The push argv, also shown verbatim in error panels for manual retry."""
        tag = f"v{self.version}" if self.version else ""
        args = ["push", "origin", f"HEAD:{self.current_branch()}"]
        if tag:
            args.append(tag)
        return args

    def verify_push_allowed(self) -> None:
        """``git push --dry-run`` — verify the remote will accept this push.

        Run immediately BEFORE the commit, closing the race window opened at
        step 1: someone else may have pushed meanwhile, and discovering that
        after a commit and tag exist means the user has to clean up.

        Mirrors the marketplace's ``dry_run()`` → ``install()`` pairing
        (library_manager.py:273): pre-flight verification over post-failure
        recovery, because nothing needs undoing if nothing was mutated.
        """
        branch = self.current_branch()
        probe = git_remote(
            ["push", "--dry-run", "origin", f"HEAD:{branch}"],
            cwd=self.repo_root,
            timeout=120.0,
        )
        if not probe.ok:
            raise PushError(
                stderr=(probe.stderr or probe.stdout).strip(),
                manual_command="git " + " ".join(self.push_command()),
            )

    def apply_commit(
        self,
        plan: CommitPlan,
        *,
        include_barn: list[Path] | None = None,
    ) -> CommitResult:
        """Stage exactly ``plan.files`` plus ``include_barn``, commit, then tag.

        Never ``-a``/``-A``. Staging is an explicit path list so a user's
        unrelated work-in-progress cannot land in a wizard-authored commit.
        There is no checkpoint commit either: the pre-wizard ``HEAD`` is already
        the rollback anchor, and the wizard authors exactly one commit.

        The tag is created only after the commit succeeds — a tag on the wrong
        commit is worse than no tag.
        """
        to_stage = [*plan.files, *(include_barn or [])]
        if not to_stage:
            raise CommitError("Nothing to commit — no files were written.")

        rel = [
            str(p.relative_to(self.repo_root)) if p.is_relative_to(self.repo_root) else str(p)
            for p in to_stage
        ]
        # `git add -A -- <paths>` stages deletions as well as modifications
        # within the given paths only; without -A a deleted file is skipped and
        # the stale version ships. The paths keep the scope explicit.
        staged = git(["add", "-A", "--", *rel], cwd=self.repo_root)
        if not staged.ok:
            raise CommitError(f"Could not stage files: {staged.stderr.strip()}", stderr=staged.stderr)

        # -m takes the message as an argv element, so shell metacharacters in a
        # user-supplied message are literal text.
        commit = git(["commit", "-m", plan.message], cwd=self.repo_root, timeout=60.0)
        if not commit.ok:
            raise CommitError(
                f"Commit failed: {(commit.stderr or commit.stdout).strip()}",
                stderr=commit.stderr or commit.stdout,
            )

        sha = git(["rev-parse", "HEAD"], cwd=self.repo_root).stdout.strip()

        tagged = git(["tag", plan.tag], cwd=self.repo_root)
        if not tagged.ok:
            raise CommitError(
                f"Committed {sha[:8]} but could not create tag {plan.tag}: {tagged.stderr.strip()}\n"
                f"Create it yourself with: git tag {plan.tag}",
                stderr=tagged.stderr,
            )

        return CommitResult(sha=sha, tag=plan.tag, files=to_stage)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_commit_step.py -v`
Expected: 21 passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py tests/share_pipeline/test_commit_step.py
git commit -m "feat(share): step 5 — marketstall rebuild, scoped commit, tag"
```

---

### Task 11: Step 6 — push

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_push_step.py`

**Interfaces:**
- Consumes: `git_remote_streaming` (Task 1); `PushResult`, `PushError` (Task 2); `push_command`, `current_branch` (Task 10).
- Produces: `async SharePipeline.apply_push(on_output: Callable[[str], None] | None = None) -> PushResult`

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_push_step.py`:

```python
"""Step 6 — pushing the commit and tag to origin."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.share_pipeline import PipelineStateError, PushError
from haywire_studio.share_pipeline.pipeline import SharePipeline

pytestmark = pytest.mark.unit


@pytest.fixture
def pushable(tmp_path: Path) -> Path:
    """A repo with a bare origin, one commit, and a v0.3.2 tag ready to push."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("a\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "tag", "v0.3.2"], cwd=repo, check=True, capture_output=True)
    return repo


def _ready(repo: Path) -> SharePipeline:
    pipeline = SharePipeline(repo)
    pipeline.version = "0.3.2"
    return pipeline


@pytest.mark.anyio
async def test_push_sends_commit_and_tag(pushable: Path, tmp_path: Path) -> None:
    result = await _ready(pushable).apply_push()

    remote = tmp_path / "remote.git"
    tags = subprocess.run(
        ["git", "tag", "--list"], cwd=remote, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "v0.3.2" in tags
    assert result.tag == "v0.3.2"
    assert result.remote == "origin"
    assert result.branch in {"main", "master"}


@pytest.mark.anyio
async def test_push_streams_output(pushable: Path) -> None:
    lines: list[str] = []
    await _ready(pushable).apply_push(on_output=lines.append)
    assert lines  # git writes transfer progress to the merged stream


@pytest.mark.anyio
async def test_push_uses_the_hardened_env(pushable: Path) -> None:
    """A missing credential must be a clean error, not an indefinite hang —
    there is no TTY behind a NiceGUI event handler."""
    from haywire_studio.share_pipeline import gitcmd

    seen: dict = {}

    async def _capture(args, *, cwd, on_output, timeout=None):
        seen["args"] = args
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch(
        "haywire_studio.share_pipeline.pipeline.git_remote_streaming",
        side_effect=_capture,
    ):
        await _ready(pushable).apply_push()

    # apply_push must route through git_remote_streaming (which applies the
    # hardened env), never through a bare create_subprocess_exec.
    assert seen["args"][0] == "push"


@pytest.mark.anyio
async def test_push_failure_raises_with_the_manual_command(pushable: Path) -> None:
    from haywire_studio.share_pipeline import gitcmd

    async def _fail(args, *, cwd, on_output, timeout=None):
        on_output("remote: Permission denied")
        return gitcmd.GitResult(ok=False, stdout="denied", stderr="denied", returncode=128)

    with patch(
        "haywire_studio.share_pipeline.pipeline.git_remote_streaming",
        side_effect=_fail,
    ):
        with pytest.raises(PushError) as excinfo:
            await _ready(pushable).apply_push()

    assert "push origin" in excinfo.value.manual_command
    assert "v0.3.2" in excinfo.value.manual_command


@pytest.mark.anyio
async def test_push_is_retryable_in_place(pushable: Path) -> None:
    """A transient network failure must not poison the pipeline — the same step
    can be run again without re-running earlier steps."""
    from haywire_studio.share_pipeline import gitcmd

    calls = {"n": 0}

    async def _flaky(args, *, cwd, on_output, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return gitcmd.GitResult(ok=False, stdout="", stderr="timed out", returncode=128)
        return gitcmd.GitResult(ok=True, stdout="ok", stderr="", returncode=0)

    pipeline = _ready(pushable)
    with patch(
        "haywire_studio.share_pipeline.pipeline.git_remote_streaming",
        side_effect=_flaky,
    ):
        with pytest.raises(PushError):
            await pipeline.apply_push()
        result = await pipeline.apply_push()

    assert result.tag == "v0.3.2"


@pytest.mark.anyio
async def test_push_without_a_version_raises(pushable: Path) -> None:
    with pytest.raises(PipelineStateError):
        await SharePipeline(pushable).apply_push()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_push_step.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'apply_push'`

- [ ] **Step 3: Write the implementation**

In `pipeline.py`, add `git_remote_streaming` to the `gitcmd` imports and `PushResult` to the `results` imports, then append to `SharePipeline`:

```python
    # ── Step 6: push ─────────────────────────────────────────────────────────

    async def apply_push(self, on_output: Callable[[str], None] | None = None) -> PushResult:
        """Push the commit and tag to ``origin``, for all callers.

        Env-hardened via :func:`git_remote_streaming`, so a missing credential
        becomes a clean error rather than an indefinite hang with no TTY. On
        failure the raised :class:`PushError` carries the exact command to run
        by hand, and the step is retryable in place — nothing here mutates
        pipeline state.
        """
        if self.version is None:
            raise PipelineStateError("apply_push() needs a version — run apply_bump() (step 3) first.")

        sink = on_output or (lambda _line: None)
        branch = self.current_branch()
        args = self.push_command()

        result = await git_remote_streaming(
            args,
            cwd=self.repo_root,
            on_output=sink,
            timeout=600.0,
        )
        if not result.ok:
            raise PushError(
                stderr=(result.stderr or result.stdout).strip(),
                manual_command="git " + " ".join(args),
            )
        return PushResult(
            remote="origin",
            branch=branch,
            tag=f"v{self.version}",
            output=result.stdout,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_push_step.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py tests/share_pipeline/test_push_step.py
git commit -m "feat(share): step 6 — env-hardened streamed push"
```

---

### Task 12: `plan()` — the read-only verifier

`plan()` is `--check`'s whole implementation and the wizard's summary panel. It must write nothing, which for docs and marketstall means generating into a throwaway copy and diffing.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py`
- Test: `tests/share_pipeline/test_plan.py`

**Interfaces:**
- Consumes: every check method from Tasks 4–10; `SharePlan` (Task 2).
- Produces:
  - `async SharePipeline.plan(on_output: Callable[[str], None] | None = None) -> SharePlan`
  - `SharePipeline.marketstall_is_stale() -> bool` — rebuilds the feed in memory and compares against the committed file.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_plan.py`:

```python
"""plan() — the read-only verifier behind `haywire share --check`."""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from haywire_studio.share_pipeline.pipeline import SharePipeline
from haywire_studio.share_pipeline.results import DriftReport

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def _no_drift(lib_dir: Path):
    from haywire_studio.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


@pytest.mark.anyio
async def test_plan_mutates_nothing(project: Path) -> None:
    """--check is a PR gate: it writes nothing, commits nothing, pushes nothing."""
    before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await SharePipeline(project).plan()

    after = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    head_after = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    assert after == before
    assert head_after == head_before


@pytest.mark.anyio
async def test_plan_reports_preconditions_and_versions(project: Path) -> None:
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        plan = await SharePipeline(project).plan()

    assert plan.preconditions.ok is True
    assert plan.versions.common_version == "0.3.1"


@pytest.mark.anyio
async def test_plan_flags_a_missing_marketstall_as_stale(project: Path) -> None:
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        plan = await SharePipeline(project).plan()

    assert plan.stale_marketstall is True
    assert plan.is_clean is False


@pytest.mark.anyio
async def test_plan_is_clean_when_the_marketstall_matches(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "feed"], cwd=project, check=True, capture_output=True)

    pipeline = SharePipeline(project)
    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        patch.object(SharePipeline, "_stale_docs", return_value=[]),
    ):
        plan = await pipeline.plan()

    assert plan.stale_marketstall is False
    assert plan.is_clean is True


@pytest.mark.anyio
async def test_plan_flags_drift(project: Path) -> None:
    from haywire_studio.share import DepDrift

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        plan = await SharePipeline(project).plan()

    assert plan.drift.needs_decision is True
    assert plan.is_clean is False


def test_marketstall_is_stale_when_content_differs(project: Path) -> None:
    (project / "marketstall.toml").write_text("# stale hand-edit\n[[haybales]]\nname = 'gone'\n")
    assert SharePipeline(project).marketstall_is_stale() is True


def test_marketstall_is_not_stale_when_it_matches(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    assert SharePipeline(project).marketstall_is_stale() is False


def test_marketstall_stale_check_leaves_the_file_untouched(project: Path) -> None:
    from haywire_studio.share import write_marketstall

    write_marketstall(project, update_readme=False)
    before = (project / "marketstall.toml").read_text()
    SharePipeline(project).marketstall_is_stale()
    assert (project / "marketstall.toml").read_text() == before


@pytest.mark.anyio
async def test_plan_skips_the_rest_when_preconditions_fail(tmp_path: Path) -> None:
    """No point diffing docs for a repo that cannot be published at all."""
    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    plan = await SharePipeline(repo).plan()

    assert plan.preconditions.ok is False
    assert plan.stale_docs == []
    assert plan.is_clean is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_plan.py -v`
Expected: FAIL — `AttributeError: 'SharePipeline' object has no attribute 'plan'`

- [ ] **Step 3: Write the implementation**

In `pipeline.py`, add `from haywire_studio.share import build_marketstall_entries` and `_MARKETSTALL_HEADER` to the `share` imports, `SharePlan` to the `results` imports, and `import toml` at the top. Then append to `SharePipeline`:

```python
    # ── plan(): the read-only verifier ───────────────────────────────────────

    async def plan(self, on_output: Callable[[str], None] | None = None) -> SharePlan:
        """Everything determinable without mutating anything.

        Backs ``haywire share --check`` (a PR gate: writes nothing, commits
        nothing, pushes nothing, exits non-zero when anything is stale) and the
        wizard's summary panel. The plan/apply split is load-bearing beyond CI:
        step 5's file-list preview IS a plan.
        """
        preconditions = self.check_preconditions()
        if not preconditions.ok:
            # Diffing docs against an unpublishable repo answers a question
            # nobody asked; the failures are the whole story.
            return SharePlan(
                preconditions=preconditions,
                drift=DriftReport(drifted=[], unresolved_only=[]),
                versions=self.plan_version(),
            )

        return SharePlan(
            preconditions=preconditions,
            drift=self.check_drift(),
            versions=self.plan_version(),
            stale_docs=await self._stale_docs(on_output=on_output),
            stale_marketstall=self.marketstall_is_stale(),
        )

    def marketstall_is_stale(self) -> bool:
        """True when a full rebuild would differ from the file on disk.

        Rebuilt in memory and compared — the check must not write, or
        ``--check`` would fail its own contract.
        """
        out_path = self.repo_root / "marketstall.toml"
        try:
            entries = build_marketstall_entries(self.repo_root)
        except NoBarnError:
            return False
        expected = _MARKETSTALL_HEADER + toml.dumps({"haybales": entries})
        if not out_path.is_file():
            return True
        return out_path.read_text() != expected

    async def _stale_docs(self, *, on_output: Callable[[str], None] | None = None) -> list[Path]:
        """Doc files that a regeneration would change, without changing them.

        Generation writes in place, so the only honest way to ask "would this
        change anything?" is to generate and then restore. ``git stash`` is off
        limits (destructive, and it would sweep the user's unrelated work), so
        the doc files' contents are snapshotted and rewritten afterwards.

        Returns the paths that differed. Deliberately conservative: if the
        generation itself fails, the caller sees the exception, not a silent
        "nothing stale".
        """
        snapshot: dict[Path, bytes | None] = {}
        for lib_dir in self._barn_library_dirs():
            for path in lib_dir.rglob("*.md"):
                snapshot[path] = path.read_bytes()

        await self.apply_docs(on_output=on_output)

        changed: list[Path] = []
        current: set[Path] = set()
        for lib_dir in self._barn_library_dirs():
            current.update(lib_dir.rglob("*.md"))

        for path in sorted(current | set(snapshot)):
            old = snapshot.get(path)
            new = path.read_bytes() if path.is_file() else None
            if old != new:
                changed.append(path)

        # Restore: rewrite what we snapshotted, delete what generation added,
        # recreate what generation deleted. The working tree must end where it
        # started — this is a read-only call.
        for path in sorted(current - set(snapshot)):
            path.unlink(missing_ok=True)
        for path, content in snapshot.items():
            if content is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

        # apply_docs() recorded its writes; a read-only call must not leave them
        # in the accumulated set.
        self.written = [p for p in self.written if p not in set(changed)]
        return changed
```

Add `NoBarnError` to the `haywire_studio.share` imports in `pipeline.py`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_plan.py -v`
Expected: 9 passed.

- [ ] **Step 5: Run the whole pipeline suite**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: all passed.

- [ ] **Step 6: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run ruff format packages/haywire-studio/src/haywire_studio/share_pipeline/ tests/share_pipeline/
uv run mypy packages/haywire-studio/src/haywire_studio/share_pipeline/
```

```bash
git add packages/haywire-studio/src/haywire_studio/share_pipeline/pipeline.py tests/share_pipeline/test_plan.py
git commit -m "feat(share): plan() — the non-mutating verifier behind --check"
```

---

### Task 13: `haywire share` CLI rewrite

Replaces today's flag-driven shape with three modes over `SharePipeline`. This is a full rewrite of the CLI-shaped functions, not an additive layer — `share.py` has 10 `sys.exit` sites and 44 print/exit calls clustered in `share_library`, `bump_version`, and `_detect_library`, all of which go.

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/share_cli.py`
- Modify: `packages/haywire-studio/src/haywire_studio/app.py:359-414` (parser), `:450-503` (dispatch)
- Modify: `packages/haywire-studio/src/haywire_studio/share.py` (delete `bump_version`, `share_library`, `_detect_library`, `_run_drift_gate`, `share_save_repo`, `_format_drift_report` if unused, `ShareSaveResult` if unused)
- Modify: `tests/test_share_bump_keyword.py`, `tests/test_share_save.py`
- Test: `tests/test_share_cli.py`

**Interfaces:**
- Consumes: `SharePipeline` and every result/error type; `derive_share_url_only` (kept in `share.py`).
- Produces:
  - `run_share_cli(*, repo_root: Path, check: bool, yes: bool, bump: str | None, message: str | None, ref: str | None, tag: str | None) -> int` — the exit code. Never calls `sys.exit`.
  - CLI contract: `haywire share` (interactive), `haywire share --check`, `haywire share --yes --bump patch [--message M] [--ref R] [--tag T]`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_share_cli.py`:

```python
"""`haywire share` — the three modes over SharePipeline."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import toml

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Git repo, bare origin, one barn library at 0.3.1, one commit."""
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    (lib / "haybale_alpha" / "__init__.py").write_text(
        '@library(label="Alpha", id="alpha")\nclass Library: pass\n'
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=repo, check=True, capture_output=True)
    return repo


def _no_drift(lib_dir: Path):
    from haywire_studio.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


def _fake_docs():
    """Patch apply_docs so no real library system boots in a unit test."""
    from haywire_studio.share_pipeline.results import DocsResult

    return patch(
        "haywire_studio.share_pipeline.pipeline.SharePipeline.apply_docs",
        new=AsyncMock(return_value=DocsResult(coverage={}, written=[])),
    )


# ── --check ──────────────────────────────────────────────────────────────────


def test_check_exits_nonzero_when_stale(project: Path, capsys) -> None:
    from haywire_studio.share_cli import run_share_cli

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        patch(
            "haywire_studio.share_pipeline.pipeline.SharePipeline._stale_docs",
            new=AsyncMock(return_value=[project / "barn" / "haybale-alpha" / "OVERVIEW.md"]),
        ),
    ):
        code = run_share_cli(
            repo_root=project, check=True, yes=False, bump=None, message=None, ref=None, tag=None
        )

    assert code != 0
    out = capsys.readouterr().out
    assert "OVERVIEW.md" in out


def test_check_exits_zero_when_clean(project: Path) -> None:
    from haywire_studio.share import write_marketstall
    from haywire_studio.share_cli import run_share_cli

    write_marketstall(project, update_readme=False)

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        patch(
            "haywire_studio.share_pipeline.pipeline.SharePipeline._stale_docs",
            new=AsyncMock(return_value=[]),
        ),
    ):
        code = run_share_cli(
            repo_root=project, check=True, yes=False, bump=None, message=None, ref=None, tag=None
        )

    assert code == 0


def test_check_writes_nothing_and_commits_nothing(project: Path) -> None:
    """A PR gate must be side-effect free."""
    from haywire_studio.share_cli import run_share_cli

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout
    status_before = subprocess.run(
        ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
    ).stdout

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        patch(
            "haywire_studio.share_pipeline.pipeline.SharePipeline._stale_docs",
            new=AsyncMock(return_value=[]),
        ),
    ):
        run_share_cli(
            repo_root=project, check=True, yes=False, bump=None, message=None, ref=None, tag=None
        )

    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
        ).stdout
        == head_before
    )
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=project, capture_output=True, text=True, check=True
        ).stdout
        == status_before
    )


def test_check_reports_precondition_failures(tmp_path: Path, capsys) -> None:
    from haywire_studio.share_cli import run_share_cli

    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    code = run_share_cli(
        repo_root=repo, check=True, yes=False, bump=None, message=None, ref=None, tag=None
    )

    assert code != 0
    assert "barn" in capsys.readouterr().out


# ── --yes ────────────────────────────────────────────────────────────────────


def test_yes_runs_the_whole_pipeline(project: Path) -> None:
    from haywire_studio.share_cli import run_share_cli

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        code = run_share_cli(
            repo_root=project, check=False, yes=True, bump="patch", message=None, ref=None, tag=None
        )

    assert code == 0
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.2"

    tags = subprocess.run(
        ["git", "tag", "--list"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()
    assert "v0.3.2" in tags


def test_yes_uses_the_supplied_message(project: Path) -> None:
    from haywire_studio.share_cli import run_share_cli

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        run_share_cli(
            repo_root=project,
            check=False,
            yes=True,
            bump="patch",
            message="release: 0.3.2",
            ref=None,
            tag=None,
        )

    subject = subprocess.run(
        ["git", "log", "-1", "--format=%s"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert subject == "release: 0.3.2"


def test_yes_without_bump_fails_fast(project: Path, capsys) -> None:
    """Non-interactive means every answer comes from a flag — guessing a version is not ours to do."""
    from haywire_studio.share_cli import run_share_cli

    code = run_share_cli(
        repo_root=project, check=False, yes=True, bump=None, message=None, ref=None, tag=None
    )

    assert code != 0
    assert "--bump" in capsys.readouterr().out


def test_yes_stops_on_unresolved_drift(project: Path, capsys) -> None:
    """Replace can destructively remove declared deps — never a non-interactive default."""
    from haywire_studio.share import DepDrift
    from haywire_studio.share_cli import run_share_cli

    def _drifty(lib_dir: Path):
        return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        code = run_share_cli(
            repo_root=project, check=False, yes=True, bump="patch", message=None, ref=None, tag=None
        )

    assert code != 0
    out = capsys.readouterr().out
    assert "drift" in out.lower()


def test_yes_reports_a_tag_collision_without_mutating(project: Path, capsys) -> None:
    from haywire_studio.share_cli import run_share_cli

    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)

    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        code = run_share_cli(
            repo_root=project, check=False, yes=True, bump="patch", message=None, ref=None, tag=None
        )

    assert code != 0
    assert "v0.3.2" in capsys.readouterr().out
    path = project / "barn" / "haybale-alpha" / "pyproject.toml"
    assert toml.loads(path.read_text())["project"]["version"] == "0.3.1"


def test_yes_prints_the_share_url(project: Path, capsys) -> None:
    from haywire_studio.share_cli import run_share_cli

    with (
        patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift),
        _fake_docs(),
    ):
        run_share_cli(
            repo_root=project, check=False, yes=True, bump="patch", message=None, ref=None, tag=None
        )

    # The fixture's origin is a local path, so no host provider resolves and the
    # warning path is exercised instead of a URL. Either way the user is told.
    out = capsys.readouterr().out
    assert "marketstall.toml" in out


def test_precondition_failure_exits_before_any_write(tmp_path: Path) -> None:
    from haywire_studio.share_cli import run_share_cli

    repo = tmp_path / "noremote"
    lib = repo / "barn" / "haybale-alpha"
    lib.mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.1.0"\n')
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    code = run_share_cli(
        repo_root=repo, check=False, yes=True, bump="patch", message=None, ref=None, tag=None
    )

    assert code != 0
    assert toml.loads((lib / "pyproject.toml").read_text())["project"]["version"] == "0.1.0"


# ── argparse surface ─────────────────────────────────────────────────────────


def test_share_help_lists_the_three_modes() -> None:
    result = subprocess.run(
        ["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True
    )
    assert "--check" in result.stdout
    assert "--yes" in result.stdout
    assert "--bump" in result.stdout


def test_removed_flags_are_gone() -> None:
    """--save and --strict/--fix were the old shape; leaving them would imply
    behaviour the pipeline no longer has."""
    result = subprocess.run(
        ["uv", "run", "haywire", "share", "--help"], capture_output=True, text=True
    )
    assert "--save" not in result.stdout
    assert "--strict" not in result.stdout
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_share_cli.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'haywire_studio.share_cli'`

- [ ] **Step 3: Write `share_cli.py`**

Create `packages/haywire-studio/src/haywire_studio/share_cli.py`:

```python
"""``haywire share`` — a thin runner over :class:`SharePipeline`.

Three modes:

* **interactive** (default) — prompts through the same steps as the wizard.
* **``--check``** — read-only verifier for a PR gate. Reports everything stale
  and exits non-zero. Writes nothing, commits nothing, pushes nothing.
* **``--yes``** — non-interactive full run with flag-supplied answers, for
  tag-triggered release automation and for the test suite (testing a
  seven-step git-mutating pipeline through a prompt loop is otherwise
  miserable).

Returns exit codes; never calls ``sys.exit`` itself, so it stays testable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from haywire_studio.share import derive_share_url_only
from haywire_studio.share_pipeline import (
    ShareError,
    SharePipeline,
    SharePlan,
)

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_STALE = 2


def run_share_cli(
    *,
    repo_root: Path,
    check: bool,
    yes: bool,
    bump: str | None,
    message: str | None,
    ref: str | None,
    tag: str | None,
) -> int:
    """Dispatch to one of the three modes and return the process exit code."""
    pipeline = SharePipeline(repo_root)
    try:
        if check:
            return _run_check(pipeline, ref=ref, tag=tag)
        if yes:
            return _run_yes(pipeline, bump=bump, message=message, ref=ref, tag=tag)
        return _run_interactive(pipeline, ref=ref, tag=tag)
    except ShareError as exc:
        print(f"\n✗ {exc}")
        return EXIT_FAILED


# ── --check ──────────────────────────────────────────────────────────────────


def _run_check(pipeline: SharePipeline, *, ref: str | None, tag: str | None) -> int:
    """Report drift and staleness. Exits non-zero when anything needs doing."""
    plan = asyncio.run(pipeline.plan(on_output=lambda line: None))
    _print_plan(plan)
    return EXIT_OK if plan.is_clean else EXIT_STALE


def _print_plan(plan: SharePlan) -> None:
    if not plan.preconditions.ok:
        print("Cannot share this project:")
        for failure in plan.preconditions.failures:
            print(f"  - {failure}")
        return

    print(f"Current version: {plan.versions.common_version or '(libraries disagree)'}")
    for lib in plan.versions.current:
        print(f"  • {lib.name}: {lib.version or '(none)'}")

    if plan.drift.needs_decision:
        print("\nDependency drift (run `haywire share` to resolve):")
        for drift in plan.drift.drifted:
            for dep in drift.pyproject_missing:
                print(f"  + {drift.lib_dir.name} pyproject.toml: {dep}")
            for dep in drift.decorator_missing:
                print(f"  + {drift.lib_dir.name} @library(dependencies): {dep}")
            for dist, declared, installed in drift.pyproject_version_lag:
                print(f"  ~ {drift.lib_dir.name} {dist}: declared {declared}, installed {installed}")

    if plan.stale_docs:
        print("\nStale generated docs:")
        for path in plan.stale_docs:
            print(f"  ~ {path}")

    if plan.stale_marketstall:
        print("\nmarketstall.toml is stale or missing.")

    print("\n✓ Everything is up to date." if plan.is_clean else "\n✗ Run `haywire share` to update.")


# ── --yes ────────────────────────────────────────────────────────────────────


def _run_yes(
    pipeline: SharePipeline,
    *,
    bump: str | None,
    message: str | None,
    ref: str | None,
    tag: str | None,
) -> int:
    """Full non-interactive run. Every decision must arrive as a flag."""
    if not bump:
        print("--yes requires --bump (patch|minor|major|X.Y.Z): a non-interactive run")
        print("cannot guess which version you meant to publish.")
        return EXIT_FAILED

    pipeline.require_preconditions()
    print("✓ Preconditions OK")

    drift = pipeline.check_drift()
    if drift.needs_decision:
        # Union is additive and safe, but Replace destructively removes declared
        # deps — that decision is never made on the user's behalf.
        print("✗ Dependency drift found. Resolve it interactively with `haywire share`:")
        for d in drift.drifted:
            print(f"  - {d.lib_dir.name}")
        return EXIT_FAILED
    print("✓ No dependency drift")

    bump_result = pipeline.apply_bump(bump)
    print(f"✓ Bumped every barn library to {bump_result.version}")
    if bump_result.lock_warning:
        print(f"⚠ {bump_result.lock_warning}")

    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    gaps = docs.total_gaps
    print(f"✓ Regenerated docs ({gaps} coverage gap(s))")

    stall = pipeline.apply_marketstall(ref=ref, tag=tag)
    print(f"✓ Wrote {stall.out_path}")
    if stall.warning:
        print(f"⚠ {stall.warning}")

    pipeline.verify_push_allowed()
    print("✓ Remote will accept the push")

    plan = pipeline.plan_commit(message=message)
    result = pipeline.apply_commit(plan)
    print(f"✓ Committed {result.sha[:8]} and tagged {result.tag}")

    push = asyncio.run(pipeline.apply_push(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Pushed to {push.remote} ({push.branch}, {push.tag})")

    url = derive_share_url_only(pipeline.repo_root, ref=ref, tag=tag)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    return EXIT_OK


# ── interactive ──────────────────────────────────────────────────────────────


def _ask(prompt: str, *, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or default


def _confirm(prompt: str) -> bool:
    return _ask(f"{prompt} (y/N)", default="n").lower().startswith("y")


def _run_interactive(pipeline: SharePipeline, *, ref: str | None, tag: str | None) -> int:
    """Prompt through the same six steps the wizard walks."""
    print("── 1. Preconditions ──")
    pipeline.require_preconditions()
    print("✓ git, barn/, and origin all OK")

    print("\n── 2. Dependency drift ──")
    drift = pipeline.check_drift()
    if drift.needs_decision:
        for d in drift.drifted:
            print(f"  {d.lib_dir.name}:")
            for dep in d.pyproject_missing:
                print(f"    + pyproject.toml: {dep}")
            for dep in d.decorator_missing:
                print(f"    + @library(dependencies): {dep}")
        choice = _ask("Union (add missing) / Replace (overwrite) / Skip", default="Union").lower()
        if choice.startswith("u"):
            pipeline.apply_drift_union(drift)
            print("✓ Merged detected dependencies")
        elif choice.startswith("r"):
            print("Replace removes declarations the source no longer imports.")
            if not _confirm("Really replace?"):
                return EXIT_FAILED
            pipeline.apply_drift_replace(drift)
            print("✓ Replaced declared dependencies")
        else:
            pipeline.acknowledge_drift()
            print("⚠ Continuing with unresolved drift")
    else:
        print("✓ No drift")

    print("\n── 3. Version ──")
    version_plan = pipeline.plan_version()
    for lib in version_plan.current:
        print(f"  {lib.name}: {lib.version or '(none)'}")
    if version_plan.versions_agree:
        for keyword, resolved in version_plan.suggestions.items():
            print(f"  {keyword}: {resolved}")
        spec = _ask("Bump (patch|minor|major|X.Y.Z)", default="patch")
    else:
        print("⚠ Versions disagree — every barn library will be set to the version you name.")
        spec = _ask("Target version (X.Y.Z)")
    bump_result = pipeline.apply_bump(spec)
    print(f"✓ All barn libraries now {bump_result.version}")
    if bump_result.lock_warning:
        print(f"⚠ {bump_result.lock_warning}")

    print("\n── 4. Docs ──")
    docs = asyncio.run(pipeline.apply_docs(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Docs regenerated ({docs.total_gaps} coverage gap(s))")

    print("\n── 5. Marketstall, commit, tag ──")
    stall = pipeline.apply_marketstall(ref=ref, tag=tag)
    print(f"✓ Wrote {stall.out_path}")
    if stall.warning:
        print(f"⚠ {stall.warning}")

    plan = pipeline.plan_commit()
    print("\nFiles to commit:")
    for path in plan.files:
        print(f"  {path.relative_to(pipeline.repo_root)}")

    include_barn: list[Path] = []
    if plan.barn_dirty:
        print("\nUncommitted content under barn/ — consumers install from a clone,")
        print("so anything left out is silently MISSING for them:")
        for entry in plan.barn_dirty:
            marker = "new" if entry.untracked else "modified"
            print(f"  ({marker}) {entry.path.relative_to(pipeline.repo_root)}")
        if _confirm("Include these in this commit?"):
            include_barn = [entry.path for entry in plan.barn_dirty]

    message = _ask("Commit message", default=plan.message)
    plan = pipeline.plan_commit(message=message)

    pipeline.verify_push_allowed()
    print("✓ Remote will accept the push")

    if not _confirm(f"Commit and tag {plan.tag}?"):
        print("Aborted before committing. Nothing was committed or tagged.")
        return EXIT_FAILED

    result = pipeline.apply_commit(plan, include_barn=include_barn)
    print(f"✓ Committed {result.sha[:8]} and tagged {result.tag}")

    print("\n── 6. Push ──")
    if not _confirm(f"Push {result.tag} to origin?"):
        print(f"Not pushed. Run this when ready:\n  git {' '.join(pipeline.push_command())}")
        return EXIT_OK

    push = asyncio.run(pipeline.apply_push(on_output=lambda line: print(f"  {line}")))
    print(f"✓ Pushed to {push.remote} ({push.branch}, {push.tag})")

    url = derive_share_url_only(pipeline.repo_root, ref=ref, tag=tag)
    if url.share_url:
        print(f"\n✓ Share this URL:\n  {url.share_url}")
    elif url.warning:
        print(f"\n⚠ {url.warning}")
    return EXIT_OK
```

- [ ] **Step 4: Replace the argparse surface**

In `packages/haywire-studio/src/haywire_studio/app.py`, replace the whole `share_parser` block (lines 359-414) with:

```python
    share_parser = subparsers.add_parser(
        "share",
        help="Publish this project: bump every barn library, regenerate docs, "
        "rebuild marketstall.toml, commit, tag, and push",
    )
    share_parser.add_argument(
        "--check",
        action="store_true",
        help="Read-only verifier: report drift and stale docs/marketstall, then exit "
        "non-zero. Writes nothing, commits nothing, pushes nothing.",
    )
    share_parser.add_argument(
        "--yes",
        action="store_true",
        help="Non-interactive full run using flag-supplied answers. Requires --bump.",
    )
    share_parser.add_argument(
        "--bump",
        type=str,
        default=None,
        metavar="VERSION",
        help="Version to publish: patch|minor|major, or an explicit X.Y.Z. Every "
        "barn/* library is set to it (lockstep).",
    )
    share_parser.add_argument(
        "--message",
        type=str,
        default=None,
        help="Commit message. Defaults to 'chore: share v<version>'.",
    )
    share_parser.add_argument(
        "--ref",
        type=str,
        default=None,
        help="Specific ref (branch, tag, or SHA) to encode in the share URL.",
    )
    share_parser.add_argument(
        "--tag",
        type=str,
        default=None,
        help="Tag to encode in the share URL. Use 'latest' to resolve to the most "
        "recent tag reachable from HEAD. The default stays branch-live: "
        "marketstall.toml is a subscription feed, so a branch-pinned URL keeps "
        "subscribers discovering every future release.",
    )
```

Delete the `_BUMP_ABSENT` sentinel and its definition if it is now unused (`grep -n "_BUMP_ABSENT" packages/haywire-studio/src/haywire_studio/app.py`).

- [ ] **Step 5: Replace the dispatch branch**

Replace the whole `elif args.command == "share":` block (lines 450-503) with:

```python
    elif args.command == "share":
        from haywire_studio.share_cli import run_share_cli

        raise SystemExit(
            run_share_cli(
                repo_root=Path.cwd(),
                check=args.check,
                yes=args.yes,
                bump=args.bump,
                message=args.message,
                ref=args.ref,
                tag=args.tag,
            )
        )
```

- [ ] **Step 6: Delete the superseded functions from `share.py`**

Before deleting, confirm nothing else calls them:

```sh
grep -rn "bump_version\|share_library\|_detect_library\|_run_drift_gate\|share_save_repo" \
  --include="*.py" packages barn tests
```

Then delete from `packages/haywire-studio/src/haywire_studio/share.py`:
- `_detect_library` (lines 236-264)
- `share_library` (683-725)
- `_run_drift_gate` (728-754)
- `share_save_repo` (869-949)
- `bump_version` (1010-1134)
- `_read_version`, `_write_version`, `_compute_next_version`, `_BUMP_KEYWORDS` — superseded by `versions.py`
- `ShareSaveResult` — only if `_derive_url`/`derive_share_url_only` no longer need it; they do, so KEEP it.

Keep: `_build_entry_for_library`, `detect_share_drift`, `apply_drift_fix`, `union_pyproject_deps`, `_derive_url`, `derive_share_url_only`, `build_marketstall_entries`, `write_marketstall`, `_update_repo_readmes`, `_format_drift_report`, `DepDrift`, `DriftError`, `NoBarnError`, `InvalidOsDeclarationError`, `ShareSaveResult`, `MarketstallWriteResult`, and every private helper they use.

Also drop the now-unused `import sys` if nothing else in the file uses it.

- [ ] **Step 7: Update the superseded tests**

Rewrite `tests/test_share_bump_keyword.py` to target `versions.py`. The version-arithmetic cases already exist in `tests/share_pipeline/test_versions.py`, so delete the file:

```bash
git rm tests/test_share_bump_keyword.py
```

In `tests/test_share_save.py`, replace every `share_save_repo(...)` call with `write_marketstall(...)` and every `ShareSaveResult` assertion with the `MarketstallWriteResult` equivalent (`result.out_path`, `result.share_url`, `result.warning`). Tests asserting on the drift gate's warn/strict/fix behaviour inside `share_save_repo` no longer have a subject — the gate is step 2 now, covered by `tests/share_pipeline/test_drift_step.py`. Delete those specific tests and keep the aggregation/URL/README ones.

- [ ] **Step 8: Run the full share test surface**

Run:
```sh
uv run pytest tests/test_share_cli.py tests/test_share_save.py tests/test_share_drift.py \
  tests/test_share_os_field.py tests/test_share_readme_markers.py \
  tests/test_share_url_derivation.py tests/test_share_marketstall_write.py \
  tests/share_pipeline/ -v
```
Expected: all passed.

- [ ] **Step 9: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/ tests/
uv run ruff format packages/haywire-studio/src/ tests/
uv run mypy packages/haywire-studio/src/
```

```bash
git add -A packages/haywire-studio/src/haywire_studio/ tests/
git commit -m "feat(share): rewrite haywire share as a SharePipeline runner (--check/--yes)"
```

---

### Task 14: `haywire init` scaffolding fixes

Two independent scaffold bugs, both about what consumers receive from a clone. Ships as one task because both live in the same function neighbourhood and the same test file.

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/init.py:183-217` (`_generate_gitignore`), plus a new `_generate_gitattributes` and its call site near line 566
- Test: `tests/test_init_scaffold_git_files.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `_generate_gitattributes() -> str`; `_generate_gitignore()` returns anchored patterns.

- [ ] **Step 1: Write the failing test**

Create `tests/test_init_scaffold_git_files.py`:

```python
"""`haywire init` scaffolds .gitignore and .gitattributes that don't corrupt a publish."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.init import _generate_gitattributes, _generate_gitignore

pytestmark = pytest.mark.unit


# ── .gitignore anchoring ─────────────────────────────────────────────────────


@pytest.mark.parametrize("pattern", ["/build/", "/dist/", "/env/", "/venv/", "/.venv/"])
def test_root_only_patterns_are_anchored(pattern: str) -> None:
    """An unanchored pattern matches at EVERY depth — including inside
    barn/<lib>/<module>/, where it silently excludes library content.
    Ignored ⇒ never committed ⇒ absent from the clone consumers install from."""
    assert pattern in _generate_gitignore()


@pytest.mark.parametrize("pattern", ["\nbuild/", "\ndist/", "\nenv/", "\nvenv/", "\n.venv/"])
def test_unanchored_variants_are_gone(pattern: str) -> None:
    assert pattern not in _generate_gitignore()


def test_depth_matching_patterns_are_kept_unanchored() -> None:
    """These SHOULD match at every depth — they're correctly ignored everywhere."""
    content = _generate_gitignore()
    assert "__pycache__/" in content
    assert "*.egg-info/" in content


def test_gitignore_explains_the_anchoring_rule() -> None:
    """The person about to edit the file is the one who needs the knowledge."""
    content = _generate_gitignore()
    assert "anchored" in content.lower()
    assert "barn/" in content


def test_gitignore_warns_before_adding_patterns() -> None:
    content = _generate_gitignore()
    assert "MISSING" in content or "missing" in content
    assert "clone" in content


def test_gitignore_still_ignores_workspace_state() -> None:
    assert ".haywire/workspace_state.json" in _generate_gitignore()


def test_anchored_patterns_do_not_ignore_barn_content(tmp_path: Path) -> None:
    """The real check: git itself must not ignore a library's build/ directory."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text(_generate_gitignore())

    asset = repo / "barn" / "haybale-alpha" / "haybale_alpha" / "build" / "shader.glsl"
    asset.parent.mkdir(parents=True)
    asset.write_text("// shader\n")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(asset.relative_to(repo))],
        cwd=repo,
        capture_output=True,
    )
    assert ignored.returncode != 0, "barn library content must not be gitignored"


def test_root_build_dir_is_still_ignored(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    (repo / ".gitignore").write_text(_generate_gitignore())
    (repo / "build").mkdir()
    (repo / "build" / "out.txt").write_text("x\n")

    ignored = subprocess.run(
        ["git", "check-ignore", "-q", "build/out.txt"], cwd=repo, capture_output=True
    )
    assert ignored.returncode == 0


# ── .gitattributes ───────────────────────────────────────────────────────────


def test_gitattributes_normalizes_text_eol() -> None:
    assert "* text=auto" in _generate_gitattributes()


def test_gitattributes_arms_no_lfs_filter() -> None:
    """git stores a ~130-byte pointer; a consumer without git-lfs receives THAT
    instead of the asset. The install succeeds and the library breaks at runtime,
    and *.png is exactly what a node library's icons and skins match."""
    content = _generate_gitattributes()
    assert "filter=lfs" not in content
    assert "lfs install" not in content


def test_gitattributes_documents_the_lfs_tradeoff() -> None:
    """Don't arm the trap; document it where the decision gets made."""
    content = _generate_gitattributes().lower()
    assert "lfs" in content
    assert "pointer" in content


def test_gitattributes_marks_binary_assets_as_binary() -> None:
    content = _generate_gitattributes()
    assert "*.png" in content
    assert "binary" in content


# ── scaffold wiring ──────────────────────────────────────────────────────────


def test_init_writes_both_files(tmp_path: Path, monkeypatch) -> None:
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("myproj", auto_sync=False)

    project = tmp_path / "myproj"
    assert (project / ".gitignore").read_text() == _generate_gitignore()
    assert (project / ".gitattributes").read_text() == _generate_gitattributes()


def test_scaffolded_project_commits_its_gitattributes(tmp_path: Path, monkeypatch) -> None:
    """It must be in the initial commit, or a consumer's clone applies no
    normalization at all."""
    from haywire_studio.init import init_project

    monkeypatch.chdir(tmp_path)
    init_project("myproj2", auto_sync=False)

    project = tmp_path / "myproj2"
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=project, capture_output=True, text=True, check=True
    ).stdout.split()
    assert ".gitattributes" in tracked
    assert ".gitignore" in tracked
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_init_scaffold_git_files.py -v`
Expected: FAIL — `ImportError: cannot import name '_generate_gitattributes'`

- [ ] **Step 3: Rewrite `_generate_gitignore`**

Replace `_generate_gitignore` in `packages/haywire-studio/src/haywire_studio/init.py` (lines 183-217) with:

```python
def _generate_gitignore() -> str:
    """Generate a default .gitignore for a scaffolded haywire project.

    Root-only patterns are ANCHORED with a leading slash. An unanchored pattern
    matches at every depth, including inside ``barn/<lib>/<module>/``, and since
    consumers install from a clone, anything ignored there is absent for
    everyone. See ``.insights/project_git_url_publishing_traps.md``.
    """
    return """\
# Patterns below are anchored with a leading slash (/build/) so they match only
# at the repo root. An unanchored pattern (build/) matches at EVERY depth —
# including inside barn/, where it would silently exclude your library's own
# files. See the note at the end of this file before adding patterns.

# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Distribution / packaging (root only)
/build/
/dist/
*.egg-info/
*.egg

# Virtual environments (root only)
/.venv/
/venv/
/env/

# Test / type-check caches
.pytest_cache/
.ruff_cache/
.mypy_cache/
.tox/
.coverage
htmlcov/

# Editor / OS
.DS_Store
.idea/
.vscode/

# Haywire per-session UI state (open graph, pan/zoom) — not project state
.haywire/workspace_state.json

# ── Before you add a pattern ────────────────────────────────────────────────
# Anything ignored inside barn/<your-library>/ will be MISSING for everyone who
# installs your library — haywire share publishes by git URL, so consumers get
# a clone of this repo, not a built package. If a pattern is only meant for the
# repo root, anchor it with a leading slash: /build/ not build/.
"""
```

- [ ] **Step 4: Add `_generate_gitattributes`**

Add immediately after `_generate_gitignore`:

```python
def _generate_gitattributes() -> str:
    """Generate a default .gitattributes: text normalization, and NO LFS.

    LFS is deliberately not armed. git stores a ~130-byte pointer file, and a
    consumer cloning WITHOUT git-lfs installed receives that pointer instead of
    the asset — the install succeeds and the library breaks at runtime. Whether
    uv's clone runs the smudge filter depends on the consumer's global LFS
    config, which neither the publisher nor Haywire controls or can detect. And
    ``*.png`` is exactly what a node library's icons and skins match, so the
    trap would fire on the most common case.

    The trade-off is documented here instead, where the decision gets made.
    """
    return """\
# Normalize line endings on commit; check out with the platform's native EOL.
* text=auto

# Binary assets — never diffed, never EOL-converted.
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.pdf binary
*.woff binary
*.woff2 binary
*.mp4 binary
*.onnx binary
*.blob binary

# ── About Git LFS ───────────────────────────────────────────────────────────
# Do NOT add `filter=lfs` lines here without understanding the consequence.
# `haywire share` publishes by git URL, so consumers install a CLONE of this
# repo. Git stores an LFS-tracked file as a ~130-byte pointer, and a consumer
# without git-lfs installed receives that pointer text instead of the real
# asset. The install succeeds; your library breaks at runtime when it loads the
# file. Whether the clone resolves the pointer depends on the consumer's own
# git config — something you cannot control or detect from here.
#
# If your library genuinely needs large assets, download them at runtime into a
# cache directory instead of committing them.
"""
```

- [ ] **Step 5: Write the file during scaffolding**

In `init_project`, immediately after the `.gitignore` write (currently line 566), add:

```python
    # .gitattributes — EOL normalization + binary markers. No LFS: see the
    # comment block in _generate_gitattributes().
    (project_dir / ".gitattributes").write_text(_generate_gitattributes())
```

The existing `git add .` at line 588 picks it up, so the initial commit includes it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_init_scaffold_git_files.py -v`
Expected: 15 passed.

- [ ] **Step 7: Verify the trap is actually closed**

Run:
```sh
cd /tmp && rm -rf gitignore-probe && uv run --directory \
  /Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo haywire init gitignore-probe --no-sync \
  && cd /tmp/gitignore-probe \
  && mkdir -p barn/haybale-gitignore-probe/haybale_gitignore_probe/build \
  && echo x > barn/haybale-gitignore-probe/haybale_gitignore_probe/build/asset.bin \
  && git status --porcelain --ignored barn/ | grep '!!' || echo "OK: nothing under barn/ is ignored"
```
Expected: `OK: nothing under barn/ is ignored`. Before the fix, `git status --ignored` reported the `build/` directory. Clean up with `rm -rf /tmp/gitignore-probe`.

- [ ] **Step 8: Update the insight file**

`.insights/project_git_url_publishing_traps.md` currently describes the `.gitignore` fix as already applied ("Fix applied at the scaffold"). That is now true. Add a line under §2 recording that `.gitattributes` is scaffolded without LFS:

```markdown
Scaffolded at init (`_generate_gitattributes`): text=auto plus `binary` markers for common asset types, and a comment block explaining the pointer-file trap. No `filter=lfs` line is ever written.
```

- [ ] **Step 9: Lint, type-check, commit**

```sh
uv run ruff check packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffold_git_files.py
uv run ruff format packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffold_git_files.py
uv run mypy packages/haywire-studio/src/
```

```bash
git add packages/haywire-studio/src/haywire_studio/init.py tests/test_init_scaffold_git_files.py .insights/project_git_url_publishing_traps.md
git commit -m "fix(init): anchor root-only gitignore patterns, scaffold .gitattributes without LFS"
```

---

### Task 15: The wizard UI

A `Popup` holding a `ui.stepper`. There is no existing `ui.stepper` usage in this repo, so this task establishes the pattern. The design guide's rules apply: no hardcoded colors (use `--hw-*` tokens), no `ui.card()` inside `ui.dialog()` — this uses `Popup`, which already carries `hw-panel`.

**Files:**
- Create: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard.py`
- Test: `tests/test_share_wizard_ui.py`

**Interfaces:**
- Consumes: `SharePipeline` and every result/error type; `Popup`; `diff_modal`/`DiffSection`; `hui`.
- Produces:
  - `show_share_wizard(repo_root: Path, *, on_done: Callable[[], None] | None = None) -> ShareWizard`
  - `class ShareWizard` — attributes `pipeline: SharePipeline`, `popup: Popup`, `step: str` (one of `"preconditions"`, `"drift"`, `"version"`, `"docs"`, `"commit"`, `"push"`, `"done"`), `error: str | None`, `log_lines: list[str]`. Methods: `async advance_from_preconditions()`, `async advance_from_drift(choice: str)`, `async advance_from_version(spec: str)`, `async advance_from_docs()`, `async advance_from_commit(message: str, include_barn: list[Path])`, `async advance_from_push()`, `retry()`.

The UI-logic split matters for testability: every `advance_from_*` method is a plain async method that drives the pipeline and updates `self.step`/`self.error`, with no NiceGUI calls inside. Rendering reads that state. Tests exercise the methods; the render functions are exercised only by the smoke test.

- [ ] **Step 1: Write the failing test**

Create `tests/test_share_wizard_ui.py`:

```python
"""The share wizard's state machine. UI rendering is smoke-tested only."""

import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture
def project(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    remote.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote, check=True, capture_output=True)

    repo = tmp_path / "project"
    repo.mkdir()
    for args in (
        ["init"],
        ["config", "user.email", "t@t.test"],
        ["config", "user.name", "T"],
        ["remote", "add", "origin", str(remote)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)

    lib = repo / "barn" / "haybale-alpha"
    (lib / "haybale_alpha").mkdir(parents=True)
    (lib / "pyproject.toml").write_text('[project]\nname = "haybale-alpha"\nversion = "0.3.1"\n')
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "HEAD"], cwd=repo, check=True, capture_output=True)
    return repo


def _wizard(project: Path):
    """A ShareWizard with no popup — the state machine under test."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.share_pipeline import SharePipeline

    return ShareWizard(pipeline=SharePipeline(project), popup=None)


def _no_drift(lib_dir: Path):
    from haywire_studio.share import DepDrift

    return DepDrift(lib_dir=lib_dir)


def _drifty(lib_dir: Path):
    from haywire_studio.share import DepDrift

    return DepDrift(lib_dir=lib_dir, pyproject_missing=["numpy"])


def _fake_docs():
    from haywire_studio.share_pipeline.results import DocsResult

    return patch(
        "haywire_studio.share_pipeline.pipeline.SharePipeline.apply_docs",
        new=AsyncMock(return_value=DocsResult(coverage={"alpha": []}, written=[])),
    )


# ── step 1 → 2 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_wizard_starts_at_preconditions(project: Path) -> None:
    wizard = _wizard(project)
    assert wizard.step == "preconditions"
    assert wizard.error is None


@pytest.mark.anyio
async def test_healthy_project_advances_to_drift(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
    assert wizard.step == "drift"
    assert wizard.error is None


@pytest.mark.anyio
async def test_failed_preconditions_stay_put_with_an_error(tmp_path: Path) -> None:
    """The menu item is always enabled; this step explains why a workspace
    can't be shared. A disabled item can't carry a tooltip — the design guide's
    disabled state includes pointer-events: none (design-guide.md:725)."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.share_pipeline import SharePipeline

    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.error is not None
    assert "barn" in wizard.error


@pytest.mark.anyio
async def test_clean_drift_skips_straight_to_version(project: Path) -> None:
    """Nothing to decide means nothing to ask."""
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
    assert wizard.drift_report is not None
    assert wizard.drift_report.needs_decision is False


# ── step 2 → 3 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_drift_union_advances(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        with patch("haywire_studio.share_pipeline.pipeline.apply_drift_fix"):
            await wizard.advance_from_drift("union")
    assert wizard.step == "version"


@pytest.mark.anyio
async def test_drift_skip_records_the_acknowledgement(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_drifty):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    assert wizard.step == "version"
    assert wizard.pipeline.drift_acknowledged is True


@pytest.mark.anyio
async def test_version_plan_is_loaded_for_the_next_panel(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    assert wizard.version_plan is not None
    assert wizard.version_plan.common_version == "0.3.1"


# ── step 3 → 4 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_version_bump_advances_to_docs(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    assert wizard.step == "docs"
    assert wizard.pipeline.version == "0.3.2"


@pytest.mark.anyio
async def test_tag_collision_keeps_the_user_on_the_version_step(project: Path) -> None:
    """Where the fix is cheapest — 'pick 0.3.2 instead' costs nothing here."""
    subprocess.run(["git", "tag", "v0.3.2"], cwd=project, check=True, capture_output=True)
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")

    assert wizard.step == "version"
    assert wizard.error is not None
    assert "v0.3.2" in wizard.error


@pytest.mark.anyio
async def test_lock_warning_surfaces_without_blocking(project: Path) -> None:
    (project / "uv.lock").write_text("")
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    with patch(
        "haywire_studio.share_pipeline.pipeline.refresh_lockfile",
        return_value=(False, "uv lock failed: boom"),
    ):
        await wizard.advance_from_version("patch")

    assert wizard.step == "docs"
    assert wizard.warnings
    assert any("boom" in w for w in wizard.warnings)


# ── step 4 → 5 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_docs_step_advances_and_keeps_coverage(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()

    assert wizard.step == "commit"
    assert wizard.docs_result is not None
    assert wizard.commit_plan is not None


@pytest.mark.anyio
async def test_docs_failure_stays_on_the_docs_step(project: Path) -> None:
    from haywire_studio.share_pipeline import DocsGenerationError

    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")

    with patch(
        "haywire_studio.share_pipeline.pipeline.SharePipeline.apply_docs",
        new=AsyncMock(side_effect=DocsGenerationError("boom", output="traceback")),
    ):
        await wizard.advance_from_docs()

    assert wizard.step == "docs"
    assert wizard.error is not None


@pytest.mark.anyio
async def test_docs_output_is_captured_for_the_log(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")

    async def _streamy(self, on_output=None):
        from haywire_studio.share_pipeline.results import DocsResult

        if on_output:
            on_output("loading libraries…")
        return DocsResult(coverage={}, written=[])

    with patch(
        "haywire_studio.share_pipeline.pipeline.SharePipeline.apply_docs",
        new=_streamy,
    ):
        await wizard.advance_from_docs()

    assert "loading libraries…" in wizard.log_lines


# ── step 5 → 6 ───────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_commit_advances_to_push(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])

    assert wizard.step == "push"
    assert wizard.commit_result is not None
    assert wizard.commit_result.tag == "v0.3.2"


@pytest.mark.anyio
async def test_commit_step_verifies_push_before_committing(project: Path) -> None:
    """Closes the race window since step 1 — and leaves nothing to undo."""
    from haywire_studio.share_pipeline import gitcmd

    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()

    head_before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
    ).stdout

    def _rejected(args, **_kw):
        if "--dry-run" in args:
            return gitcmd.GitResult(ok=False, stdout="", stderr="! [rejected]", returncode=1)
        return gitcmd.GitResult(ok=True, stdout="", stderr="", returncode=0)

    with patch("haywire_studio.share_pipeline.pipeline.git_remote", side_effect=_rejected):
        await wizard.advance_from_commit("chore: share v0.3.2", [])

    assert wizard.step == "commit"
    assert wizard.error is not None
    assert (
        subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project, capture_output=True, text=True, check=True
        ).stdout
        == head_before
    )


@pytest.mark.anyio
async def test_opted_in_barn_files_reach_the_commit(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    asset = project / "barn" / "haybale-alpha" / "haybale_alpha" / "icon.png"
    asset.write_bytes(b"\x89PNG")
    with _fake_docs():
        await wizard.advance_from_docs()

    await wizard.advance_from_commit("chore: share v0.3.2", [asset])

    committed = subprocess.run(
        ["git", "show", "--name-only", "--format=", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert "barn/haybale-alpha/haybale_alpha/icon.png" in committed


# ── step 6 → done ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_push_completes_the_wizard(project: Path) -> None:
    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])
    await wizard.advance_from_push()

    assert wizard.step == "done"
    assert wizard.push_result is not None


@pytest.mark.anyio
async def test_push_failure_is_retryable_in_place(project: Path) -> None:
    from haywire_studio.share_pipeline import PushError

    wizard = _wizard(project)
    with patch("haywire_studio.share_pipeline.pipeline.detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_drift("skip")
    await wizard.advance_from_version("patch")
    with _fake_docs():
        await wizard.advance_from_docs()
    await wizard.advance_from_commit("chore: share v0.3.2", [])

    with patch(
        "haywire_studio.share_pipeline.pipeline.SharePipeline.apply_push",
        new=AsyncMock(side_effect=PushError(stderr="timeout", manual_command="git p ush ...")),
    ):
        await wizard.advance_from_push()

    assert wizard.step == "push"
    assert wizard.error is not None
    assert wizard.manual_command is not None

    # Retrying the same step works — the failed step is retryable in place.
    wizard.retry()
    assert wizard.error is None
    await wizard.advance_from_push()
    assert wizard.step == "done"


@pytest.mark.anyio
async def test_retry_clears_only_the_error(project: Path) -> None:
    wizard = _wizard(project)
    wizard.error = "boom"
    wizard.warnings = ["keep me"]
    wizard.retry()
    assert wizard.error is None
    assert wizard.warnings == ["keep me"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_share_wizard_ui.py -v`
Expected: collection error — `ModuleNotFoundError: No module named 'haybale_marketplace.editors._share_wizard'`

- [ ] **Step 3: Write the state machine**

Create `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard.py`:

```python
"""Share Project wizard — a stepper over :class:`SharePipeline`.

The state machine (:class:`ShareWizard`) is deliberately free of NiceGUI calls:
every ``advance_from_*`` method drives the pipeline and updates ``step`` /
``error`` / ``warnings``, and the render functions read that state. That split
is what makes the flow testable without a browser.

Failure posture mirrors the pipeline's: a failed step stays put with an inline
error and is retryable in place. Nothing is rolled back, because nothing was
mutated past the point of failure — every precondition is checkable without
mutation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from nicegui import ui

from haywire.ui import elements as hui
from haywire.ui.components.popup import Popup
from haywire_studio.share_pipeline import (
    CommitPlan,
    CommitResult,
    DocsResult,
    DriftReport,
    PushResult,
    ShareError,
    SharePipeline,
    VersionPlan,
)

logger = logging.getLogger(__name__)

STEPS = ("preconditions", "drift", "version", "docs", "commit", "push", "done")

_STEP_TITLES = {
    "preconditions": "Check the project",
    "drift": "Dependencies",
    "version": "Version",
    "docs": "Documentation",
    "commit": "Review and commit",
    "push": "Publish",
    "done": "Shared",
}


class ShareWizard:
    """Linear, resumable state machine for the Share Project flow."""

    def __init__(self, *, pipeline: SharePipeline, popup: Optional[Popup]) -> None:
        self.pipeline = pipeline
        self.popup = popup
        self.step: str = "preconditions"
        self.error: str | None = None
        self.manual_command: str | None = None
        self.warnings: list[str] = []
        self.log_lines: list[str] = []

        self.drift_report: DriftReport | None = None
        self.version_plan: VersionPlan | None = None
        self.docs_result: DocsResult | None = None
        self.commit_plan: CommitPlan | None = None
        self.commit_result: CommitResult | None = None
        self.push_result: PushResult | None = None

        self.on_render: Callable[[], None] | None = None

    # ── state transitions ────────────────────────────────────────────────────

    def retry(self) -> None:
        """Clear the error so the current step can be attempted again.

        Warnings are kept: a stale uv.lock is still stale after a retry.
        """
        self.error = None
        self.manual_command = None

    def _fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step."""
        logger.exception("Share wizard step %r failed", self.step)
        self.error = str(exc)
        self.manual_command = getattr(exc, "manual_command", None)

    async def advance_from_preconditions(self) -> None:
        self.retry()
        try:
            self.pipeline.require_preconditions()
            self.drift_report = self.pipeline.check_drift()
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "drift"

    async def advance_from_drift(self, choice: str) -> None:
        """*choice* is ``"union"``, ``"replace"``, or ``"skip"``.

        Replace can destructively remove declared deps, so it is a real
        decision the caller must have already confirmed — never an auto-fix.
        """
        self.retry()
        report = self.drift_report
        try:
            if report is not None and report.needs_decision:
                if choice == "union":
                    self.pipeline.apply_drift_union(report)
                elif choice == "replace":
                    self.pipeline.apply_drift_replace(report)
                else:
                    self.pipeline.acknowledge_drift()
            self.version_plan = self.pipeline.plan_version()
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "version"

    async def advance_from_version(self, spec: str) -> None:
        self.retry()
        try:
            result = self.pipeline.apply_bump(spec)
        except ShareError as exc:
            self._fail(exc)
            return
        if result.lock_warning:
            self.warnings.append(result.lock_warning)
        self.step = "docs"

    async def advance_from_docs(self) -> None:
        self.retry()
        try:
            self.docs_result = await self.pipeline.apply_docs(on_output=self._push_log)
            stall = self.pipeline.apply_marketstall()
            if stall.warning:
                self.warnings.append(stall.warning)
            self.commit_plan = self.pipeline.plan_commit()
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "commit"

    async def advance_from_commit(self, message: str, include_barn: list[Path]) -> None:
        self.retry()
        try:
            # Verified BEFORE committing: someone may have pushed since step 1,
            # and discovering that after a commit and tag exist leaves cleanup.
            self.pipeline.verify_push_allowed()
            plan = self.pipeline.plan_commit(message=message)
            self.commit_plan = plan
            self.commit_result = self.pipeline.apply_commit(plan, include_barn=include_barn)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "push"

    async def advance_from_push(self) -> None:
        self.retry()
        try:
            self.push_result = await self.pipeline.apply_push(on_output=self._push_log)
        except ShareError as exc:
            self._fail(exc)
            return
        self.step = "done"

    def _push_log(self, line: str) -> None:
        """Collect a streamed output line.

        Modifying an existing element from a background task is always safe (no
        slot context needed) — see .insights/feedback_nicegui_async.md case 3 —
        so the log element is updated directly when one is attached.
        """
        self.log_lines.append(line)
        log = getattr(self, "_log_element", None)
        if log is not None:
            log.push(line)
```

- [ ] **Step 4: Run the state-machine tests**

Run: `uv run pytest tests/test_share_wizard_ui.py -v`
Expected: all passed.

- [ ] **Step 5: Add the rendering layer**

Append to `_share_wizard.py`:

```python
# ──────────────────────────────────────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────────────────────────────────────


def show_share_wizard(
    repo_root: Path,
    *,
    on_done: Callable[[], None] | None = None,
) -> ShareWizard:
    """Open the Share Project wizard and return its state machine.

    Not closable mid-flight past the commit step: the popup's own close button
    stays available (the wizard mutates nothing that needs undoing), but the
    step buttons are the intended path.
    """
    popup = Popup(
        title="Share Project",
        width="620px",
        closable=True,
        backdrop_click_close=False,
        escape_close=False,
    )
    wizard = ShareWizard(pipeline=SharePipeline(repo_root), popup=popup)

    with popup:
        body = ui.column().classes("w-full gap-2")

    def _render() -> None:
        body.clear()
        with body:
            _render_progress(wizard)
            _render_step(wizard, _render, on_done)

    wizard.on_render = _render
    _render()
    popup.open()
    return wizard


def _render_progress(wizard: ShareWizard) -> None:
    """A one-line step indicator. Colours come from --hw-* tokens only."""
    index = STEPS.index(wizard.step)
    with ui.row().classes("w-full items-center gap-1"):
        for position, name in enumerate(STEPS[:-1]):
            done = position < index
            active = position == index
            colour = (
                "var(--hw-positive)" if done else ("var(--hw-accent)" if active else "var(--hw-border)")
            )
            ui.element("div").classes("flex-1 rounded").style(
                f"height: 3px; background: {colour};"
            ).tooltip(_STEP_TITLES[name])
    ui.label(_STEP_TITLES[wizard.step]).classes("text-sm font-medium")


def _render_error(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Inline error banner with a Retry button. Same visual as the progress modal."""
    if wizard.error is None:
        return
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
    ):
        ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
        with ui.column().classes("gap-1 flex-1"):
            ui.label(wizard.error).classes("text-xs hw-text-danger")
            if wizard.manual_command:
                hui.code_block(wizard.manual_command)

    def _retry() -> None:
        wizard.retry()
        rerender()

    ui.button("Retry", on_click=_retry).props("flat dense")


def _render_warnings(wizard: ShareWizard) -> None:
    for warning in wizard.warnings:
        with ui.row().classes("w-full items-start gap-2"):
            ui.icon("warning", size="14px").classes("flex-shrink-0 mt-0.5").style(
                "color: var(--hw-warning);"
            )
            ui.label(warning).classes("text-xs hw-text-muted")


def _render_step(
    wizard: ShareWizard,
    rerender: Callable[[], None],
    on_done: Callable[[], None] | None,
) -> None:
    """Dispatch to the current step's panel."""
    _render_warnings(wizard)
    _render_error(wizard, rerender)

    if wizard.step == "preconditions":
        _panel_preconditions(wizard, rerender)
    elif wizard.step == "drift":
        _panel_drift(wizard, rerender)
    elif wizard.step == "version":
        _panel_version(wizard, rerender)
    elif wizard.step == "docs":
        _panel_docs(wizard, rerender)
    elif wizard.step == "commit":
        _panel_commit(wizard, rerender)
    elif wizard.step == "push":
        _panel_push(wizard, rerender)
    else:
        _panel_done(wizard, on_done)


def _advance(wizard: ShareWizard, rerender: Callable[[], None], coro_factory):
    """Wrap an advance call so the panel re-renders afterwards.

    Returns the coroutine rather than scheduling it: NiceGUI wraps a returned
    Awaitable with the parent slot before scheduling, which is what keeps
    ui.notify() and element creation working. Scheduling it ourselves would
    hand the work a task with an empty slot stack.
    See .insights/feedback_nicegui_async.md.
    """

    async def _run():
        await coro_factory()
        rerender()

    return _run()


def _panel_preconditions(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Checks that git is available, that barn/ holds at least one library, "
        "and that origin is set and reachable."
    ).classes("text-xs hw-text-dim")
    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Check",
            on_click=lambda: _advance(wizard, rerender, wizard.advance_from_preconditions),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_drift(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    report = wizard.drift_report
    if report is None or not report.needs_decision:
        ui.label("No dependency drift — every import is declared.").classes("text-xs hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button(
                "Continue",
                on_click=lambda: _advance(
                    wizard, rerender, lambda: wizard.advance_from_drift("skip")
                ),
            ).props("flat dense").style("color: var(--hw-positive);")
        return

    ui.label("These imports are not declared:").classes("text-xs hw-text-dim")
    for drift in report.drifted:
        hui.section_label(drift.lib_dir.name)
        with ui.column().classes("gap-0.5 ml-1"):
            for dep in drift.pyproject_missing:
                ui.label(f"+ pyproject.toml: {dep}").classes("text-xs font-mono").style(
                    "color: var(--hw-positive);"
                )
            for dep in drift.decorator_missing:
                ui.label(f"+ @library(dependencies): {dep}").classes("text-xs font-mono").style(
                    "color: var(--hw-positive);"
                )
            for dist, declared, installed in drift.pyproject_version_lag:
                ui.label(f"~ {dist}: declared {declared}, installed {installed}").classes(
                    "text-xs font-mono hw-text-dim"
                )

    def _open_replace_confirm() -> None:
        from haywire.ui.modals import confirm_modal

        confirm_modal(
            title="Replace declared dependencies?",
            message=(
                "Replace overwrites each library's declarations with exactly what "
                "its source imports. Anything declared but no longer imported is "
                "REMOVED. This cannot be undone by the wizard."
            ),
            confirm_label="Replace",
            danger=True,  # confirm_modal colours the button with --hw-danger
            on_confirm=lambda: _advance(
                wizard, rerender, lambda: wizard.advance_from_drift("replace")
            ),
        )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Skip",
            on_click=lambda: _advance(wizard, rerender, lambda: wizard.advance_from_drift("skip")),
        ).props("flat dense")
        ui.button("Replace", on_click=_open_replace_confirm).props("flat dense").style(
            "color: var(--hw-warning);"
        )
        ui.button(
            "Union",
            on_click=lambda: _advance(wizard, rerender, lambda: wizard.advance_from_drift("union")),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_version(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    plan = wizard.version_plan
    if plan is None:
        return

    hui.section_label("Current versions")
    with ui.column().classes("gap-0.5 ml-1"):
        for lib in plan.current:
            ui.label(f"{lib.name}: {lib.version or '(none)'}").classes("text-xs font-mono")

    ui.label(
        "Every barn library is published at the same version (lockstep), and the "
        "repo is tagged with it."
    ).classes("text-xs hw-text-dim")

    if plan.versions_agree:
        options = {keyword: f"{keyword} → {resolved}" for keyword, resolved in plan.suggestions.items()}
        options["custom"] = "custom…"
        choice = ui.select(options, value="patch", label="Bump").classes("w-full")
        custom = hui.input_field(placeholder="X.Y.Z")
        custom.bind_visibility_from(choice, "value", lambda v: v == "custom")

        def _spec() -> str:
            return (custom.value or "").strip() if choice.value == "custom" else str(choice.value)
    else:
        ui.label(
            "These versions disagree. Name the version every library should be set to — "
            "picking one automatically would downgrade the others."
        ).classes("text-xs").style("color: var(--hw-warning);")
        custom = hui.input_field(placeholder="X.Y.Z")

        def _spec() -> str:
            return (custom.value or "").strip()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Bump",
            on_click=lambda: _advance(
                wizard, rerender, lambda: wizard.advance_from_version(_spec())
            ),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_docs(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    ui.label(
        "Regenerates OVERVIEW, QUICKREF, and per-component docs for every barn "
        "library, then rebuilds marketstall.toml. Runs in a separate process."
    ).classes("text-xs hw-text-dim")
    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 160px; font-family: monospace;")
    for line in wizard.log_lines:
        log.push(line)
    wizard._log_element = log  # noqa: SLF001 — the wizard owns this element

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Generate",
            on_click=lambda: _advance(wizard, rerender, wizard.advance_from_docs),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_commit(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    plan = wizard.commit_plan
    if plan is None:
        return

    if wizard.docs_result is not None and wizard.docs_result.total_gaps:
        hui.section_label(f"Documentation coverage: {wizard.docs_result.total_gaps} gap(s)")
        with ui.column().classes("gap-0.5 ml-1"):
            for lib_id, lines in sorted(wizard.docs_result.coverage.items()):
                for line in lines:
                    ui.label(f"{lib_id}: {line}").classes("text-xs hw-text-dim")

    hui.section_label(f"{len(plan.files)} file(s) in this commit")
    with ui.scroll_area().classes("w-full").style("height: 140px;"):
        with ui.column().classes("gap-0.5"):
            for path in plan.files:
                rel = path.relative_to(wizard.pipeline.repo_root)
                ui.label(str(rel)).classes("text-xs font-mono hw-text-dim")

    checkboxes: list[tuple[ui.checkbox, Path]] = []
    if plan.barn_dirty:
        hui.section_label("Uncommitted content under barn/")
        ui.label(
            "Consumers install from a clone of this repo, so anything left out here "
            "is silently missing for them."
        ).classes("text-xs").style("color: var(--hw-warning);")
        for entry in plan.barn_dirty:
            rel = entry.path.relative_to(wizard.pipeline.repo_root)
            marker = "new" if entry.untracked else "modified"
            box = ui.checkbox(f"{rel} ({marker})", value=True).props("dense")
            box.classes("text-xs")
            checkboxes.append((box, entry.path))

    if plan.diffstat:
        # hui.expansion_section, not ui.expansion — header styling is only
        # guaranteed correct through the wrapper (design guide §8.11).
        with hui.expansion_section("Diff summary", default_open=False):
            hui.code_block(plan.diffstat)

    message_input = hui.input_field(value=plan.message, placeholder="Commit message")
    ui.label(f"Tags this commit {plan.tag}.").classes("text-xs hw-text-dim")

    def _included() -> list[Path]:
        return [path for box, path in checkboxes if box.value]

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Commit and tag",
            on_click=lambda: _advance(
                wizard,
                rerender,
                lambda: wizard.advance_from_commit(
                    (message_input.value or plan.message).strip(), _included()
                ),
            ),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_push(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    result = wizard.commit_result
    if result is not None:
        ui.label(f"Committed {result.sha[:8]}, tagged {result.tag}.").classes("text-xs hw-text-dim")
    ui.label("Pushes the commit and tag to origin.").classes("text-xs hw-text-dim")

    log = ui.log(max_lines=200).classes("w-full text-xs").style("height: 140px; font-family: monospace;")
    wizard._log_element = log  # noqa: SLF001

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Push",
            on_click=lambda: _advance(wizard, rerender, wizard.advance_from_push),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_done(wizard: ShareWizard, on_done: Callable[[], None] | None) -> None:
    from haywire_studio.share import derive_share_url_only

    result = wizard.push_result
    if result is not None:
        ui.label(f"Published {result.tag} to {result.remote}/{result.branch}.").classes(
            "text-sm"
        ).style("color: var(--hw-positive);")

    url = derive_share_url_only(wizard.pipeline.repo_root)
    if url.share_url:
        ui.label("Share this URL so others can subscribe to your feed:").classes(
            "text-xs hw-text-dim"
        )
        hui.code_block(url.share_url)
    elif url.warning:
        ui.label(url.warning).classes("text-xs hw-text-muted")

    def _close() -> None:
        if wizard.popup is not None:
            wizard.popup.close()
        if on_done is not None:
            on_done()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
```

The `hui` helpers used above all exist and were verified against this repo:
`code_block` (elements.py:305), `section_label` (:237), `input_field` (:635),
`expansion_section` (:511). `confirm_modal` takes
`title=`/`message=`/`confirm_label=`/`danger=`/`on_confirm=`/`on_cancel=`
(confirm_modal.py:15). Re-confirm before relying on them if the files have moved:

```sh
grep -n "^def code_block\|^def section_label\|^def input_field\|^def expansion_section" \
  packages/haywire-core/src/haywire/ui/elements/elements.py
grep -n "def confirm_modal" -A 8 packages/haywire-core/src/haywire/ui/modals/confirm_modal.py
```

- [ ] **Step 6: Add a render smoke test**

Append to `tests/test_share_wizard_ui.py`:

```python
def test_render_functions_import_and_reference_only_tokens() -> None:
    """No hardcoded colours — the design guide forbids them, and a literal hex
    breaks every theme but the one it was picked in."""
    import re
    from pathlib import Path as _Path

    source = _Path(
        "barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard.py"
    ).read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source), "hardcoded colour found"
    assert "box-shadow" not in source, "no box-shadow on chrome (design guide)"
    assert "ui.card()" not in source, "use Popup / hui.dialog_card(), not a bare card"
```

- [ ] **Step 7: Run the tests**

Run: `uv run pytest tests/test_share_wizard_ui.py -v`
Expected: all passed.

- [ ] **Step 8: Lint, type-check, commit**

```sh
uv run ruff check barn/haybale-marketplace/ tests/test_share_wizard_ui.py
uv run ruff format barn/haybale-marketplace/ tests/test_share_wizard_ui.py
uv run mypy barn/haybale-marketplace/haybale_marketplace/
```

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard.py tests/test_share_wizard_ui.py
git commit -m "feat(marketplace): Share Project wizard state machine and stepper UI"
```

---

### Task 16: Menu wiring, docs, and the full sweep

**Files:**
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py:149-163`
- Modify: `docs/components/marketplace/` — whichever canon file documents the burger menu (locate it in this task)
- Test: `tests/test_share_wizard_menu.py`

**Interfaces:**
- Consumes: `show_share_wizard` (Task 15).
- Produces: `LibraryBrowserEditor._on_share_project_click(context) -> None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_share_wizard_menu.py`:

```python
"""The Share Project entry point lives on the repo-scoped burger menu."""

import inspect
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


def test_share_menu_item_is_on_the_library_browser() -> None:
    """Not on LibraryOverviewEditor: the unit of sharing is the PROJECT, and the
    other repo-scoped actions (Refresh, Add Source, Edit File) live here (ADR 0023)."""
    from haybale_marketplace.editors.library_browser_editor import LibraryBrowserEditor

    source = inspect.getsource(LibraryBrowserEditor._build_ui)
    assert "Share Project" in source
    assert "_on_share_project_click" in source


def test_overview_editor_has_no_share_button() -> None:
    """A per-library Share button would misrepresent a project-scoped, lockstep action."""
    overview = Path(
        "barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py"
    ).read_text()
    assert "show_share_wizard" not in overview
    assert "Share Project" not in overview


def test_handler_exists_and_takes_context() -> None:
    from haybale_marketplace.editors.library_browser_editor import LibraryBrowserEditor

    sig = inspect.signature(LibraryBrowserEditor._on_share_project_click)
    assert list(sig.parameters) == ["self", "context"]


def test_handler_notifies_when_no_workspace_root(monkeypatch) -> None:
    """A studio started outside a project has nothing to share; say so instead
    of opening a wizard that fails at step 1 for a confusing reason."""
    from haybale_marketplace.editors import library_browser_editor as mod

    notifications: list[tuple[str, str]] = []
    monkeypatch.setattr(
        mod.ui, "notify", lambda msg, **kw: notifications.append((msg, kw.get("type", "")))
    )
    opened: list[Path] = []
    monkeypatch.setattr(
        "haybale_marketplace.editors._share_wizard.show_share_wizard",
        lambda root, **kw: opened.append(root),
    )

    editor = mod.LibraryBrowserEditor.__new__(mod.LibraryBrowserEditor)
    context = type("Ctx", (), {"app": type("App", (), {"workspace_root": None})()})()
    editor._on_share_project_click(context)

    assert opened == []
    assert notifications
    assert "project" in notifications[0][0].lower()


def test_handler_opens_the_wizard_at_the_workspace_root(monkeypatch, tmp_path: Path) -> None:
    from haybale_marketplace.editors import library_browser_editor as mod

    opened: list[Path] = []
    monkeypatch.setattr(
        "haybale_marketplace.editors._share_wizard.show_share_wizard",
        lambda root, **kw: opened.append(Path(root)),
    )
    monkeypatch.setattr(mod.ui, "notify", lambda *a, **kw: None)

    editor = mod.LibraryBrowserEditor.__new__(mod.LibraryBrowserEditor)
    context = type("Ctx", (), {"app": type("App", (), {"workspace_root": str(tmp_path)})()})()
    editor._on_share_project_click(context)

    assert opened == [tmp_path]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_share_wizard_menu.py -v`
Expected: FAIL — `AssertionError: assert 'Share Project' in source`

- [ ] **Step 3: Add the menu item**

In `barn/haybale-marketplace/haybale_marketplace/editors/library_browser_editor.py`, inside the burger `with ui.menu():` block (currently lines 150-163), add the item after `Add Source…` and before the separator:

```python
                        ui.menu_item(
                            "Share Project…",
                            on_click=lambda c=context: self._on_share_project_click(c),
                        )
```

- [ ] **Step 4: Add the handler**

Add after `_on_add_source_click`:

```python
    def _on_share_project_click(self, context: "SessionContext") -> None:
        """Open the Share Project wizard for the current workspace.

        Project-scoped, not library-scoped: a `haywire init` project is a uv
        workspace root with one marketstall.toml feed and one git remote, so the
        artifact being published is repo-shaped and every barn/* library versions
        in lockstep. See docs/adr/0023-project-scoped-lockstep-sharing.md.
        """
        from ._share_wizard import show_share_wizard

        workspace_root = getattr(context.app, "workspace_root", None)
        if not workspace_root:
            ui.notify(
                "No project open — Share works on a haywire project directory.",
                type="warning",
            )
            return

        show_share_wizard(Path(workspace_root))
```

`Path` and `ui` are already imported at the top of the file.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_share_wizard_menu.py -v`
Expected: 5 passed.

- [ ] **Step 6: Document the new CLI surface**

Locate the docs that describe `haywire share`:

```sh
grep -rln "haywire share" docs/ CLAUDE.md README.md
```

Update every hit so `--save`, `--strict`, and `--fix` are gone and the three modes are described. In `CLAUDE.md`'s Commands block, the `haywire docs` lines stay; add nothing about `share` there unless a `share` line already exists (it does not today — leave it that way).

At minimum, update `docs/components/marketplace/marketplace-canon.md` (or the file `grep` finds) with:

```markdown
### Publishing a project

`haywire share` publishes the whole project: every `barn/*` library is bumped to
the same version (lockstep), docs are regenerated, `marketstall.toml` is rebuilt,
and the result is committed, tagged `v<version>`, and pushed.

| Mode | What it does |
| --- | --- |
| `haywire share` | Interactive. Prompts through the same six steps as the GUI wizard. |
| `haywire share --check` | Read-only. Reports dependency drift and stale docs/marketstall, exits non-zero. Writes nothing. Use it as a PR gate. |
| `haywire share --yes --bump patch` | Non-interactive. Every answer comes from a flag; refuses to run with unresolved dependency drift. |

The same pipeline backs the **Share Project…** item in the Marketplace editor's
burger menu. `--ref`/`--tag` pin the share URL for a frozen feed; the default is
branch-live, because `marketstall.toml` is a subscription feed and a tag-pinned
URL freezes subscribers at whatever version they subscribed to.
```

- [ ] **Step 7: Run the full test suite**

Run: `uv run pytest -m "not browser and not perf"`
Expected: all passed. If any pre-existing test fails, check whether it referenced a deleted `share.py` function; those are this plan's responsibility. Anything else pre-existing gets reported, not silently fixed.

Then the browser tests too, since the marketplace editor changed:

Run: `uv run pytest`
Expected: all passed.

- [ ] **Step 8: Full lint, format, and type check**

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ \
  barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ \
  barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
```
Expected: all clean. `ruff format --check` failing means running `uv run ruff format .` and re-committing — CI runs both and they catch disjoint problems.

- [ ] **Step 9: Regenerate the marketplace library's docs**

The marketplace library gained a file, so its generated docs are stale:

```sh
uv run haywire docs barn/haybale-marketplace
```

Review the diff (`git diff barn/haybale-marketplace/`) before staging — the generator owns `docs/`, `OVERVIEW.md`, and `QUICKREF.md` entirely.

- [ ] **Step 10: Commit**

```bash
git add barn/haybale-marketplace/ tests/test_share_wizard_menu.py docs/
git commit -m "feat(marketplace): wire Share Project into the burger menu, document the new CLI"
```

---

## Loose ends deliberately left out

Recorded so a later session doesn't mistake them for oversights:

- **Farmhand MCP tools.** The pipeline was designed to be callable from a Farmhand wrapper (`FarmhandError(code, message, ids)` translation, two-call detect-then-apply for the drift decision), and the seams are in place. No tools are built: the UI-guided flow is user-friendly enough on its own, so this is deferred until there is a concrete agent-driven use case.
- **`install_spec` pinning to the release tag.** Verified mechanics are in `.insights/project_git_url_publishing_traps.md` §3. Deferred because it changes what every consumer installs — a far larger blast radius than a publish wizard — and needs its own thinking about how a pinned consumer moves to a new version.
- **Retrofitting `.gitignore`/`.gitattributes` into existing projects.** Only new `haywire init` scaffolds get the fixes. An edited `.gitignore` is an expression of intent.
- **Undo/redo integration.** No `ctx.fence()`, no rollback. Pre-flight verification means nothing needs undoing.
- **Share-time detection of gitignored barn files.** After anchoring, the patterns that still match at depth are all correctly ignored, so a warning would fire on every run for a fresh library and train users to skip it.
