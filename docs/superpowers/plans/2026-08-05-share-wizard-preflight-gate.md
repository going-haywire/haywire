# Share Wizard Preflight Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Share Wizard's step-1 collect-all/fix-in-place/recheck loop with a fail-fast preflight gate (one failure at a time, no in-wizard retry loop), add two missing preconditions (clean working tree, recognized git host), and route failures to modals instead of inline banner rows: **precondition** failures get one of two shapes (inform / act), and **mid-pipeline** failures (steps 2-6) get a third (rollback-then-inform) that reverts the working tree before reporting.

**Architecture:** `steps/preconditions.py::check()` changes from "collect every failure into a list" to "stop at the first failure and return it" — a pure, already-well-tested function, so this is a mechanical rewrite with existing test coverage as a guide. Two new probes are added to its sequence: working-tree-clean (new first check) and host-recognized (slotted between origin-exists and origin-reachable). The wizard UI (`_state.py`/`chrome.py`/`panels.py`) drops its `add_origin`/`strip_os` inline-fix machinery entirely and gains a small modal layer: `remedy_modal.py` (new file) renders one of three shapes keyed off a new `PreconditionFailure.kind` field. Mid-pipeline failures (steps 2–6) get a distinct rollback modal that reverts the whole repo with `git checkout -- . && git clean -fd` before reporting — safe specifically because the new clean-tree precondition guarantees nothing else could be lost.

**Tech Stack:** Python 3.12, NiceGUI (`ui.dialog` + `hui.dialog_card`), pytest, existing `SharePipeline`/`StepFlow` machinery.

## Verified Facts (read the code, do not re-derive)

These were confirmed against the working tree on 2026-08-05. Several contradict what an earlier draft of this plan assumed — trust this section over intuition.

- **`tests/test_share_wizard_ui.py` is NOT a browser test file.** It has no `user` fixture, no NiceGUI test client, and no Playwright. `_wizard()` (line 48-53) builds `ShareWizard(pipeline=SharePipeline(project), popup=None)` and tests call `await wizard.advance_from_*()` directly. Its own docstring says: *"The share wizard's state machine. UI rendering is smoke-tested only."* **No test in this file can assert that a modal is visible or that a dialog button was clicked.** Every wizard test in this plan is therefore a state-machine test.
- **`error_detail` cannot open a modal.** `stepper/chrome.py::show_step_flow._render()` (line 67-73) calls `render_error(...)` on *every* re-render, and `render_error` (line 107-136) invokes `error_detail` *inside* the error banner's `ui.column()` slot, then renders a `Retry` button underneath regardless of the return value. Calling `dialog.open()` there spawns a new dialog per redraw, parents it to a slot that gets cleared, and leaves a redundant Retry button beside "Restart Wizard". The modal needs a different seam — see Task 6.
- **`urlsplit()` yields an empty hostname for both local paths and scp-form SSH URLs.** Measured:
  `'/tmp/remote.git'` → `''`; `'git@gitlab.com:a/b.git'` → `''`; `'https://github.com/a/b.git'` → `'github.com'`.
  Every `bare_remote` fixture in `tests/share_pipeline/test_preconditions.py` and `tests/test_share_wizard_ui.py` points `origin` at a **local filesystem path**. A host-recognition probe that does not special-case "no parseable hostname" fails every one of those tests. See Task 4.
- **The CLI shares `check_preconditions()`.** `cli.py` drives the same `SharePipeline`, so Task 3's clean-tree gate changes CLI behavior whether or not any task edits `cli.py`. It also reads `plan.barn_dirty` (line 344-352) and passes `include_barn=` to `apply_commit` (line 364) — API that Task 8 deletes. "CLI out of scope" is not achievable; the constraint below is corrected accordingly.
- **`barn_dirty` has more call sites than an earlier draft listed.** Full set: `results.py:126,137,143`; `steps/commit.py:12,44,60,71,81,100,116,163,165,175`; `pipeline/__init__.py:30,46`; `pipeline.py:23,191-193,215-218`; `cli.py:344-364`; `panels.py:513-525` + `_included()`; `_state.py:389,397`; `tests/share_pipeline/test_vocabulary.py:8,135,140`; `tests/share_pipeline/test_commit_step.py:128-169,289,301`; `tests/test_share_wizard_ui.py:570`.
- **`_user_config_path()` already exists** at `haywire/core/marketstall/host_providers/config.py:22`, documented as *"Wrapped for test monkeypatching."* Use it; do not re-derive `Path.home() / ".haywire" / "config.toml"`.
- **`PreconditionsError.__init__` takes `list[PreconditionFailure]`** (`errors.py:27`) and builds a multi-line message by iterating it. Keeping that constructor signature is what lets Task 1's shim work.

## Global Constraints

- Line length 109 (ruff). Run `uv run ruff check .` and `uv run ruff format --check .` after every task that touches `.py` files.
- Type-check with `uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/` before the final task.
- No hardcoded colors — use `var(--hw-*)` tokens (design-guide.md). No `ui.card()` inside `ui.dialog()` — use `hui.dialog_card()`. No `box-shadow` on chrome elements outside `dialog_card`.
- **CLI (`packaging/share/cli.py`) gets no new UX** — no modals, no rollback prompt, no interactive remediation. But it is NOT untouched: Task 8 must remove its `barn_dirty`/`include_barn` block, because that API is being deleted out from under it. The CLI also inherits the new clean-tree gate automatically (it calls the same `check_preconditions()`); that is intended, and Task 10 documents it.
- Class B (inline input validation) is explicitly OUT OF SCOPE — no task introduces it.
- Every new/changed `.py` file needs `from __future__ import annotations` if the surrounding file already has it (match file-local convention).
- `git_remote`/`git_remote_streaming` (network-touching) vs. `git`/`run_streaming` (local-only) — use the hardened variant only for calls that reach a remote (see `packages/haywire-studio/src/haywire_studio/packaging/share/git.py` docstring).
- **Test-count discipline:** this plan deliberately refurbishes existing tests rather than adding parallel ones. Where a task says "replace test X", replace it — do not leave the old one beside the new one.

---

## File Structure

**Modified:**
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py` — `PreconditionFailure` gains `kind` field; `PreconditionsReport.failures` becomes single-result shaped.
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py` — `check()` rewritten to stop-at-first-failure; two new probes added.
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/pipeline.py` — `check_preconditions()`/`require_preconditions()` return-type follow-through; rollback method added.
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/errors.py` — `PreconditionsError` follow-through for single-failure shape.
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/fixes.py` — `_fix_add_origin`/`_fix_strip_os` kept as pipeline-level API (still reachable, e.g. for tests / future CLI use) but no longer wizard-invoked. Docstring-only edit (Task 9).
- `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py` — gains `ssh_to_https` (promoted out of `url.py`) plus `"ssh_to_https"` in `__all__` (Task 4).
- `packages/haywire-studio/src/haywire_studio/packaging/share/url.py` — `_ssh_to_https` deleted, imported from `host_providers` instead. Its `_unknown_host_warning` stays untouched (Task 5 verifies this).
- `packages/haywire-studio/src/haywire_studio/packaging/share/cli.py` — the `barn_dirty`/`include_barn` block (lines 344-352, 364) removed with the API it reads (Task 8).
- `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/_state.py` — drop `advance_from_preconditions_fix`; `precondition_failures` → `precondition_failure`; add `pending_modal` one-shot; add rollback-triggering failure path for steps 2–6; `advance_from_commit` drops `include_barn`.
- `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/chrome.py` — drop the `error_detail=` wiring and `_render_precondition_failures` entirely (the modal is opened from the panel, not the error banner — see Task 6).
- `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py` — delete `_render_fix`; `_panel_preconditions` drains `pending_modal`; `_panel_commit` loses the `barn_dirty` checkbox block and `_included()`.

**New:**
- `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/remedy_modal.py` — the three modal shapes (inform / act / rollback) as NiceGUI dialogs, dispatched by `PreconditionFailure.kind`.
- `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/rollback.py` — `revert_working_tree(pipeline)`: `git checkout -- .` + `git clean -fd`, whole repo.

**Test files — the full accounting.** This plan nets **+8 tests, −6 tests** (17 candidate new tests were reviewed; 7 were dropped as redundant with existing coverage, and 6 existing tests are deleted as their subject disappears).

*Refurbished in place (behavior changed, test rewritten — do NOT keep the old one alongside):*

- `test_preconditions.py::test_every_failure_is_reported_together` → `test_check_stops_at_the_first_failure` (Task 2).
- `test_preconditions.py::test_require_preconditions_raises_with_all_failures` → `..._with_the_first_failure` (Task 2).
- `test_preconditions.py::project` fixture — gains a commit so the clean-tree probe passes (Task 3).
- `test_preconditions.py::test_every_failure_has_a_non_empty_remedy` — its 5 scenarios each need a commit; the `broken3` scenario's premise (multi-failure) is corrected (Task 3).
- `test_share_wizard_ui.py`'s 5 `advance_from_preconditions_fix` tests (lines 703-810) → retargeted at `pipeline.apply_precondition_fix` + `advance_from_preconditions`, since the wizard method is deleted but the fix→recheck round-trip still matters (Task 6).

*Genuinely new (8):*

- `test_vocabulary.py`: `kind` defaults to `"inform"` (1).
- `test_preconditions.py`: dirty-tree fires first (1), unrecognized host + remedy snippet (1), unparseable-hostname skips recognition (1), host-recognition passes through to reachability (1).
- `test_rollback.py`: 3 tests for `revert_working_tree`.

*Dropped as redundant (7) — rationale recorded so a future reader doesn't "helpfully" add them back:*

- `PreconditionsReport.failure` is-None / returns-single-entry (2): a 2-line property already exercised by every stop-at-first assertion.
- `test_clean_working_tree_passes_this_check`: identical to the existing `test_healthy_project_passes` once the fixture commits.
- 3 × `ssh_to_https` unit tests: a pure move of a function already covered through `_derive_url` by `test_share_url_derivation.py:56,117,133`. Task 4 Step 5 re-runs those as the regression gate for the move.
- `test_commit_plan_never_has_barn_dirty`: `assert not hasattr(frozen_dataclass, "field")` asserts the language works; mypy + the deletion cover it.

*Deleted (6) — subject removed:*

- `test_share_wizard_ui.py::test_opted_in_barn_files_reach_the_commit` (line 570).
- `test_commit_step.py`'s `barn_dirty_files` block (lines 128-169, 4 tests) and the 2 `include_barn` assertions (lines 289, 301).
- `test_vocabulary.py`'s `CommitPlan(barn_dirty=...)` construction (line 135-140) — edited, not deleted, to drop the field.

---

## Task 1: `PreconditionFailure` gains a `kind` field; report shape becomes single-result

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py:10-47`
- Test: `tests/share_pipeline/test_vocabulary.py` (existing file — extend)

**Interfaces:**
- Consumes: nothing new.
- Produces: `PreconditionFailure.kind: Literal["inform", "act"]` (default `"inform"`); `PreconditionsReport.failure: PreconditionFailure | None` (new field, replaces list-typed `failures` as the primary accessor); `PreconditionsReport.failures` kept temporarily as a computed compatibility shim (`[self.failure] if self.failure else []`) so Task 2 can migrate probes one at a time without breaking every call site in the same commit.

This task only touches the dataclasses — no behavior changes to `check()` yet (that's Task 2). `kind` distinguishes the two modal shapes for step-1 failures decided in the design: `"inform"` (nothing the wizard can act on) is the default for every existing failure; `"act"` marks the two (soon three) failures that get an act-modal. The rollback modal (Class C, mid-pipeline) is NOT a `PreconditionFailure` at all — it is a distinct `ShareError` path, handled in Task 7. Do not add a `"rollback"` kind here.

- [ ] **Step 1: Write the failing test**

Add to `tests/share_pipeline/test_vocabulary.py` (read the file first to match its existing style before inserting):

```python
def test_precondition_failure_kind_defaults_to_inform_and_accepts_act():
    """``kind`` is what selects the wizard's modal shape, so its default
    matters: every failure that does not opt in must present as inform-only,
    never accidentally offering a fix button it has no handler for."""
    from haywire_studio.packaging.share.pipeline.results import PreconditionFailure

    assert PreconditionFailure(message="x").kind == "inform"
    assert PreconditionFailure(message="x", kind="act", fix_id="add_origin").kind == "act"
```

Only ONE test here, deliberately. Two candidates were considered and dropped: `PreconditionsReport.failure` returning `None` when ok and the single entry otherwise is a two-line property whose behavior is asserted by every stop-at-first test in Task 2-4 (`report.failure.message`, `report.failure.kind`) — a dedicated test would restate the implementation. See the plan header's test accounting.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_vocabulary.py -k "kind_defaults" -v`
Expected: FAIL — `TypeError: PreconditionFailure.__init__() got an unexpected keyword argument 'kind'`.

- [ ] **Step 3: Write minimal implementation**

In `results.py`, update the `PreconditionFailure` dataclass (around line 10-33):

```python
from typing import Literal

@dataclass(frozen=True)
class PreconditionFailure:
    """One reason a project cannot be published.

    ``message`` states the fault; ``remedy`` states the next action and is
    computed from repo state where that beats a constant (naming the branches
    that contain HEAD, quoting the TOML parser's line number). Presentation
    belongs to the caller: the CLI indents, the wizard renders a remedy modal.

    ``kind`` selects the wizard's remedy-modal shape: ``"inform"`` (default)
    for a failure the wizard cannot act on — message + remedy text, dismiss
    only. ``"act"`` for a failure the wizard CAN repair in place — the modal
    additionally offers a button that performs the fix, then the user
    restarts the wizard to re-check from the top. Mid-pipeline failures
    (steps 2-6, after preflight has passed) are a third, distinct modal shape
    handled outside this class entirely — see ``steps/rollback.py``.

    ``fix_id`` names a repair the pipeline can perform in place. Set only
    when ``kind == "act"``. A string rather than a callable so the report
    stays serializable and repo-mutating closures never cross the engine/UI
    seam.

    ``lib_dir`` is the affected barn library's directory, relative to
    ``repo_root``, for fixes that need to know which library to repair — a
    plain string (not a Path) for the same serializability reason as ``fix_id``.
    """

    message: str
    remedy: str = ""
    kind: Literal["inform", "act"] = "inform"
    fix_id: str | None = None
    fix_label: str = ""
    lib_dir: str | None = None


@dataclass(frozen=True)
class PreconditionsReport:
    """Outcome of step 1. ``ok`` is True iff nothing failed.

    ``check()`` (steps/preconditions.py) stops at the first failure it finds
    — an earlier failure can invalidate the relevance of a later probe (a
    dirty tree makes every later check moot; an unrecognized host makes the
    reachability probe against it wasted). So ``failures`` never holds more
    than one entry; ``failure`` is the primary accessor going forward.
    ``failures`` is kept as a read-only view for callers not yet migrated.
    """

    failures: list[PreconditionFailure]
    remote_url: str | None
    barn_libraries: list[Path]
    default_branch: str | None = None

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def failure(self) -> PreconditionFailure | None:
        return self.failures[0] if self.failures else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_vocabulary.py -k "kind_defaults" -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full vocabulary test file to check nothing else broke**

Run: `uv run pytest tests/share_pipeline/test_vocabulary.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py tests/share_pipeline/test_vocabulary.py
git commit -m "feat(share): add PreconditionFailure.kind and PreconditionsReport.failure

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 2: `check()` stops at the first failure (existing checks only — no new probes yet)

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py:27-222`
- Test: `tests/share_pipeline/test_preconditions.py`

**Interfaces:**
- Consumes: `PreconditionFailure`, `PreconditionsReport` from Task 1.
- Produces: `check(pipeline) -> PreconditionsReport` — same signature, now returns at most one failure. The `failures: list[PreconditionFailure] = []` accumulator (line 54) and the `else:` branches that exist only to keep collecting after a fault (lines 80-91, 148-171) all disappear once probes return early.

This task rewrites the CONTROL FLOW of `check()` only — every existing probe stays, in the same order, with the same messages/remedies. The only change: `return` immediately after constructing each `PreconditionFailure`, instead of `.append()`-ing to a list and continuing. This is deliberately separated from Task 3 (new probes) so a broken merge is easy to bisect.

The one behavior change existing tests must be updated for: `test_every_failure_is_reported_together` (currently asserts no-barn AND no-origin both appear) no longer holds — stop-at-first-failure means only the first-encountered problem is reported. Per the design spec, this is the intended new behavior, not a regression: the barn/-exists probe runs before the origin probe, so a project with both problems now reports only "no barn/" first; fixing that and re-running the wizard surfaces the origin problem next. Rename this test to assert the new behavior.

`test_every_failure_has_a_non_empty_remedy` iterates `report.failures` — this still works unchanged since it is now a list of ≤1 item, but simplify it to use `report.failure` for clarity.

- [ ] **Step 1: Write the failing test**

Replace `test_every_failure_is_reported_together` in `tests/share_pipeline/test_preconditions.py` (currently at line 125-132) with:

```python
def test_check_stops_at_the_first_failure(tmp_path: Path) -> None:
    """No barn/ AND no origin are both true here, but only the first-encountered
    problem (no barn/, which is probed before origin) is reported — an earlier
    failure can make a later probe's result moot, so check() does not run it."""
    repo = tmp_path / "broken"
    _init_repo(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert len(report.failures) == 1
    assert "barn" in report.failure.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py::test_check_stops_at_the_first_failure -v`
Expected: FAIL — `assert len(report.failures) == 1` fails because today's `check()` collects both the barn/ and origin failures (`len(report.failures) >= 2`).

- [ ] **Step 3: Write minimal implementation**

In `preconditions.py`, rewrite `check()` (replacing lines 27-222) so every `failures.append(...)` becomes an early `return PreconditionsReport(failures=[...], ...)`. **Read the current file first** — the rewrite below preserves every message, remedy, and fix_id verbatim, only changing control flow, so diff it against the original rather than trusting this transcription:

```python
def check(pipeline: "SharePipeline") -> PreconditionsReport:
    """Verify everything needed to publish. Stops at the FIRST failure.

    Reports rather than raises so the wizard's first panel can explain why
    a workspace cannot be shared. The menu item is always enabled — a
    disabled one cannot carry a tooltip, since the design guide's disabled
    state includes ``pointer-events: none`` (design-guide.md:725).

    Stop-at-first-failure (not collect-all): an earlier failure can make a
    later probe's result moot or misleading — a dirty working tree means
    nothing else matters until it's clean; an unreachable-because-nonexistent
    origin makes the reachability round-trip wasted; an unrecognized host
    makes the reachability probe against it wasted too. Each probe below
    returns immediately once it finds a problem, so ``PreconditionsReport``
    never carries more than one failure. The wizard exits to a remedy modal
    on any failure and the user restarts it after fixing what's reported —
    cheap enough that this costs nothing (see ADR — Share Wizard Preflight
    Gate, 2026-08-05).

    The remote reachability check is ``git ls-remote --symref origin
    HEAD``: it exercises the exact credential path ``git push`` uses, so
    an auth failure surfaces here rather than after a commit and tag
    already exist. ``--symref`` narrows the round-trip to one ref instead
    of every ref, and its output additionally names the remote's default
    branch (``ref: refs/heads/<name>\\tHEAD``), which the non-default-
    branch check below needs. ``git symbolic-ref refs/remotes/origin/HEAD``
    is NOT a usable local substitute for that — it is unset in this very
    repo (nothing populates it without an explicit ``git remote set-head``)
    — so the remote round-trip is the only reliable source.

    Every ``barn/*`` library's ``pyproject.toml`` is parsed with
    :func:`read_manifest`; a malformed file or an invalid ``os``
    declaration is reported here rather than surfacing later as a crash
    mid-docs-generation or a silently wrong marketstall entry.
    """
    version = git(["--version"], cwd=pipeline.repo_root, timeout=10.0)
    if not version.ok:
        return PreconditionsReport(
            failures=[PreconditionFailure(message="git is not installed.", remedy=GIT_INSTALL_HINT)],
            remote_url=None,
            barn_libraries=[],
        )

    barn = pipeline.repo_root / "barn"
    barn_libraries: list[Path] = []
    if not barn.is_dir():
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"No barn/ directory at {pipeline.repo_root}. Is this a haywire project root?",
                    remedy=(
                        "Run this from your haywire project root (the directory containing "
                        "barn/), or run `haywire init <name>` to scaffold a new project."
                    ),
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

    barn_libraries = pipeline._barn_library_dirs()
    if not barn_libraries:
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"No library with a pyproject.toml under {barn}. Nothing to publish.",
                    remedy=(
                        "Add a library under barn/, each with its own pyproject.toml — "
                        "see docs/haybale/haybale-package-canon.md for the expected layout."
                    ),
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

    for lib_dir in barn_libraries:
        pyproject_path = lib_dir / "pyproject.toml"
        try:
            rel_path = pyproject_path.relative_to(pipeline.repo_root)
        except ValueError:
            rel_path = pyproject_path
        try:
            rel_lib_dir = lib_dir.relative_to(pipeline.repo_root)
        except ValueError:
            rel_lib_dir = lib_dir
        try:
            read_manifest(lib_dir)
        except InvalidOsDeclarationError as exc:
            invalid_values = invalid_os_values(lib_dir)
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message=f"Invalid manifest at {rel_path}: {exc}",
                        remedy=(
                            "[tool.haywire].os may only declare `macos`, `windows`, `linux`. "
                            "`other` is a runtime sentinel for platforms that don't map to one "
                            "of those three — it is set at runtime and must never be declared. "
                            "Remove it (or the whole invalid entry) from the list."
                        ),
                        kind="act",
                        fix_id="strip_os",
                        fix_label=describe_os_fix(invalid_values),
                        lib_dir=str(rel_lib_dir),
                    )
                ],
                remote_url=None,
                barn_libraries=barn_libraries,
            )
        except ManifestReadError as exc:
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message=f"Could not read {rel_path}: {exc}",
                        remedy=f"Fix the TOML in {rel_path} so it parses, then try again.",
                    )
                ],
                remote_url=None,
                barn_libraries=barn_libraries,
            )

    remote = git(["remote", "get-url", "origin"], cwd=pipeline.repo_root, timeout=10.0)
    if not remote.ok or not remote.stdout.strip():
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message="No 'origin' remote is configured.",
                    remedy=_NO_REMOTE_HINT,
                    kind="act",
                    fix_id="add_origin",
                    fix_label="Add origin remote",
                )
            ],
            remote_url=None,
            barn_libraries=barn_libraries,
        )

    remote_url = remote.stdout.strip()
    reachable = git_remote(["ls-remote", "--symref", "origin", "HEAD"], cwd=pipeline.repo_root, timeout=60.0)
    if not reachable.ok:
        detail = (reachable.stderr or reachable.stdout).strip().splitlines()
        first = detail[0] if detail else f"exit {reachable.returncode}"
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Cannot reach origin ({remote_url}): {first}",
                    remedy="Check the URL and your credentials, then try again.",
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
        )

    default_branch: str | None = None
    for line in reachable.stdout.splitlines():
        left, sep, right = line.partition("\t")
        if sep and right.strip() == "HEAD" and left.startswith("ref: refs/heads/"):
            default_branch = left.removeprefix("ref: refs/heads/").strip()
            break

    symbolic = git(["symbolic-ref", "-q", "HEAD"], cwd=pipeline.repo_root, timeout=10.0)
    if not symbolic.ok:
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message="HEAD is detached — no branch is currently checked out.",
                    remedy=_detached_head_remedy(pipeline),
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
            default_branch=default_branch,
        )

    if default_branch is not None:
        current = pipeline.current_branch()
        if current is None:
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message="HEAD is detached — no branch is currently checked out.",
                        remedy=_detached_head_remedy(pipeline),
                    )
                ],
                remote_url=remote_url,
                barn_libraries=barn_libraries,
                default_branch=default_branch,
            )
        if current != default_branch:
            return PreconditionsReport(
                failures=[
                    PreconditionFailure(
                        message=(
                            f"Currently on `{current}`, but the repository's default branch "
                            f"is `{default_branch}`."
                        ),
                        remedy=(
                            f"Switch to the default branch and publish from there: "
                            f"`git switch {default_branch}`."
                        ),
                    )
                ],
                remote_url=remote_url,
                barn_libraries=barn_libraries,
                default_branch=default_branch,
            )

    pipeline.remote_url = remote_url
    return PreconditionsReport(
        failures=[],
        remote_url=remote_url,
        barn_libraries=barn_libraries,
        default_branch=default_branch,
    )
```

Note the `strip_os` and `add_origin` failures now carry `kind="act"` — set here in Task 2 since it's a one-line addition to code already being rewritten, even though the modal that consumes it doesn't exist until Task 6. This keeps `check()` as the single source of truth for which failures are actionable, rather than splitting that decision between this file and the UI layer.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v`
Expected: PASS for `test_check_stops_at_the_first_failure`. Also re-check `test_require_preconditions_raises_with_all_failures` (line 147) — it asserts `len(excinfo.value.failures) >= 2`, which now fails (always exactly 1). Update it:

```python
def test_require_preconditions_raises_with_the_first_failure(tmp_path: Path) -> None:
    repo = tmp_path / "broken2"
    _init_repo(repo)
    with pytest.raises(PreconditionsError) as excinfo:
        SharePipeline(repo).require_preconditions()
    assert len(excinfo.value.failures) == 1
```

Also update `test_invalid_os_declaration_carries_strip_os_fix_id` and any other test asserting on `fix_id`/`kind` co-presence — add `assert f.kind == "act"` alongside the existing `assert f.fix_id == "strip_os"` assertion (both in `test_invalid_os_declaration_carries_strip_os_fix_id`, line ~261-275) and to `add_origin`'s coverage in `test_missing_origin_fails_with_setup_instructions` (line 98-105):

```python
def test_missing_origin_fails_with_setup_instructions(tmp_path: Path) -> None:
    repo = tmp_path / "noremote"
    _init_repo(repo)
    _add_lib(repo)
    report = SharePipeline(repo).check_preconditions()
    assert report.ok is False
    assert report.failure.kind == "act"
    assert report.failure.fix_id == "add_origin"
    assert any("remote add origin" in f.remedy for f in report.failures)
    assert report.remote_url is None
```

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v`
Expected: all PASS

- [ ] **Step 5: Run full precondition + vocabulary suite**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py tests/share_pipeline/test_preconditions.py
git commit -m "feat(share): check() stops at the first precondition failure

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 3: New precondition — working tree must be clean (runs before every check except git-installed)

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py`
- Test: `tests/share_pipeline/test_preconditions.py`

**Interfaces:**
- Consumes: `git` helper from `haywire_studio.packaging.share.git` (already imported in this file).
- Produces: nothing new exported — this is a probe inserted into `check()`'s existing sequence.

This is THE precondition that makes rollback safe (Task 7): if the tree is proven clean before the wizard writes anything, any dirt found after a failure is provably the current run's own writes, so a blanket revert cannot destroy pre-existing uncommitted work.

**Position: the second probe** — immediately after the git-installed check, before the `barn/` check. It cannot be literally first, because `git status --porcelain` needs the binary that the first probe verifies. It goes ahead of everything else because it is local-only, cheap, and the most likely to fire in practice (matching the design's "cheap and most-likely-to-fire checks run early"). Everything downstream of it — including all of Task 4's host work — is therefore only ever reached from a clean tree.

Detection: `git status --porcelain` non-empty means dirty (covers staged, unstaged, and untracked files — deliberately "whole repo, period", not scoped to `barn/`, per the settled design).

- [ ] **Step 1: Write the failing test**

Add to `tests/share_pipeline/test_preconditions.py`:

```python
def test_dirty_working_tree_fails_first_and_lists_every_dirty_file(
    tmp_path: Path, bare_remote: Path
) -> None:
    """A dirty tree wins over every other probe, and names every offending
    file so the user can act without re-running `git status` themselves.

    The repo is otherwise healthy EXCEPT that it is also on a non-default
    branch — proving ordering, since stop-at-first-failure means only the
    earliest probe can show. Two dirty files, one modified and one untracked,
    cover both halves of `git status --porcelain` output.
    """
    repo = tmp_path / "dirty"
    _init_repo(repo)
    _add_lib(repo)
    _commit(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)], cwd=repo, check=True, capture_output=True
    )
    (repo / "barn" / "haybale-alpha" / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (repo / "untracked.txt").write_text("scratch")

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    assert "working tree" in report.failure.message.lower()
    assert "untracked.txt" in report.failure.message
    assert "pyproject.toml" in report.failure.message
```

ONE test, not three. The plan's earlier draft split "fires first" and "lists every file" across two tests with identical setup, and added a clean-tree pass test — but once Step 5 fixes the `project` fixture to commit, that third test is character-for-character the existing `test_healthy_project_passes` (line 67). Do not add it.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -k "dirty_working_tree" -v`
Expected: FAIL — no such check exists yet, so `check()` proceeds past the dirt and `report.ok` is True (or fails on a later probe with a message that mentions neither file).

- [ ] **Step 3: Write minimal implementation**

In `preconditions.py`, add a new probe right after the git-installed check (after the `if not version.ok:` block, before the `barn = pipeline.repo_root / "barn"` line):

```python
    dirty = git(["status", "--porcelain"], cwd=pipeline.repo_root, timeout=10.0)
    if dirty.ok and dirty.stdout.strip():
        dirty_files = [line[3:].strip() for line in dirty.stdout.splitlines() if line.strip()]
        listed = "\n".join(f"  {f}" for f in dirty_files)
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Working tree is not clean:\n{listed}",
                    remedy=(
                        "Commit or stash these changes before sharing. The publish pipeline "
                        "reverts everything it writes on failure by resetting the whole working "
                        "tree — anything already uncommitted here would be lost along with it, "
                        "so nothing may be dirty before the wizard starts."
                    ),
                )
            ],
            remote_url=None,
            barn_libraries=[],
        )

```

Place this block immediately after the existing:
```python
    version = git(["--version"], cwd=pipeline.repo_root, timeout=10.0)
    if not version.ok:
        return PreconditionsReport(
            failures=[PreconditionFailure(message="git is not installed.", remedy=GIT_INSTALL_HINT)],
            remote_url=None,
            barn_libraries=[],
        )

```
and before `    barn = pipeline.repo_root / "barn"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -k "dirty_working_tree" -v`
Expected: PASS (1 test)

- [ ] **Step 5: Run the full precondition suite — existing fixtures may need updating**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v`

The `project` fixture (line 52-64) creates a repo with a barn library but never commits — every file it creates is untracked. Every existing test built on `project` will now fail this new check first, masking whatever they meant to test. Fix the fixture itself so existing tests keep testing what they were written to test:

```python
@pytest.fixture
def project(tmp_path: Path, bare_remote: Path) -> Path:
    """A shareable project: git repo, one barn library, origin pointing at a real bare repo, clean tree."""
    repo = tmp_path / "project"
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_remote)],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    _commit(repo)
    return repo
```

Note this fixture change alone makes a clean-tree "happy path" test unnecessary — `test_healthy_project_passes` (line 67) now exercises exactly that, through the same fixture.

One subtlety to verify rather than assume: `_commit()` must run AFTER `git remote add origin`, because adding a remote writes `.git/config`, which is not part of the working tree — so order does not actually matter for cleanliness here, but keeping the commit last matches every other fixture in the file and avoids a second `git add -A` surprise if `_add_lib` is ever extended.

Every OTHER existing test that builds a broken repo from scratch (`test_missing_barn_directory_fails`, `test_barn_with_no_library_fails`, `test_missing_origin_fails_with_setup_instructions`, `test_unreachable_remote_fails`, `test_check_stops_at_the_first_failure`, `test_missing_git_binary_reports_install_instructions` via `project`, `test_require_preconditions_raises_with_the_first_failure`, `test_every_failure_has_a_non_empty_remedy`'s five scenarios, the `test_invalid_os_declaration_*` trio, `test_malformed_toml_fails_with_remedy`) constructs its repo with `_init_repo` + `_add_lib` but WITHOUT committing — meaning every one of them is now "dirty" (untracked files) before it ever reaches the check it means to test. Fix each by adding `_commit(repo)` right after the repo is fully set up for that scenario, EXCEPT where the test is deliberately about an earlier-failing state that should still win (none currently are — dirty-tree is now probe #1, before everything else, so every other scenario needs a commit to reach its own probe). For the `test_invalid_os_declaration_*` tests specifically, which mutate `pyproject.toml` on the already-committed `project` fixture AFTER the fixture returns, add a second `_commit(project)` after the mutation:

```python
def test_invalid_os_declaration_fails_with_remedy(project: Path) -> None:
    lib = project / "barn" / "haybale-alpha"
    pyproject = lib / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    _commit(project, "add invalid os")

    report = SharePipeline(project).check_preconditions()
    ...
```

Apply the same `_commit(project, "...")` pattern to `test_invalid_os_declaration_carries_strip_os_fix_id`, `test_invalid_os_declaration_fix_label_states_correction_when_unambiguous`, and `test_malformed_toml_fails_with_remedy` (each mutates a file on the committed `project` fixture and must commit again before checking).

For the from-scratch repos, the rule is: **a repo needs `_commit(repo)` if and only if `_add_lib` wrote files into it.** `_add_lib` creates `barn/<name>/pyproject.toml`, which `git status --porcelain` reports as untracked; a bare `_init_repo` leaves an empty repo, and an empty directory is invisible to git. Applying that rule:

*Need `_commit(repo)` added* (they call `_add_lib`):

- `test_missing_origin_fails_with_setup_instructions` (line 98)
- `test_unreachable_remote_fails` (line 108)
- `test_missing_origin_carries_add_origin_fix_id` (line 612)
- `test_add_origin_round_trip_clears_the_missing_origin_failure` (line 696)
- the `noremote2` and `badremote2` scenarios inside `test_every_failure_has_a_non_empty_remedy` (lines 199-213)
- the `gitless` repo at the end of that same test (line 225-227) — though its `git` is monkeypatched to raise, so the dirty probe never runs; commit anyway for consistency and to keep the test honest if the patch target ever moves.

*Need NO change* (empty repo, or nothing untracked):

- `test_missing_barn_directory_fails` (line 75) and `test_barn_with_no_library_fails` (line 86) — the latter's `barn/` is an empty dir, invisible to git. **Verify** with `git status --porcelain` rather than trusting this; if it does report dirt, add a commit.
- `test_check_stops_at_the_first_failure` (Task 2's replacement) and `test_require_preconditions_raises_with_the_first_failure` — both use `_init_repo` ALONE with no `_add_lib`, so there is nothing untracked. An earlier draft of this plan listed both as needing a commit; that is wrong, and committing an empty repo would fail (`git commit` with nothing staged is a non-zero exit, and `_commit` runs with `check=True`).
- the `nobarn2`, `emptybarn2`, and `broken3` scenarios inside `test_every_failure_has_a_non_empty_remedy` — same reason.

**One test needs its premise corrected, not just a commit:** `test_every_failure_has_a_non_empty_remedy` (line 171) loops `for failure in report.failures` across six scenarios. That loop still works (a ≤1-item list), but its docstring claims to cover "everything-broken" via the `broken3` scenario, which was only meaningful under collect-all. Update the docstring to say each scenario now yields exactly one failure, and add `assert len(report.failures) == 1` inside the loop so the test actively defends the new invariant instead of silently tolerating either shape.

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -v` after each fixture fix, iterating until every test passes for the reason it was written to test (not accidentally catching the new dirty-tree check instead). A test that now fails on "Working tree is not clean" when it meant to probe something else is the signal that its repo still needs a commit.

Expected final state: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py tests/share_pipeline/test_preconditions.py
git commit -m "feat(share): require a clean working tree before preflight can pass

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 4: New precondition — recognized git host

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py`
- Test: `tests/share_pipeline/test_preconditions.py`

**Interfaces:**
- Consumes: `resolve_host` from `haywire.core.marketstall.host_providers` (already public — `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py:24`); `_ssh_to_https` currently private to `haywire_studio.packaging.share.url` — this task PROMOTES it to a shared location since both `preconditions.py` and `url.py` now need SSH→HTTPS conversion before hostname parsing.
- Produces: nothing new exported beyond `ssh_to_https`.

Slots between "origin configured" and "origin reachable" in `check()` — skips the (network) reachability probe entirely when the host is unrecognized, since a wasted round-trip against a host haywire can't build URLs for isn't useful (per the design's resolution of open question 1).

> **⚠ THE TRAP IN THIS TASK — read before writing any code.**
> A naive `resolve_host(urlsplit(url).hostname)` probe **breaks the entire existing test suite**. Measured against the real code:
>
> | `origin` value | `urlsplit().hostname` | `resolve_host(...)` |
> | --- | --- | --- |
> | `https://github.com/a/b.git` | `'github.com'` | GitHubProvider |
> | `git@gitlab.com:a/b.git` (scp form) | `''` | `None` |
> | `/tmp/pytest-xxx/remote.git` (local path) | `''` | `None` |
>
> **Every `bare_remote` fixture in the repo points `origin` at a local filesystem path.** That is `tests/share_pipeline/test_preconditions.py:43-64` (the `bare_remote` and `project` fixtures, feeding ~25 tests) and `tests/test_share_wizard_ui.py:24-45`. Without the guard below, all of them fail at the new probe with "Host '' is not recognized."
>
> The guard: **host recognition only applies to remotes that name a network host.** A remote with no parseable hostname is a local path (or a transport haywire has no opinion about) and must SKIP this probe entirely — it is not an unrecognized host, it is not-a-host. `ssh_to_https` converts the scp form first, so `git@gitlab.com:a/b.git` correctly yields `gitlab.com` and IS checked.

First, promote `_ssh_to_https` out of `url.py` since it's needed in two places now:

- [ ] **Step 1: Move the function (no new test file — see rationale)**

This is a pure relocation of an already-covered function. `url.py::_ssh_to_https` (lines 54-64) is exercised through `_derive_url` by `tests/test_share_url_derivation.py:56,117,133` and `tests/test_share_readme_markers.py:71,95,119,167`, all of which pass `git@github.com:alice/cool-libs.git` and assert on the derived HTTPS blob URL. **Those tests are the regression gate for this move** (Step 5 runs them). An earlier draft of this plan added three fresh unit tests here asserting `ssh_to_https("git@github.com:user/repo.git") == "https://github.com/user/repo.git"` — that restates the regex against the same three cases the existing tests already drive end-to-end. Do not add them.

The one genuinely new behavior — what happens when there is NO hostname — is tested where it matters, as a precondition probe, in Step 7 below.

- [ ] **Step 2: (merged into Step 1 — no separate red phase for a pure move)**

The red phase for a relocation is "the import fails", which Step 3 resolves in the same edit. Skip straight to Step 3, then use Step 5's existing-test run as the verification that the move preserved behavior.

- [ ] **Step 3: Write minimal implementation — move the function**

In `packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py`, add:

```python
import re


def ssh_to_https(url: str) -> str:
    """Convert an SSH-style git URL to HTTPS; HTTPS URLs pass through unchanged.

    git@github.com:user/repo.git  ->  https://github.com/user/repo.git
    git@gitlab.com:user/repo.git  ->  https://gitlab.com/user/repo.git

    Shared by the share pipeline's precondition check (host recognition) and
    ``haywire_studio.packaging.share.url`` (share-URL derivation) — both need
    to parse a hostname out of whatever ``git remote get-url origin`` returns,
    which may be either form.
    """
    match = re.match(r"^git@([^:]+):(.+)$", url)
    if match:
        host, path = match.groups()
        return f"https://{host}/{path}"
    return url
```

Add `"ssh_to_https"` to `__all__` (line 12).

In `packages/haywire-studio/src/haywire_studio/packaging/share/url.py`, delete the local `_ssh_to_https` function (lines 54-64) and replace its one call site (`_derive_url`, currently `https_url = _ssh_to_https(remote_url)...`) with an import:

```python
from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
```

and change the call from `_ssh_to_https(remote_url)` to `ssh_to_https(remote_url)`.

- [ ] **Step 4: (merged into Step 5 — the existing suites ARE this move's test)**

- [ ] **Step 5: Run the existing suites that cover `_ssh_to_https` through `_derive_url`**

```bash
uv run pytest tests/test_share_url_derivation.py tests/test_share_readme_markers.py -v
```

Expected: all PASS. These drive `git@github.com:alice/cool-libs.git` through the moved function and assert on the derived blob URL (`test_share_url_derivation.py:56,117,133`; `test_share_readme_markers.py:71,95,119,167`), plus `test_share_save_unknown_host_warns_with_config_snippet` for the None-provider branch. A failure here means the move changed behavior — fix it before continuing, since every later step assumes this function is sound.

- [ ] **Step 6: Commit the extraction**

```bash
git add packages/haywire-core/src/haywire/core/marketstall/host_providers/__init__.py packages/haywire-studio/src/haywire_studio/packaging/share/url.py
git commit -m "refactor(share): promote ssh_to_https to host_providers, shared by url.py and preconditions.py

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 7: Write the failing test for the new host-recognition precondition**

Add to `tests/share_pipeline/test_preconditions.py`:

Three tests. **None of them touch the network** — a real `git ls-remote` against `github.com` would put a DNS round-trip (or a 60s timeout in a sandboxed CI) into the fast unit suite, which `.insights/project_slow_test_outliers.md` names as the single most common cause of multi-second tests in this repo.

```python
def _repo_with_origin(tmp_path: Path, name: str, origin: str) -> Path:
    """A committed, clean repo with one barn library and *origin* set.

    Local helper: every host-recognition test needs exactly this shape, and
    the clean-tree probe (Task 3) means the commit is mandatory, not optional.
    """
    repo = tmp_path / name
    _init_repo(repo)
    _add_lib(repo)
    subprocess.run(
        ["git", "remote", "add", "origin", origin], cwd=repo, check=True, capture_output=True
    )
    _commit(repo)
    return repo


def test_unrecognized_host_fails_with_the_config_snippet(tmp_path: Path) -> None:
    """A self-hosted domain with no [[hosts]] entry fails here, and the remedy
    is the exact TOML to paste — the act-modal (Task 6) writes this verbatim.

    It also does NOT reach the reachability probe: that round-trip would be
    wasted against a host haywire cannot build URLs for regardless. Proven by
    the message being about recognition, not reachability, even though this
    origin is equally unreachable.
    """
    repo = _repo_with_origin(tmp_path, "unknownhost", "https://git.example-corp.internal/team/repo.git")

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    assert "git.example-corp.internal" in report.failure.message
    assert "not recognized" in report.failure.message.lower()
    assert "Cannot reach origin" not in report.failure.message
    assert "[[hosts]]" in report.failure.remedy
    assert 'hostname = "git.example-corp.internal"' in report.failure.remedy
    assert report.failure.kind == "act"
    assert report.failure.fix_id == "add_host_config"
    # The act-modal reads the hostname from lib_dir rather than re-parsing
    # the remedy text — this is that contract.
    assert report.failure.lib_dir == "git.example-corp.internal"


def test_local_path_origin_skips_host_recognition_entirely(tmp_path: Path, bare_remote: Path) -> None:
    """THE REGRESSION GUARD for this task. A filesystem-path origin has no
    hostname at all (`urlsplit('/tmp/x.git').hostname == ''`), and must be
    treated as not-a-host — NOT as an unrecognized host.

    Every bare_remote-backed fixture in this repo (and in
    tests/test_share_wizard_ui.py) points origin at a local path, so getting
    this wrong fails ~25 otherwise-unrelated tests with
    "Host '' is not recognized."
    """
    repo = _repo_with_origin(tmp_path, "localpath", str(bare_remote))

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is True


def test_recognized_host_passes_through_to_the_reachability_probe(
    tmp_path: Path, monkeypatch
) -> None:
    """A recognized host moves PAST this probe to reachability.

    resolve_host is stubbed rather than pointing at real github.com: the point
    is the control flow after recognition succeeds, and the origin is a
    nonexistent local path so the next probe fails fast and offline.
    """
    from haywire_studio.packaging.share.pipeline.steps import preconditions as precond_module

    monkeypatch.setattr(precond_module, "resolve_host", lambda hostname: object())

    repo = _repo_with_origin(tmp_path, "recognized", "https://git.example-corp.internal/team/repo.git")

    report = SharePipeline(repo).check_preconditions()

    assert report.ok is False
    assert "not recognized" not in report.failure.message.lower()
    assert "Cannot reach origin" in report.failure.message
```

The stub in the third test requires `preconditions.py` to import `resolve_host` as a **module-level name** (`from ... import resolve_host`, called as `resolve_host(...)`) so `monkeypatch.setattr(precond_module, "resolve_host", ...)` intercepts it. Step 9's implementation does exactly that — do not switch it to `host_providers.resolve_host(...)`.

- [ ] **Step 8: Run tests to verify they fail**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -k "unrecognized_host or local_path_origin or recognized_host" -v`

Expected:

- `test_unrecognized_host_fails_with_the_config_snippet` — FAIL (no such probe yet; the run instead fails at reachability or passes).
- `test_local_path_origin_skips_host_recognition_entirely` — **PASS already**, and that is correct and intended. It is a regression guard: it must pass before the change and still pass after. If it ever fails during Step 10, the guard branch is missing or wrong.
- `test_recognized_host_passes_through_to_the_reachability_probe` — PASS already (nothing rejects the host yet). Same character: it pins behavior the new probe must not break.

This requires `preconditions.py` to import `resolve_host` as a module-level name (`from haywire.core.marketstall.host_providers import resolve_host` then call `resolve_host(...)`, not `host_providers.resolve_host(...)`) so `monkeypatch.setattr(precond_module, "resolve_host", ...)` can intercept it — confirm this import style in Step 9's implementation.

- [ ] **Step 9: Write minimal implementation**

In `preconditions.py`, add to the module-level imports (top of file, beside the existing `from haywire_studio...` block — NOT inside the function, so the test's `monkeypatch.setattr` can intercept `resolve_host`):

```python
from urllib.parse import urlsplit

from haywire.core.marketstall.host_providers import resolve_host, ssh_to_https
```

Add a new probe between the "origin configured" block and the "origin reachable" block (i.e., right after `remote_url = remote.stdout.strip()` and before `reachable = git_remote(...)`):

```python
    remote_url = remote.stdout.strip()

    # Host recognition applies only to remotes that NAME a network host.
    # `git remote get-url` legitimately returns a local filesystem path
    # (`/srv/git/foo.git`, a sibling clone, a test's bare repo), for which
    # urlsplit() yields an empty hostname. That is not-a-host, not an
    # unrecognized host: there is no config entry that would make it
    # recognizable and nothing for the marketstall to build a browser URL
    # from, so the probe has no opinion and skips. ssh_to_https() runs first
    # so the scp form (git@host:owner/repo) resolves to its real hostname
    # rather than falling into this same empty-hostname branch.
    https_url = ssh_to_https(remote_url).removesuffix(".git").rstrip("/")
    hostname = (urlsplit(https_url).hostname or "").lower()
    if hostname and resolve_host(hostname) is None:
        return PreconditionsReport(
            failures=[
                PreconditionFailure(
                    message=f"Host '{hostname}' is not recognized.",
                    remedy=(
                        f"Add this to ~/.haywire/config.toml:\n\n"
                        f"[[hosts]]\n"
                        f'hostname = "{hostname}"\n'
                        f'provider = "gitlab"   # or "github"\n\n'
                        f"This only teaches haywire how to build browser-friendly URLs for "
                        f"this host — it has nothing to do with push access."
                    ),
                    kind="act",
                    fix_id="add_host_config",
                    fix_label="Add host to config.toml",
                    # lib_dir carries the fix's SUBJECT: the hostname here, a
                    # barn library directory for strip_os. Reused rather than
                    # adding a fourth near-identical field, and it keeps the
                    # act-modal from re-parsing `remedy` prose to recover it.
                    lib_dir=hostname,
                )
            ],
            remote_url=remote_url,
            barn_libraries=barn_libraries,
        )

    reachable = git_remote(["ls-remote", "--symref", "origin", "HEAD"], cwd=pipeline.repo_root, timeout=60.0)
```

Widen `lib_dir`'s docstring in `results.py` (currently "the affected barn library's directory", lines 24-26) to describe it as the fix's subject — a barn library directory for `strip_os`, a hostname for `add_host_config` — keeping the existing note about why it is a `str` and not a `Path`.

**The `hostname and` guard is load-bearing** — see this task's opening warning. Dropping it turns every local-path `origin` into a "Host '' is not recognized." failure and breaks ~25 existing tests across two files.

(Remove the old `reachable = git_remote(...)` line that immediately followed `remote_url = remote.stdout.strip()` before this edit — it moves to after the new host-check block, unchanged otherwise.)

Note `fix_id="add_host_config"` is a NEW fix_id — the act-modal for this one (Task 6) does NOT dispatch through `_PRECONDITION_FIXES`/`apply_precondition_fix` like `add_origin`/`strip_os` do, because "ask permission, write `~/.haywire/config.toml`" is a home-directory file write outside the repo, a different concern than `_PRECONDITION_FIXES`'s repo-mutation handlers. Task 6 handles `add_host_config` as a special case in the modal layer directly, not by adding a fourth entry to `fixes.py`'s dispatch table. Document this explicitly as a code comment when Task 6 is implemented.

- [ ] **Step 10: Run tests to verify they pass**

Run: `uv run pytest tests/share_pipeline/test_preconditions.py -k "unrecognized_host or local_path_origin or recognized_host" -v`
Expected: PASS (3 tests). `test_local_path_origin_skips_host_recognition_entirely` passing here is the proof the guard branch works.

- [ ] **Step 11: Run the full precondition suite AND the wizard suite**

```bash
uv run pytest tests/share_pipeline/ tests/test_share_wizard_ui.py -v
```

Expected: all PASS. The wizard suite is included deliberately, not as belt-and-braces: its `project` fixture (`tests/test_share_wizard_ui.py:24-45`) also points `origin` at a local bare repo, so it is the second population that a missing `hostname and` guard would take down. If anything there fails with "not recognized", the guard is wrong — fix Step 9, do not touch the fixture.

Note the wizard fixture already commits and pushes (lines 42-44), so Task 3's clean-tree probe is satisfied there without changes.

- [ ] **Step 12: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/preconditions.py tests/share_pipeline/test_preconditions.py
git commit -m "feat(share): recognize-host precondition, skips reachability probe when unknown

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 5: `url.py`'s standalone unknown-host warning stays as-is (verification only, no code change)

**Files:**
- Test: `tests/test_share_url_derivation.py` (read-only verification)

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new.

Per the settled design ("what it does NOT do"), `url.py::_derive_url`'s own unknown-host warning is intentionally NOT removed or delegated to the new precondition — it serves the standalone `derive_share_url_only` path (`haywire share`, no `--save`, re-deriving the URL after preflight already passed once, potentially in a separate process/invocation). This task is a verification step, not a code change: confirm `_unknown_host_warning` in `url.py` still exists and its tests still pass after Task 4's `_ssh_to_https` extraction.

- [ ] **Step 1: Verify `_unknown_host_warning` and its call site survived the Task 4 extraction unchanged**

Run: `grep -n "_unknown_host_warning" packages/haywire-studio/src/haywire_studio/packaging/share/url.py`
Expected output: two lines — the function definition and its one call site inside `_derive_url`, both intact (Task 4 only touched `_ssh_to_https`, a different function in the same file).

- [ ] **Step 2: Run its existing tests**

Run: `uv run pytest tests/test_share_url_derivation.py -k "unknown_host" -v`
Expected: PASS (`test_share_save_unknown_host_warns_with_config_snippet`)

- [ ] **Step 3: No commit needed — this task makes no code change.**

If Step 1 or 2 surfaces a problem, fix it as part of Task 4 and re-run that task's commit instead of committing separately here.

---

## Task 6: Remedy-modal layer — inform and act shapes, wired into the wizard

**Files:**
- Create: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/remedy_modal.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/_state.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/chrome.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py`
- Test: `tests/test_share_wizard_ui.py`

**Interfaces:**
- Consumes: `PreconditionFailure` (with `.kind`, from Task 1); `hui._copy_button` pattern (packages/haywire-core/src/haywire/ui/elements/elements.py:991 — currently module-private, this task either imports it directly via the private name within the same package boundary or duplicates the three-line pattern locally — prefer duplicating locally since `_copy_button` is prefixed `_` specifically to signal "internal to elements.py", and reaching across that boundary would be the kind of undeclared-dependency pattern CLAUDE.md's traps warn about); `hui.dialog_card`, `hui.dialog_actions`, `hui.input_field` (all public); `SharePipeline.apply_precondition_fix` (existing, for `add_origin`/`strip_os`); a new `add_host_config` handler (local to this file, NOT added to `fixes.py`'s `_PRECONDITION_FIXES` — see Task 4 Step 9's note).
- Produces: `show_remedy_modal(wizard: ShareWizard, failure: PreconditionFailure, *, on_restart: Callable[[], None]) -> None` — opens a `ui.dialog`, renders inform or act shape based on `failure.kind`, `on_restart` is called when the user dismisses (inform) or after a successful act-fix confirmation.

This task deletes the old inline fix-loop (`_render_fix`, `add_origin`'s inline `ui.input`, `advance_from_preconditions_fix`) and replaces it with a modal. The wizard's OWN popup stays open underneath (matching the design: "Restart Wizard" re-runs preflight in the SAME wizard instance, not a fresh one) — only a `ui.dialog` opens on top.

### Two corrections to the obvious approach — read both before writing code

**(a) `error_detail` is the WRONG seam. Do not use it.**

An earlier draft wired the modal into `show_step_flow(..., error_detail=...)`. That does not work, for three independent reasons visible in `packages/haywire-core/src/haywire/ui/components/stepper/chrome.py`:

1. `_render()` (line 67-73) calls `render_error` on **every** re-render. `error_detail` returning a freshly `open()`ed dialog means a new dialog every redraw, stacking up.
2. `render_error` (line 126) invokes `error_detail` **inside** the error banner's `ui.column()` slot. `body.clear()` on the next render deletes that slot out from under the dialog — the exact "redraw deletes handler slot" trap in `.insights/feedback_nicegui_redraw_deletes_handler_slot.md`.
3. `render_error` renders its own **Retry button** (line 132-136) regardless of what `error_detail` returns. The user would get "Retry" *and* "Restart Wizard" for one failure.

**The seam instead: a one-shot `pending_modal` on the wizard, drained by the panel.** `_state.py` records *that a modal is owed* (pure data, no NiceGUI — keeps the state machine testable, which is the whole point of the `_state.py`/`panels.py` split documented at the top of `_state.py`). `_panel_preconditions` drains it during its own render and opens the dialog. Draining makes it one-shot, so a redraw does not reopen it.

Because `error_detail` goes away entirely, `chrome.py`'s `_render_precondition_failures` is **deleted**, not rewritten, and `show_step_flow` is called without the `error_detail=` argument. The shared chrome then renders `flow.error` as its plain one-line label with a Retry button — which is correct and wanted for the *non*-preconditions steps that Task 7 does not convert.

**(b) `tests/test_share_wizard_ui.py` cannot test modals. It is not a browser test file.**

Its docstring: *"The share wizard's state machine. UI rendering is smoke-tested only."* `_wizard()` (line 48-53) builds `ShareWizard(..., popup=None)` and tests `await` the `advance_from_*` methods. There is no `user` fixture, no NiceGUI client, no Playwright. **Every test below asserts on state (`wizard.pending_modal`, `wizard.precondition_failure`, on-disk effects), never on rendered elements.** The dialog-rendering code itself is covered only by the existing render smoke test — that is the deliberate, pre-existing posture of this file, not a gap this plan introduces.

If someone later wants true modal-interaction coverage, it belongs in `tests/ui/harness/` with `@pytest.mark.browser` (see `.insights/project_playwright_asyncio_order_trap.md` for why placement matters). **That is out of scope here** — do not add a Playwright test as part of this task.

- [ ] **Step 1: Write the failing test for modal dispatch (state-level)**

Add to `tests/test_share_wizard_ui.py`, near the existing precondition tests:

```python
@pytest.mark.anyio
async def test_precondition_failure_queues_an_inform_modal(tmp_path: Path) -> None:
    """A failure the wizard cannot repair queues a modal request carrying the
    failure itself. The panel drains it on next render (rendering is smoke-
    tested only in this file — see the module docstring)."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    repo = tmp_path / "broken"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.step == "preconditions"
    assert wizard.precondition_failure is not None
    assert wizard.precondition_failure.kind == "inform"
    assert wizard.pending_modal is not None


@pytest.mark.anyio
async def test_draining_the_pending_modal_clears_it(tmp_path: Path) -> None:
    """One-shot: the panel drains on render, so a redraw cannot reopen the
    dialog (the failure itself stays on the wizard for the modal to read)."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    repo = tmp_path / "broken2"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.take_pending_modal() is not None
    assert wizard.take_pending_modal() is None
    assert wizard.pending_modal is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_share_wizard_ui.py -k "pending_modal" -v`
Expected: FAIL — `AttributeError: 'ShareWizard' object has no attribute 'pending_modal'`.

- [ ] **Step 3: Write minimal implementation — `remedy_modal.py`**

```python
"""Remedy modals for Share Wizard preflight failures.

Every ``check_preconditions()`` failure (Task 1-4) is one of two shapes:

- ``kind == "inform"``: nothing the wizard can do about it — message, remedy
  text, and a Restart Wizard button. No fix affordance.
- ``kind == "act"``: the wizard CAN repair this in place — same content plus
  a button that performs the fix. Success re-runs preflight from the top
  automatically is NOT what happens: per the settled design, EVERY act-modal
  ends with an explicit "Restart Wizard" click, even on a successful fix —
  no auto-continue. Preflight is cheap enough that re-running it from #0 is
  free, and an explicit click keeps the user in control of when the wizard
  re-engages rather than silently reacting to a background git operation.

A third shape (rollback, for mid-pipeline failures at steps 2-6) is handled
by :func:`show_rollback_modal` in the same module — distinct from these two
because it also has to trigger a working-tree revert as a side effect of
opening, not just report.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire_studio.packaging.share.pipeline import PreconditionFailure, ShareError

from ._state import ShareWizard


def _copy_button(value: str) -> ui.button:
    """Copy-to-clipboard button, matching hui's internal ``_copy_button`` pattern
    (elements.py:991) — duplicated locally rather than imported since that name
    is module-private to ``elements.py`` by convention."""
    return (
        ui.button(
            icon="content_copy",
            on_click=lambda: ui.run_javascript(f"navigator.clipboard.writeText({_json.dumps(value)})"),
        )
        .props("flat round dense size=xs")
        .tooltip("Copy to clipboard")
    )


def show_remedy_modal(
    wizard: ShareWizard,
    failure: PreconditionFailure,
    *,
    on_restart: Callable[[], None],
) -> None:
    """Open the inform or act remedy modal for one preflight failure."""
    with ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
        ui.label(failure.message).classes("text-sm hw-text-danger whitespace-pre-line")
        if failure.remedy:
            ui.label(failure.remedy).classes("text-xs hw-text-dim font-mono whitespace-pre-line")

        error_label = ui.label("").classes("text-xs hw-text-danger")

        if failure.kind == "act":
            _render_act_body(wizard, failure, error_label)

        def _restart() -> None:
            dialog.close()
            on_restart()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Restart Wizard", on_click=_restart).props("flat dense").style(
                "color: var(--hw-positive);"
            )
    dialog.open()


def _render_act_body(wizard: ShareWizard, failure: PreconditionFailure, error_label: ui.label) -> None:
    """The extra widgets an act-kind failure needs, above the Restart Wizard row."""
    fix_id = failure.fix_id
    if fix_id == "add_origin":
        url_input = hui.input_field(placeholder="git remote URL").classes("w-full mt-2")
        fix_button = ui.button("Add origin remote").props("flat dense").style("color: var(--hw-positive);")
        fix_button.set_enabled(False)
        url_input.on_value_change(lambda: fix_button.set_enabled(bool((url_input.value or "").strip())))

        def _apply_add_origin() -> None:
            try:
                wizard.pipeline.apply_precondition_fix("add_origin", url=(url_input.value or "").strip())
            except ShareError as exc:
                error_label.text = str(exc)
                return
            error_label.text = "Done — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_add_origin)

    elif fix_id == "strip_os":
        fix_button = (
            ui.button(failure.fix_label or "Fix").props("flat dense mt-2").style("color: var(--hw-positive);")
        )

        def _apply_strip_os() -> None:
            try:
                wizard.pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir or "")
            except ShareError as exc:
                error_label.text = str(exc)
                return
            error_label.text = "Done — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_strip_os)

    elif fix_id == "add_host_config":
        # Not dispatched through _PRECONDITION_FIXES (fixes.py): this writes
        # ~/.haywire/config.toml, a file outside the repo the pipeline owns —
        # a different concern than the repo-mutation handlers in fixes.py.
        ui.label("Add this entry?").classes("text-xs hw-text-dim mt-2")
        with ui.row().classes("items-center gap-1"):
            ui.label(failure.remedy).classes("text-xs font-mono whitespace-pre-line flex-1")
            _copy_button(failure.remedy)
        fix_button = (
            ui.button("Write to ~/.haywire/config.toml")
            .props("flat dense mt-2")
            .style("color: var(--hw-positive);")
        )

        def _apply_add_host_config() -> None:
            # hostname arrives as data on the failure (lib_dir), not parsed
            # back out of the remedy prose — see Step 7.
            hostname = failure.lib_dir or ""
            if not hostname:
                error_label.text = "No hostname on this failure — cannot write the entry."
                return
            try:
                written = append_host_config(hostname)
            except OSError as exc:
                error_label.text = f"Could not write the config: {exc}"
                return
            error_label.text = f"Written to {written} — click Restart Wizard to re-check."
            fix_button.set_enabled(False)

        fix_button.on_click(_apply_add_host_config)
```

`append_host_config` is defined in Step 7 (extracted so it is testable without a browser). `Path` is then unused in this module unless something else needs it — drop the `from pathlib import Path` import if ruff flags it. The `import json as _json` at the top IS still needed, by `_copy_button`.

Now wire it into the wizard. In `_state.py`, delete `advance_from_preconditions_fix` (lines 180-211) entirely — it is superseded by `remedy_modal.py`'s direct calls to `apply_precondition_fix`. Simplify `fail()` (lines 151-160):

```python
    def fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step.

        ``PreconditionsError`` carries a single structured ``PreconditionFailure``
        — stashed separately so the wizard can open a remedy modal instead of
        the shared chrome's generic one-line error banner. ``pending_modal`` is
        the one-shot request the panel drains on its next render; see
        :meth:`take_pending_modal`.
        """
        super().fail(exc)
        self.precondition_failure = exc.failure if isinstance(exc, PreconditionsError) else None
        if self.precondition_failure is not None:
            self.pending_modal = self.precondition_failure
```

And its type declaration (line 71): `self.precondition_failures: list[PreconditionFailure] | None = None` becomes two fields:

```python
        self.precondition_failure: PreconditionFailure | None = None
        # One-shot: set by fail(), drained by _panel_preconditions on its next
        # render. Kept separate from `precondition_failure` (which persists so
        # the open modal can read it) precisely so a redraw does not reopen the
        # dialog — see .insights/feedback_nicegui_redraw_deletes_handler_slot.md.
        self.pending_modal: PreconditionFailure | None = None
```

Add the drain method beside `retry()`:

```python
    def take_pending_modal(self) -> PreconditionFailure | None:
        """Return the queued modal request, clearing it. One-shot by design.

        Pure state, no NiceGUI: the panel calls this during its own render and
        opens the dialog itself, keeping this class testable without a browser
        (the split this module's docstring describes).
        """
        pending, self.pending_modal = self.pending_modal, None
        return pending
```

`retry()` must clear both (it currently clears `precondition_failures`, line 149):

```python
    def retry(self) -> None:
        super().retry()
        self.precondition_failure = None
        self.pending_modal = None
```

Add `.failure` property to `PreconditionsError` in `errors.py` matching `PreconditionsReport.failure` from Task 1:

```python
class PreconditionsError(ShareError):
    """The (single) step-1 precondition failure. See PreconditionFailure.kind
    for the two ways the wizard's remedy modal presents it."""

    def __init__(self, failures: list[PreconditionFailure]) -> None:
        self.failures = list(failures)
        lines = ["Cannot share this project:"]
        for failure in self.failures:
            lines.append(f"  - {failure.message}")
            if failure.remedy:
                for remedy_line in failure.remedy.splitlines():
                    lines.append(f"      {remedy_line}")
        super().__init__("\n".join(lines))

    @property
    def failure(self) -> PreconditionFailure | None:
        return self.failures[0] if self.failures else None
```

In `chrome.py`, **delete** `_render_precondition_failures` (lines 90-108) outright and drop the `error_detail=` argument from the `show_step_flow(...)` call (line 85) — see correction (a) above for why that hook cannot carry a modal. Also remove `_render_fix` from the `from .panels import (...)` block (lines 20-35), and remove the now-unused `ui` and `Callable` imports if nothing else in the file uses them (`grep -n "ui\.\|Callable" chrome.py` after the edit — `Callable` is still used by `show_share_wizard`'s `on_done` parameter, `ui` likely is not).

`chrome.py` gains no import of `remedy_modal` — the panel owns that, not the popup shell.

In `panels.py`, delete `_render_fix` (lines 20-61) entirely and drain the modal at the top of `_panel_preconditions` (line 63):

```python
def _panel_preconditions(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    # Drained here, not in chrome's error banner: the banner re-renders on
    # every redraw and its slot is cleared underneath any dialog opened from
    # it. take_pending_modal() is one-shot, so the dialog opens exactly once
    # per failure no matter how often this panel re-renders.
    pending = wizard.take_pending_modal()
    if pending is not None:
        def _restart() -> None:
            wizard.retry()
            rerender()

        show_remedy_modal(wizard, pending, on_restart=_restart)

    ui.label(
        "Checks that git is available, that barn/ holds at least one library, "
        "and that origin is set and reachable."
    ).classes("text-xs hw-text-dim")
    ...
```

Add `from .remedy_modal import show_remedy_modal` to `panels.py`'s imports. Keep the `PreconditionFailure` import only if something else still uses it — check with `grep -n PreconditionFailure panels.py` after deleting `_render_fix`; if `_render_fix` was its only consumer, remove it (ruff F401 will flag it otherwise).

Update `_panel_preconditions`'s descriptive label too, since the checks changed: it should now read *"Checks that your working tree is clean, that git is available, that barn/ holds at least one library, and that origin is set, recognized, and reachable."*

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_share_wizard_ui.py -k "pending_modal" -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Refurbish the five existing `advance_from_preconditions_fix` tests**

`advance_from_preconditions_fix` is deleted, so `tests/test_share_wizard_ui.py:703-810` no longer compiles. **Do not simply delete these five tests** — the fix→recheck round-trip they cover still exists, just at the pipeline level now (the modal's button calls `pipeline.apply_precondition_fix` directly, then the user clicks Restart Wizard, which is `retry()` + `advance_from_preconditions()`). Rewrite each to drive that sequence:

| Existing test (line) | Becomes |
| --- | --- |
| `test_strip_os_fix_reaches_checked_with_no_error` (703) | apply `strip_os` via pipeline, then `advance_from_preconditions()` → asserts `step == "checked"`, `precondition_failure is None` |
| `test_add_origin_fix_against_reachable_remote_reaches_checked` (724) | same shape with `add_origin` + the pushed local remote |
| `test_add_origin_fix_with_bad_url_swaps_in_the_reachability_failure` (751) | after the fix + re-check, asserts the failure is now the reachability one, `kind == "inform"` |
| `test_fix_success_never_advances_past_checked` (779) | unchanged intent: after fix + re-check, `step == "checked"` and `drift_report is None` |
| `test_failing_fix_is_caught_and_rendered_without_crashing` (795) | `pipeline.apply_precondition_fix("add_origin", ...)` on a repo that already has one raises `PreconditionsError` — assert the raise directly; the "rendered without crashing" half is gone with the wizard method |

Worked example for the first:

```python
@pytest.mark.anyio
async def test_strip_os_fix_then_recheck_reaches_checked(os_project: Path) -> None:
    """The act-modal's contract, minus the dialog: take fix_id/lib_dir straight
    off the failure (no string-parsing), apply it, then Restart Wizard —
    which is retry() + advance_from_preconditions() — lands on 'checked'."""
    wizard = _wizard(os_project)
    await wizard.advance_from_preconditions()

    failure = wizard.precondition_failure
    assert failure is not None
    assert failure.fix_id == "strip_os"
    assert failure.kind == "act"
    assert failure.lib_dir is not None

    wizard.pipeline.apply_precondition_fix("strip_os", lib_dir=failure.lib_dir)

    wizard.retry()
    await wizard.advance_from_preconditions()

    assert wizard.step == "checked"
    assert wizard.error is None
    assert wizard.precondition_failure is None
```

**Fixture cascade in this file too — verified, one fixture needs a fix:**

- `noremote_project` (line 681-698) already commits its seed (lines 695-696). No change.
- `project` (line 24-45) already commits AND pushes. No change.
- **`os_project` (line 672-678) is broken by Task 3** and must be fixed. It takes the committed `project`, then appends the invalid `[tool.haywire].os` block to `pyproject.toml` *after* the commit — leaving the tree dirty. The clean-tree probe now fires first, so every test built on it would report "Working tree is not clean" instead of the os failure they exist to test. Add a commit after the mutation:

```python
@pytest.fixture
def os_project(project: Path) -> Path:
    """`project`, but with an invalid `[tool.haywire].os` declaration.

    Committed after the mutation: the clean-tree precondition runs before the
    manifest probe, so an uncommitted edit here would mask the very failure
    these tests are about.
    """
    pyproject = project / "barn" / "haybale-alpha" / "pyproject.toml"
    pyproject.write_text(pyproject.read_text() + '\n[tool.haywire]\nos = ["macos", "other"]\n')
    subprocess.run(["git", "add", "-A"], cwd=project, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "invalid os"], cwd=project, check=True, capture_output=True
    )
    return project
```

The same "mutate a committed fixture, then commit again" pattern applies to any other test in this file that edits files after the `project` fixture returns — grep for `write_text` inside test bodies and check each.

- [ ] **Step 6: Run the refurbished tests**

Run: `uv run pytest tests/test_share_wizard_ui.py -k "strip_os or add_origin or fix" -v`
Expected: all PASS. These exercise the fix→recheck round-trip at the pipeline level; the dialog that invokes it is not under test here (see correction (b)).

- [ ] **Step 7: Extract the `add_host_config` writer so it is testable at all**

The other two fixes route through `pipeline.apply_precondition_fix`, which has its own pipeline-level tests. `add_host_config` does not (it writes outside the repo — see Task 4 Step 9). If its logic lives inline in a NiceGUI click handler, **nothing in this repo's fast suite can test it**, since this file cannot click buttons.

So pull the write out of the handler into a plain function in `remedy_modal.py`, and revise Step 3's `_apply_add_host_config` to call it:

```python
def append_host_config(hostname: str, provider: str = "gitlab") -> Path:
    """Append a ``[[hosts]]`` entry for *hostname* to the user's config.

    Separate from the click handler so it is testable without a browser, and
    routed through ``_user_config_path()`` — the location's single source of
    truth, already documented there as "wrapped for test monkeypatching"
    (host_providers/config.py:22). Do not rebuild ``Path.home() / ...`` here.
    """
    from haywire.core.marketstall.host_providers.config import _user_config_path

    path = _user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f'\n[[hosts]]\nhostname = "{hostname}"\nprovider = "{provider}"\n')
    return path
```

**Also drop the regex.** Step 3's draft handler recovers the hostname by running `re.search(r'hostname = "([^"]+)"', failure.remedy)` — parsing one file's prose in another file, which breaks silently the first time the remedy's wording changes.

Carry it as data instead, on `PreconditionFailure.lib_dir`. That field is already the generic "which subject does this fix apply to" string (a barn directory for `strip_os`; documented as such in `results.py:24-26`), it is unused by `add_host_config`, and it is already `str | None` for exactly this serializability reason. **Amend Task 4 Step 9's failure construction** to add:

```python
                    # lib_dir carries the fix's subject: the hostname here, a
                    # barn directory for strip_os. Reused rather than adding a
                    # fourth near-identical field, and it keeps the modal from
                    # having to re-parse `remedy` prose to recover it.
                    lib_dir=hostname,
```

and widen that field's docstring in `results.py` from "the affected barn library's directory" to "the subject of the fix — a barn library directory for `strip_os`, a hostname for `add_host_config`".

The handler then reads `append_host_config(failure.lib_dir or "")`, with no regex anywhere.

Test it directly (state + on-disk, no UI):

```python
def test_append_host_config_writes_a_hosts_entry(tmp_path: Path, monkeypatch) -> None:
    """The add_host_config fix writes a [[hosts]] entry the resolver then honors.

    Asserted through load_self_hosted_hosts() rather than by string-matching
    the file: what matters is that resolve_host() will now recognize the host,
    not the exact bytes written.
    """
    from haywire.core.marketstall.host_providers import config as host_config
    from haybale_marketplace.editors._share_wizard.remedy_modal import append_host_config

    cfg = tmp_path / ".haywire" / "config.toml"
    monkeypatch.setattr(host_config, "_user_config_path", lambda: cfg)

    append_host_config("git.example-corp.internal")

    assert host_config.load_self_hosted_hosts(cfg) == {"git.example-corp.internal": "gitlab"}
```

Note the monkeypatch target: `append_host_config` imports `_user_config_path` **inside** the function body (as written above), so patching the attribute on the `config` module works. Keep that import inside the function for exactly this reason.

Run: `uv run pytest tests/test_share_wizard_ui.py -k "append_host_config" -v`
Expected: PASS.

- [ ] **Step 8: Run the full wizard UI test suite**

Run: `uv run pytest tests/test_share_wizard_ui.py -v`
Expected: all PASS. Any test still referencing the deleted names must be fixed as part of this step — grep first:

```bash
grep -n "advance_from_preconditions_fix\|_render_fix\|precondition_failures" tests/test_share_wizard_ui.py
```

Expected hits before this step: the five tests at lines 703-810 (Step 5 rewrites them) and `precondition_failures` at lines 132-135, 710-711, 731-732, 757, 782, 806-810 (rename to the singular `precondition_failure` and drop the list indexing). Zero hits after.

Also grep the non-test tree for the same names, since `_state.py` is not the only consumer:

```bash
grep -rn "advance_from_preconditions_fix\|precondition_failures\|_render_fix" barn/ packages/ --include="*.py"
```

Expected after this step: no output.

- [ ] **Step 9: Lint and format check**

Run: `uv run ruff check barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/ packages/haywire-studio/src/haywire_studio/packaging/share/`
Run: `uv run ruff format --check barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/ packages/haywire-studio/src/haywire_studio/packaging/share/`
Expected: clean. Fix any issues with `uv run ruff format <path>` and re-check.

- [ ] **Step 10: Commit**

```bash
git add barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/ packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/errors.py tests/test_share_wizard_ui.py
git commit -m "feat(share): remedy-modal layer replaces the inline preflight fix/recheck loop

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 7: Rollback for mid-pipeline failures (steps 2-6)

**Files:**
- Create: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/rollback.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/pipeline.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/remedy_modal.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/_state.py`
- Test: `tests/share_pipeline/test_rollback.py` (new)

**Interfaces:**
- Consumes: `git` helper (local-only, since revert never talks to a remote).
- Produces: `revert_working_tree(pipeline: SharePipeline) -> None` — raises `ShareError` subclass on failure (the revert itself failing is its own unrecoverable case, reported plainly, no further auto-action).
- `SharePipeline.rollback() -> None` — thin wrapper calling `revert_working_tree(self)`.

Safe specifically because Task 3's clean-tree precondition guarantees nothing existed to lose before this run started. Whole-repo scope (`git checkout -- .` + `git clean -fd`), matching the clean-tree check's own scope, per the settled design.

> **⚠ TWO THINGS THE IMPLEMENTER WILL HIT IMMEDIATELY.**
>
> **1. A repo hook blocks these commands from the agent's shell.** `.claude/hooks/block-dangerous-git.sh` refuses any Bash command matching `git clean -fd`, `git clean -f`, `git checkout \.`, `git restore \.`, `reset --hard`, or `git push`. This does **not** affect the product code — `revert_working_tree` runs them through the `git()` helper inside a Python subprocess, which the hook never sees — but it does mean:
>
> - You cannot hand-verify the rollback with an ad-hoc `git clean -fd` in a scratch repo. Verify through `pytest tests/share_pipeline/test_rollback.py` instead; the tests call the real function.
> - Do not "work around" the hook. If you genuinely need a manual check, ask the user.
>
> **2. `git clean -fd` does NOT remove gitignored files** (no `-x` flag), which is correct and deliberate here: `.venv/`, `__pycache__/`, and build output must survive a rollback. It DOES remove untracked-and-unignored files — including any the *user* created between preflight and the failure. That window is the one real gap in the clean-tree safety argument; it is accepted (the window is seconds long and the wizard is modal throughout), but do not widen the scope to `-x` on the theory that "cleaner is safer". It is not.

- [ ] **Step 1: Write the failing test**

Create `tests/share_pipeline/test_rollback.py`:

```python
"""Tests for reverting the working tree after a mid-pipeline failure."""

import subprocess
from pathlib import Path

import pytest

from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline
from haywire_studio.packaging.share.pipeline.steps.rollback import revert_working_tree

pytestmark = pytest.mark.unit


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=path, check=True, capture_output=True)


def _commit(repo: Path, message: str = "init") -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)


def test_revert_discards_a_modified_tracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    tracked = repo / "tracked.txt"
    tracked.write_text("original")
    _commit(repo)

    tracked.write_text("modified by a failed pipeline run")
    revert_working_tree(SharePipeline(repo))

    assert tracked.read_text() == "original"


def test_revert_removes_a_newly_created_untracked_file(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    _init_repo(repo)
    (repo / "seed.txt").write_text("seed")
    _commit(repo)

    new_file = repo / "written_by_docs_step.md"
    new_file.write_text("generated during a failed run")
    revert_working_tree(SharePipeline(repo))

    assert not new_file.exists()


def test_revert_leaves_committed_history_untouched(tmp_path: Path) -> None:
    repo = tmp_path / "repo3"
    _init_repo(repo)
    (repo / "a.txt").write_text("a")
    _commit(repo, "first")

    (repo / "b.txt").write_text("uncommitted during a failed run")
    revert_working_tree(SharePipeline(repo))

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "first" in log
    assert len(log.strip().splitlines()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/share_pipeline/test_rollback.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named '...steps.rollback'`

- [ ] **Step 3: Write minimal implementation**

Create `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/rollback.py`:

```python
"""Revert the whole working tree after a mid-pipeline failure (steps 2-6).

Safe specifically because ``steps/preconditions.py``'s clean-working-tree
check (step 1) guarantees nothing existed to lose before this run started —
so anything dirty by the time a later step fails is provably THIS run's own
writes, and a blanket revert cannot destroy pre-existing uncommitted work.
Whole-repo scope, matching the clean-tree check's own scope (not narrowed to
barn/ or marketstall.toml) — see the design's resolution of open question 3
(2026-08-05).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire_studio.packaging.share.git import git
from haywire_studio.packaging.share.pipeline.errors import ShareError

if TYPE_CHECKING:
    from haywire_studio.packaging.share.pipeline.pipeline import SharePipeline


class RollbackError(ShareError):
    """The revert itself failed. Nothing further is attempted automatically."""


def revert_working_tree(pipeline: "SharePipeline") -> None:
    """``git checkout -- .`` + ``git clean -fd``, whole repo.

    Purely local — never touches a remote — so uses the unhardened ``git``
    helper, not ``git_remote``.
    """
    checkout = git(["checkout", "--", "."], cwd=pipeline.repo_root, timeout=30.0)
    if not checkout.ok:
        raise RollbackError(
            f"Could not revert tracked changes: {(checkout.stderr or checkout.stdout).strip()}"
        )
    clean = git(["clean", "-fd"], cwd=pipeline.repo_root, timeout=30.0)
    if not clean.ok:
        raise RollbackError(
            f"Could not remove untracked files: {(clean.stderr or clean.stdout).strip()}"
        )
```

Add the wrapper method to `SharePipeline` (`pipeline.py`), near `check_preconditions`:

```python
    def rollback(self) -> None:
        """Revert every write this run made — safe because step 1 guaranteed
        a clean tree before anything was written. See steps/rollback.py."""
        from haywire_studio.packaging.share.pipeline.steps import rollback as steps_rollback

        steps_rollback.revert_working_tree(self)
```

(Import inside the method, matching this file's existing lazy-import style for step modules used only occasionally — check the file's convention before finalizing; if `pipeline.py` imports all `steps_*` modules at the top already, as seen in the file's header block, add `from haywire_studio.packaging.share.pipeline.steps import rollback as steps_rollback` there instead and call `steps_rollback.revert_working_tree(self)` directly, matching every other step method in the class.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/share_pipeline/test_rollback.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Wire rollback into the wizard's failure path for steps 2-6**

In `_state.py`, every `advance_from_*` method past `advance_from_preconditions` follows the same `except ShareError as exc: self.fail(exc); return` pattern. Add a rollback trigger: on any such failure, call `self.pipeline.rollback()` before setting the error, so the modal that opens is reporting a state that has ALREADY been cleaned up (matching the design: the rollback modal "also has to trigger the revert as a side effect of opening").

**This supersedes Task 6's edit to `fail()` — the version below is the FINAL one.** Task 6 added the `pending_modal` assignment; this task adds the rollback branch. Write the merged method, do not layer a second override:

```python
    def fail(self, exc: BaseException) -> None:
        """Record a failure without advancing. Keeps the user on the step.

        ``PreconditionsError`` carries a single structured ``PreconditionFailure``
        — stashed so the panel can open a remedy modal (see take_pending_modal).

        For any step past "preconditions", the working tree may hold this
        run's own writes — reverted here before the error is shown, so the
        rollback modal always reports a state that has already been cleaned
        up, matching the design's "Class C" contract. The "preconditions"
        step is exempt: step 1 never mutates, so a revert there would cost a
        git subprocess for a guaranteed no-op.
        """
        super().fail(exc)
        self.precondition_failure = exc.failure if isinstance(exc, PreconditionsError) else None
        if self.precondition_failure is not None:
            self.pending_modal = self.precondition_failure
            return
        if self.step != "preconditions":
            try:
                self.pipeline.rollback()
            except ShareError as rollback_exc:
                logger.error("Rollback after step %r failure also failed: %s", self.step, rollback_exc)
                self.error = f"{self.error}\n\nAdditionally, rollback failed: {rollback_exc}"
```

Note the early `return` on the precondition branch: a `PreconditionsError` can also be raised from a *later* step (`verify_push_allowed`), and rolling back on it would be wrong — the remedy modal handles it. `logger` already exists at `_state.py:48`; `ShareError` is already imported (line 38).

- [ ] **Step 6: Write the failing test for rollback triggering on a mid-pipeline failure**

State-level, in `tests/test_share_wizard_ui.py` (this file has no browser harness — see Task 6 correction (b)). The docs step is the natural place to force a failure: the file already patches it via `_fake_docs()` (line 68-75), so the pattern is established.

```python
@pytest.mark.anyio
async def test_mid_pipeline_failure_reverts_the_working_tree(project: Path) -> None:
    """A failure past step 1 leaves no trace: the tree is reverted BEFORE the
    error is reported, so the modal describes an already-cleaned state."""
    from haywire_studio.packaging.share.pipeline import DocsGenerationError

    wizard = _wizard(project)
    with patch.object(steps_detect, "detect_share_drift", side_effect=_no_drift):
        await wizard.advance_from_preconditions()
        await wizard.advance_from_checked()

    # A write this run made, standing in for whatever a real step would leave.
    stray = project / "generated_by_a_failed_run.md"
    stray.write_text("partial output")

    with patch.object(
        SharePipeline, "apply_docs", new=AsyncMock(side_effect=DocsGenerationError("docs blew up"))
    ):
        await wizard.advance_from_docs()

    assert wizard.error is not None
    assert "docs blew up" in wizard.error
    assert not stray.exists()


@pytest.mark.anyio
async def test_precondition_failure_does_not_trigger_a_rollback(tmp_path: Path) -> None:
    """Step 1 never mutates, so it must not pay for a revert — and a stray
    file there must survive, proving no blanket clean ran."""
    from haybale_marketplace.editors._share_wizard import ShareWizard
    from haywire_studio.packaging.share.pipeline import SharePipeline

    repo = tmp_path / "broken3"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    stray = repo / "untouched.txt"
    stray.write_text("mine")

    wizard = ShareWizard(pipeline=SharePipeline(repo), popup=None)
    await wizard.advance_from_preconditions()

    assert wizard.error is not None
    assert stray.exists()
```

`DocsGenerationError` is the real name (verified — `errors.py:71`; the full set is `PreconditionsError`, `ManifestError`, `VersionError`, `InvalidSpecifierError`, `TagCollisionError`, `DocsGenerationError`, `MarketstallError`, `CommitError`, `PushError`, `PipelineStateError`, all under `ShareError`). Any `ShareError` subclass serves the test's purpose.

- [ ] **Step 7: Run tests to verify they fail, then implement until green**

Run: `uv run pytest tests/test_share_wizard_ui.py -k "reverts_the_working_tree or does_not_trigger_a_rollback" -v`
Expected before Step 5's edit: the first FAILs (stray file survives), the second PASSes (nothing rolls back yet). After: both PASS.

- [ ] **Step 8: Add the distinct rollback modal shape to `remedy_modal.py`**

```python
def show_rollback_modal(message: str, *, on_close: Callable[[], None]) -> None:
    """Class C: a mid-pipeline failure (steps 2-6). Distinct from
    show_remedy_modal — this always reports that a revert has ALREADY run
    (see ShareWizard.fail()), so there is nothing to act on and no fix
    affordance is offered, only acknowledgement."""
    with ui.dialog() as dialog, hui.dialog_card("w-[480px]"):
        ui.icon("error", size="20px").classes("hw-text-danger")
        ui.label("Something went wrong, and it could not be fixed automatically.").classes(
            "text-sm hw-text-danger"
        )
        ui.label(message).classes("text-xs hw-text-dim whitespace-pre-line")
        ui.label("Every change this run made has been reverted — nothing was left behind.").classes(
            "text-xs hw-text-dim"
        )

        def _close() -> None:
            dialog.close()
            on_close()

        with ui.row().classes("w-full justify-end gap-2 mt-2"):
            ui.button("Close", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
    dialog.open()
```

**Wiring — same one-shot seam as Task 6, NOT `error_detail`** (which Task 6 deleted; see its correction (a)). Generalize the pending-modal field so it can carry either shape. In `_state.py`, change `pending_modal`'s type and the `fail()` assignment:

```python
        # Either a PreconditionFailure (step 1 -> remedy modal) or the plain
        # error string of a rolled-back mid-pipeline failure (-> rollback
        # modal). One-shot; drained by the panel that renders next.
        self.pending_modal: PreconditionFailure | str | None = None
```

and in `fail()`, after the rollback branch succeeds, queue the rollback modal:

```python
        if self.step != "preconditions":
            try:
                self.pipeline.rollback()
            except ShareError as rollback_exc:
                logger.error("Rollback after step %r failure also failed: %s", self.step, rollback_exc)
                self.error = f"{self.error}\n\nAdditionally, rollback failed: {rollback_exc}"
            self.pending_modal = self.error or ""
```

(Queued after the `except`, unconditionally, so the modal still opens — and now reports the rollback failure too — when the revert itself fails.)

Every panel that can be the current one when a mid-pipeline step fails must drain it. Rather than repeating the drain in eight panels, put it in one helper in `panels.py` and call it at the top of each `_panel_*`:

```python
def _drain_pending_modal(wizard: ShareWizard, rerender: Callable[[], None]) -> None:
    """Open whichever modal the last failure queued, exactly once.

    Called first thing by every panel: a step's failure keeps the user on
    that step, so the panel that re-renders after fail() is the one that owes
    the modal. One-shot via take_pending_modal(), so redraws don't restack it.
    """
    pending = wizard.take_pending_modal()
    if pending is None:
        return

    def _restart() -> None:
        wizard.retry()
        rerender()

    if isinstance(pending, str):
        show_rollback_modal(pending, on_close=_restart)
    else:
        show_remedy_modal(wizard, pending, on_restart=_restart)
```

Then `_panel_preconditions`'s Task 6 drain becomes a call to this helper, and every other panel gains `_drain_pending_modal(wizard, rerender)` as its first line. Import both modal functions in `panels.py`; `chrome.py` still imports neither.

Type note: `take_pending_modal`'s return type widens to `PreconditionFailure | str | None` to match.

- [ ] **Step 9: Run test to verify it passes**

Run: `uv run pytest tests/test_share_wizard_ui.py -k "mid_pipeline_failure_reverts" -v`
Expected: PASS

- [ ] **Step 10: Run the full wizard + rollback + preconditions suites**

Run: `uv run pytest tests/test_share_wizard_ui.py tests/share_pipeline/ -v`
Expected: all PASS

- [ ] **Step 11: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-studio/src/ barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/
uv run ruff format --check packages/haywire-studio/src/ barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: clean. Fix anything new (anything pre-existing and unrelated to this plan is not yours to fix here).

- [ ] **Step 12: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/rollback.py packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/pipeline.py barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/ tests/share_pipeline/test_rollback.py tests/test_share_wizard_ui.py
git commit -m "feat(share): revert the working tree on any mid-pipeline failure (steps 2-6)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 8: Remove dead code — `barn_dirty` opt-in mechanism

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/results.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/steps/commit.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/pipeline.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/__init__.py`
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/cli.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/panels.py`
- Modify: `barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/_state.py`
- Test: `tests/share_pipeline/test_vocabulary.py`, `tests/share_pipeline/test_commit_step.py`, `tests/test_share_wizard_ui.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing — pure removal.

Per the settled design: "nothing dirty can exist by the time step 5 runs" once Task 3's clean-tree precondition is in place, so `barn_dirty_files()`, `BarnDirtyFile`, `CommitPlan.barn_dirty`, and its rendering in `panels.py` are unreachable dead code, not dormant-but-safe — they should be removed, not left in place, per this session's explicit design note.

> **⚠ THIS TASK BREAKS THE CLI IF SCOPED AS "wizard only".** `cli.py:344-352` reads `plan.barn_dirty` and `cli.py:364` passes `include_barn=` to `apply_commit`. Deleting the field without editing `cli.py` leaves an `AttributeError` on the CLI's commit path. The plan's global constraint has been corrected accordingly: the CLI gets **no new UX**, but it does get this deletion. It is not optional.

- [ ] **Step 1: Confirm the reference list (already surveyed — verify it still holds)**

```bash
grep -rn "barn_dirty\|BarnDirtyFile\|include_barn" packages/ barn/ tests/ --include="*.py"
```

Expected hits, all of which this task resolves:

| File | Lines | Action |
| --- | --- | --- |
| `pipeline/results.py` | 126-131, 137, 143 | delete `BarnDirtyFile` class + `barn_dirty` field |
| `pipeline/__init__.py` | 30, 46 | drop from imports and `__all__` |
| `pipeline/pipeline.py` | 23, 191-193, 215-218 | drop import, `barn_dirty_files()` method, `include_barn` param |
| `pipeline/steps/commit.py` | 12, 44-81, 100, 116, 163-175 | delete `barn_dirty_files()`, its `CommitPlan` kwarg, `include_barn` in `apply()` |
| `share/cli.py` | 344-352, 364 | delete the prompt block; `apply_commit(plan)` |
| `_share_wizard/panels.py` | 513-525, `_included()` | delete checkbox block and helper |
| `_share_wizard/_state.py` | 389, 397 | drop `include_barn` from `advance_from_commit` |
| `tests/share_pipeline/test_vocabulary.py` | 8, 135, 140 | edit the `CommitPlan(...)` construction |
| `tests/share_pipeline/test_commit_step.py` | 128-169, 289, 301 | delete the `barn_dirty_files` tests + `include_barn` assertions |
| `tests/test_share_wizard_ui.py` | 570 | delete `test_opted_in_barn_files_reach_the_commit` |

- [ ] **Step 2: (no new test — deletion is verified by the suite, not by a new assertion)**

An earlier draft added `test_commit_plan_never_has_barn_dirty_once_preflight_passed` asserting `not hasattr(plan, "barn_dirty")`. Do not add it: on a frozen dataclass, that asserts the language works. The real verification is that the whole suite still passes with every reference gone (Step 6) plus mypy catching any missed attribute access (Step 8). The invariant it wanted to document belongs in `CommitPlan`'s docstring, which Step 4 rewrites.

- [ ] **Step 3: (folded into Step 4 — nothing to red-phase for a pure deletion)**

- [ ] **Step 4: Remove the dead code**

In `results.py`, delete the `BarnDirtyFile` class and the `barn_dirty` field from `CommitPlan`:

```python
@dataclass(frozen=True)
class CommitPlan:
    """Step 5's preview: exactly what would be staged, committed, and tagged.

    ``files`` is the pipeline's own accumulated write set. Nothing outside
    that write set can be dirty by the time this runs — step 1's clean-
    working-tree precondition guarantees it — so there is no separate
    opt-in-extras mechanism here (there used to be one, for barn/ content
    left uncommitted before the wizard started; that state is now
    structurally impossible to reach).
    """

    files: list[Path]
    message: str
    tag: str
    diffstat: str = ""
```

In `steps/commit.py`, delete the `barn_dirty_files` function entirely and its call site inside `plan()` (the `barn_dirty=barn_dirty_files(pipeline)` keyword argument to `CommitPlan(...)`). Remove the now-unused `BarnDirtyFile` import.

In `panels.py`, delete the `checkboxes` list, the `if plan.barn_dirty:` block (lines 514-525), and the `_included()` helper + its use in the "Commit and tag" button's `on_click` — the commit call no longer takes an `include_barn` argument:

```python
    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Commit and tag",
            on_click=lambda: _advance(
                rerender,
                lambda: wizard.advance_from_commit((message_input.value or plan.message).strip()),
            ),
        ).props("flat dense").style("color: var(--hw-positive);")
```

Update `_state.py`'s `advance_from_commit` signature to drop `include_barn`:

```python
    async def advance_from_commit(self, message: str) -> None:
        self.retry()
        try:
            self.pipeline.verify_push_allowed()
            plan = self.pipeline.plan_commit(message=message)
            self.commit_plan = plan
            self.commit_result = self.pipeline.apply_commit(plan)
        except ShareError as exc:
            self.fail(exc)
            return
        self.step = "push"
```

In `pipeline.py`: delete the `BarnDirtyFile` import (line 23), the `barn_dirty_files()` method (lines 191-193), and `apply_commit`'s `include_barn` parameter (lines 215-218), so it becomes `return steps_commit.apply(self, plan)`. Follow through into `steps/commit.py::apply()` (lines 163-175): drop the parameter and stage `commit_plan.files` alone.

In `pipeline/__init__.py`: remove `BarnDirtyFile` from the import block (line 30) and from `__all__` (line 46).

**In `cli.py` — the step an earlier draft omitted.** Delete the whole prompt block at lines 344-352 and drop the argument at line 364:

```python
    message = _ask("Commit message", default=plan.message)
    plan = pipeline.plan_commit(message=message)

    pipeline.verify_push_allowed()
    print("✓ Remote will accept the push")

    if not _confirm(f"Commit and tag {plan.tag}?"):
        print("Aborted before committing. Nothing was committed or tagged.")
        return EXIT_FAILED

    result = pipeline.apply_commit(plan)
```

The `include_barn: list[Path] = []` local goes with it. Check whether `Path` is still used elsewhere in `cli.py` before removing its import (it almost certainly is).

- [ ] **Step 5: (folded into Step 6 — no dedicated test for a deletion)**

- [ ] **Step 6: Fix every test that referenced the removed API**

Three files, per Step 1's table:

- `tests/share_pipeline/test_vocabulary.py` (lines 8, 135, 140): drop `BarnDirtyFile` from the import and remove the `barn_dirty=[...]` kwarg plus the `plan.barn_dirty[0].untracked` assertion from the `CommitPlan` test. Keep the rest of that test — it still covers `files`/`message`/`tag`.
- `tests/share_pipeline/test_commit_step.py` (lines 128-169): delete the whole `# ── barn_dirty_files ──` section. At lines 289 and 301, drop the `include_barn=` arguments (keep the tests — they cover `apply_commit` itself).
- `tests/test_share_wizard_ui.py` (line 570): delete `test_opted_in_barn_files_reach_the_commit` entirely, and fix any other `advance_from_commit(msg, [...])` call to pass the message alone.

Run: `uv run pytest tests/share_pipeline/ tests/test_share_wizard_ui.py -v`
Expected: all PASS

- [ ] **Step 7: Full-repo grep to confirm zero remaining references**

```bash
grep -rn "barn_dirty\|BarnDirtyFile\|include_barn" packages/ barn/ tests/ docs/ --include="*.py" --include="*.md"
```

Expected: hits ONLY in this plan file (`docs/superpowers/plans/2026-08-05-*.md`), which is expected and fine. Anything under `packages/`, `barn/`, or `tests/` means a call site was missed — most likely `cli.py`, which is the one outside the wizard and therefore the easiest to forget.

- [ ] **Step 8: Lint, format, type-check**

```bash
uv run ruff check packages/haywire-studio/src/ barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/
uv run ruff format --check packages/haywire-studio/src/ barn/haybale-marketplace/haybale_marketplace/editors/_share_wizard/
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "refactor(share): remove barn_dirty opt-in mechanism, dead since the clean-tree precondition

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 9: `fixes.py` — confirm `add_origin`/`strip_os` handlers stay as pipeline-level API

**Files:**
- Modify: `packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/fixes.py` (docstring update only)
- Test: none new — existing `tests/share_pipeline/` coverage of `apply_precondition_fix` already exercises these.

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — `_PRECONDITION_FIXES`, `_fix_add_origin`, `_fix_strip_os` all keep their current signatures; only their caller changed (Task 6's `remedy_modal.py` calls `pipeline.apply_precondition_fix(...)` directly instead of the wizard's now-deleted `advance_from_preconditions_fix`).

This task is a documentation-only correction: the module docstring and `_PRECONDITION_FIXES`'s comment currently describe these as dispatched "by `SharePipeline.apply_precondition_fix`" without saying who calls THAT — worth being explicit now that the caller changed shape (was: `ShareWizard.advance_from_preconditions_fix`, an async method with its own recheck loop; now: `remedy_modal.py`'s synchronous act-modal button handlers, no recheck).

- [ ] **Step 1: Update the module docstring**

In `fixes.py`, change the header comment:

```python
"""Precondition-fix handlers dispatched by ``SharePipeline.apply_precondition_fix``.

Called directly from the Share Wizard's act-modal button handlers
(``_share_wizard/remedy_modal.py``) — NOT auto-rechecked afterward. The user
clicks the modal's own "Restart Wizard" button to re-run
``check_preconditions()`` from the top; there is no longer an in-place
recheck loop (see docs/superpowers/plans/2026-08-05-share-wizard-preflight-gate.md).
"""
```

- [ ] **Step 2: Verify existing tests still pass unchanged (no behavior touched)**

Run: `uv run pytest tests/share_pipeline/ -v`
Expected: all PASS — this task changed only a comment.

- [ ] **Step 3: Commit**

```bash
git add packages/haywire-studio/src/haywire_studio/packaging/share/pipeline/fixes.py
git commit -m "docs(share): clarify fixes.py's handlers are called from remedy_modal.py, not a recheck loop

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 10: Update `docs/guides/sharing-libraries.md` to match the new wizard behavior

**Files:**
- Modify: `docs/guides/sharing-libraries.md`

**Interfaces:** none — documentation only.

This session already added §4.4 "Git remote requirements" and two §8 pitfalls describing the OLD inline-fix-loop wizard behavior ("the wizard's 'Check the project' step offers this as an inline **Add origin remote** fix — type the URL and it runs the command for you, then re-checks in place"). That description is now wrong — update it to describe the modal-based flow.

- [ ] **Step 1: Update §4.3's wizard description**

Find and update this passage (originally at what was line 85-91 before Task 1-9's other doc edits shifted line numbers — search by content, not line number):

> "For the two precondition failures with an unambiguous, no-input repair — a missing `origin` remote, and an invalid `[tool.haywire].os` declaration — the wizard's first step offers an inline fix button instead of just a remedy: the repair runs in place, the project is re-checked automatically, and the panel updates without the user leaving the wizard. Every other failure still gets remedy text only (§8 lists them), since the repair either needs a judgment call or isn't haywire's to make."

Replace with:

```markdown
Any precondition failure stops the wizard and opens a remedy modal explaining
it — the wizard never shows more than one problem at a time, since an
earlier failure can make a later check meaningless (there's no point probing
whether your remote is reachable before you even have one configured). Three
failures — no `origin` remote, an invalid `[tool.haywire].os` declaration,
and an unrecognized git host — get an **act** modal: a button that performs
the repair right there (adds the remote, corrects the `os` list, or writes
the `~/.haywire/config.toml` entry for you, with your permission). Every
other failure gets an **inform** modal: message and remedy text only, since
the fix either needs a judgment call or isn't haywire's to make (detached
HEAD, wrong branch, unreachable remote). Either way, the modal ends with a
**Restart Wizard** button — closing it and re-running every check from the
top, which costs nothing since preflight is fast.
```

- [ ] **Step 2: Update §4.4's precondition-order list**

The "checked in this order" list currently has three items (origin exists → host recognized → push accepted). Add the new first item and renumber the rest, keeping their existing text:

```markdown
`haywire share` needs four things from your git setup before it will publish anything, checked in this order:

1. **The working tree is clean.** `git status --porcelain` must be empty — no
   staged, unstaged, or untracked changes anywhere in the repo, not just under
   `barn/`. This is deliberately strict: the publish pipeline reverts
   everything it writes if a later step fails, by resetting the whole working
   tree, and that's only safe to do because nothing else could have been
   sitting there dirty when the run started. Commit or stash first. This
   applies to `haywire share` on the command line exactly as it does in the
   GUI wizard — both run the same checks.
2. **An `origin` remote is configured.** …
3. **The host is recognized.** … (existing text)
4. **The remote accepts your push.** … (existing text)
```

Two accuracy notes for whoever writes this section:

- Item 3 must say that host recognition applies only to remotes naming a **network host**. A remote pointing at a local filesystem path (a sibling clone, a shared drive) skips the check entirely — it is not an unrecognized host, and publishing to one is allowed.
- Item 1's "reverts everything it writes" is only true for failures at steps 2-6. A step-1 failure never mutates and never rolls back. Do not overstate it.

- [ ] **Step 3: Update the two §8 pitfall entries added earlier this session**

The "Host not recognized" and "Push failed: terminal prompts disabled" pitfalls both currently describe fixing things by hand outside the wizard, which is still accurate for the SECOND one (push credentials — still an inform-only failure, no act-modal). But the host-unrecognized one now has an act-modal in the wizard — update its wording:

```markdown
**`haywire share` fails with "Host '\<hostname\>' is not recognized.".**
Your `origin` remote points at a host haywire doesn't ship built-in support
for — anything other than `github.com`/`gitlab.com`, typically a self-hosted
GitLab or GitHub Enterprise instance. In the GUI wizard, this failure's modal
offers to write the needed `~/.haywire/config.toml` entry for you — click
through it, then Restart Wizard. From the CLI, add it by hand per
[§4.4](#44-git-remote-requirements) and retry. This is unrelated to push
access — see the next entry if the push itself also fails.
```

Also add a new pitfall for the working-tree-clean check, since it's a new failure mode users will hit:

```markdown
**`haywire share` fails with "Working tree is not clean.".**
You have uncommitted changes somewhere in the repo — not just under `barn/`.
The publish pipeline reverts everything it writes if a step fails partway
through, by resetting the whole working tree, and that's only safe when
nothing else was dirty to begin with. Commit or stash your changes, then
retry.
```

- [ ] **Step 4: Verify the guide's internal links/anchors still resolve after renumbering**

If §4.4's list numbering shifted anything referenced elsewhere by anchor (`#44-git-remote-requirements` etc.), grep for stale references:

```bash
grep -rn "#44-git-remote-requirements\|§4\.4" docs/guides/sharing-libraries.md
```

Confirm every hit still points at the right section after this task's edits.

- [ ] **Step 5: Commit**

```bash
git add docs/guides/sharing-libraries.md
git commit -m "docs(share): update sharing-libraries.md for the modal-based preflight gate

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Task 11: Full-suite verification

**Files:** none — verification only.

- [ ] **Step 1: Run the pre-commit gate**

```bash
uv run pytest -m "not browser and not perf" -q > /tmp/gate.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/gate.log
grep -E "passed|failed" /tmp/gate.log | tail -1
```
Expected: `exit=0`, no FAILED/ERROR lines, summary shows 0 failed.

- [ ] **Step 2: Run the full suite including browser tests**

```bash
uv run pytest -q > /tmp/full.log 2>&1; echo "exit=$?"
grep -E "^FAILED|^ERROR" /tmp/full.log
grep -E "passed|failed" /tmp/full.log | tail -1
```
Expected: `exit=0`, no FAILED/ERROR lines.

- [ ] **Step 3: Final lint/format/type-check across the whole repo**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/ tests/
```
Expected: all clean.

- [ ] **Step 4: Report**

State plainly: full suite pass/fail counts, lint/format/mypy clean or not, and list anything that was pre-existing/unrelated noise versus introduced by this plan.

---

## Self-Review Notes

**Spec coverage check** (against the settled design from this session's conversation):
- ✅ `check()` stops at first failure — Task 2.
- ✅ New clean-working-tree precondition, first probe — Task 3.
- ✅ New host-recognition precondition, between origin-exists and reachability, skips reachability when unrecognized — Task 4.
- ✅ `url.py`'s own unknown-host warning stays independent (not delegated) — Task 5 (verification only).
- ✅ Inform/act modal shapes, `PreconditionFailure.kind` — Tasks 1, 6.
- ✅ `add_origin`/`strip_os` promoted to act-modals (were already fix_id-bearing) — Tasks 2, 6.
- ✅ New `add_host_config` act-modal, no app restart needed (config read fresh every call, confirmed via `load_self_hosted_hosts` source) — Task 6.
- ✅ Every act-modal ends with an explicit "Restart Wizard" click, no auto-continue — Task 6.
- ✅ Rollback (Class C) for mid-pipeline failures, whole-repo `git checkout -- . && git clean -fd`, safe because of the clean-tree precondition — Task 7.
- ✅ Rollback modal is distinct from the remedy modal (own component) — Task 7 Step 8.
- ✅ `barn_dirty` mechanism removed as dead code — Task 8.
- ⚠️ **CLI gets no new UX, but is NOT untouched** — Task 8 must delete its `barn_dirty`/`include_barn` block (`cli.py:344-364`), and it inherits the clean-tree gate via the shared `check_preconditions()`. An earlier draft claimed "CLI untouched"; that was wrong and would have shipped an `AttributeError`.
- ✅ Class B (inline validation) not introduced — no task adds it.
- ✅ Docs updated to match new behavior — Task 10.

**Corrections applied after a code-verification pass (2026-08-05).** An earlier draft of this plan was checked against the working tree; four claims did not survive, and the tasks were rewritten:

1. **`error_detail` cannot open a modal** (Tasks 6, 7). It fires on every re-render, inside a slot that gets cleared, and leaves a duplicate Retry button. Replaced with the one-shot `pending_modal` field drained by the panel.
2. **`tests/test_share_wizard_ui.py` has no browser harness** (Tasks 6, 7). Every modal test is now a state-machine test; the placeholder "read the harness and fill this in" steps are gone, replaced with runnable code.
3. **Host recognition needed a not-a-host guard** (Task 4). `urlsplit()` returns an empty hostname for local paths, which is what every `bare_remote` fixture uses; without the guard ~25 existing tests fail.
4. **`barn_dirty` had more call sites than listed** (Task 8), including `cli.py`, `pipeline/__init__.py`, and `pipeline.py`.

**Test accounting:** net +8/−6, with 7 candidate tests deliberately dropped as redundant and 5 existing tests refurbished rather than deleted. The full table with per-test rationale is in the File Structure section — consult it before adding any test not listed there.

**No placeholders remain.** Every task now contains runnable code or an explicit, verified instruction. The two former exceptions (Task 6 Steps 1 and 5) are written out in full.

**Type consistency check:** `PreconditionFailure.kind` (Task 1) → set by `check()` (Tasks 2-4 on `strip_os`, `add_origin`, `add_host_config`) → branched on by `show_remedy_modal` (Task 6). `PreconditionsReport.failure` / `PreconditionsError.failure` both return `PreconditionFailure | None`. `ShareWizard.precondition_failure` (singular) replaces `precondition_failures` (plural). `pending_modal` starts as `PreconditionFailure | None` in Task 6 and **widens to `PreconditionFailure | str | None` in Task 7** — `take_pending_modal`'s annotation must widen with it, and the panel dispatches on `isinstance(pending, str)`. `PreconditionFailure.lib_dir` carries a barn directory for `strip_os` and a hostname for `add_host_config`; its docstring is widened in Task 6 Step 7 to say so.

**Known gap, accepted:** the modal *rendering* code (`remedy_modal.py`'s dialog bodies) has no automated coverage, because this repo's wizard tests are state-only by design. Its logic is kept thin and its one non-trivial piece (`append_host_config`) is extracted and tested directly. True click-through coverage would need a `tests/ui/harness/` browser test — out of scope here, and noted so the absence is a decision rather than an oversight.
