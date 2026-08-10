---
status: current
doc_template: impl-spec
scope: SharePipeline's step-by-step mechanics, the collect-then-apply-once contract, the three failure outcomes, the error taxonomy, the default-branch publishing rule, and the current CI-facing tooling
see-also:
  - ../../guides/sharing-libraries.md
  - ../../reference/glossary.md
---

# Share Pipeline — Architecture

*The mechanics: what `SharePipeline` actually does, step by step, in the current codebase.*

## 1. Mental model

`SharePipeline` (`haywire.core.publishing.pipeline.pipeline`) is a single stateful object that drives one project's publish, one step at a time. It is the one engine behind every caller: the `haywire share` CLI and the Share editor's flow (`barn/haybale-share`) both construct a `SharePipeline(repo_root)` and call the same methods in the same order.

It is stateful because later steps consume earlier steps' outputs — dependency resolution precedes docs regeneration, the bumped version feeds both the docs render and the marketstall entry, and the final commit's file list is the union of every step's writes. A stateful object keeps that sequencing in one place instead of re-derived by each caller, and maps onto the flow's linear, resumable stepper UI.

Each step that can affect the working tree is split into a **check/plan** call (mutates nothing) and an **apply** call (mutates). This plan/apply split is covered in full in §3.

## 2. The steps

Eight step modules under `publishing/pipeline/steps/` — `preconditions.py`, `detect.py`, `dependencies.py`, `framework.py`, `version.py`, `docs.py`, `commit.py`, `push.py`. `SharePipeline` delegates to each rather than implementing the logic inline.

```text
1. Preconditions          check_preconditions() / require_preconditions()
2. Detect                 check_drift()   [pure — writes nothing]
3. Dependencies           apply_framework() | apply_removals() | apply_additions() | apply_floors()
4. Version bump           plan_version() → check_tag_available() → apply_bump()
5. Regenerate docs        docs_command() → apply_docs()   [async, subprocess]
6. Marketstall + commit   apply_marketstall() → plan_commit() → apply_commit()
7. Push                   verify_push_allowed() → apply_push()   [async]
```

### 2.0 Steps are not 1:1 with UI screens

The Share flow renders **three** screens over nine step modules, because the user asks three questions — can I publish, what am I publishing, ship it:

| Screen | Backed by |
|---|---|
| Preflight | `preconditions.py`, then `detect.py` + `framework.plan()` + `version.plan()` to prepare the next screen |
| Review | `SharePipeline.apply_all()` over every `dependencies.py` applier, then `version.apply_bump()` |
| Publish | `docs.py` → `commit.apply_marketstall()` → `push.verify_allowed()` → `commit.apply()` → `push.apply()` → `ShareFlow._hot_swap_bumped_libraries()` |

The engine keeps its finer-grained modules because each has its own reason to exist: `detect.py` is pure and shared with `haywire deps check`; `dependencies.py` owns every write to `[project] dependencies` (splitting one file's mutations across modules would spread one concern thin); `framework.py` only **plans**, because `plan_framework()` must read the author's actual prior declaration — when the framework write lived alongside the other dependency writes, "keep the current declaration" computed from a value another step had already rewritten.

Those are the ENGINE's units of work. The screens are the USER's units of decision, and the two do not have to agree. An earlier wizard made them agree — thirteen screens, one per pipeline concern — and a clean repo then walked six consecutive screens of good news requiring six clicks and offering no decisions.

`tests/share_pipeline/test_step_sequence.py` enforces what actually matters: every decision the UI can express has an applier behind it, and `apply_all()` reads every `ShareDecisions` field. A field it forgot would be collected from the author and then silently dropped — invisible in a collect-then-apply-once design, since nothing writes until the single apply.

### 2.1 Step 1 — Preconditions

`check_preconditions()` verifies everything needed to publish and collects **every** failure in one pass, rather than raising on the first — a user missing both a remote and a barn library should see both at once, not discover the second after fixing the first. It returns a `PreconditionsReport` (`ok` is `True` iff `failures` is empty); `require_preconditions()` wraps it and raises `PreconditionsError` on failure.

It checks, in order:

- `git --version` — if git itself is missing, every other probe would just report the same missing binary as a different symptom, so the method returns immediately with a single failure.
- `barn/` exists and contains at least one directory with a `pyproject.toml` (via `barn.barn_library_dirs()`).
- Every barn library's `pyproject.toml` parses via `read_manifest()` — a malformed file or an invalid `[tool.haywire].os` declaration is reported here rather than surfacing later as a crash mid-docs-generation or a silently wrong marketstall entry.
- An `origin` remote is configured.
- The remote is reachable, via `git ls-remote --symref origin HEAD`. This exercises the exact credential path `git push` uses, so an auth failure surfaces here rather than after a commit and tag already exist. `--symref` also narrows the round-trip to one ref and additionally names the remote's default branch (`ref: refs/heads/<name>\tHEAD` in the output) — the local `git symbolic-ref refs/remotes/origin/HEAD` is *not* a usable substitute, since nothing populates it without an explicit `git remote set-head`.
- HEAD is not detached (`git symbolic-ref -q HEAD`, not `git rev-parse --abbrev-ref HEAD` — see §5 for why).
- The current branch matches the remote's default branch (see §5).

Reporting rather than raising also matters for the Preflight screen. It runs automatically when the flow opens (`show_step_flow(auto_start=True)`) — a first step that only checks, writes nothing, and asks the user to confirm an intent they already expressed by opening it does not deserve a button. On failure the screen renders the message and its remedy **inline**, offering the in-place fix where one exists (`fix_id`) and "Check again" always. So it needs a populated failure to render, not an exception to catch before the UI exists.

Inline, specifically, rather than in a modal: a `ui.dialog()` is a top-level element that a panel's own container clear cannot reach, so an earlier wizard had to close the whole popup to show one, and opening it outside a click handler stacked it on every redraw.

### 2.2 Step 2 — Detect

`check_drift()` runs `detect_share_drift()` (from `share.drift.detect`) against every barn library. It is **pure**: nothing here writes, which is what lets `haywire deps check` and any future read-only surface share it.

The findings split by consequence, not by category:

- **`drifted`** — the library has an **undeclared import** (`pyproject_missing`): the source imports a distribution the published manifest omits. This is the only state that breaks a consumer's install, so it is the only one `DepDrift.has_drift` and `DriftReport.needs_decision` count.
- **`findings_only`** — something to report, nothing to refuse over: **linked registrations** (repaired automatically, see §2.3), **unused declarations** (declared, never imported), **version floor lag** (a declared floor below the installed version), and unresolved imports (usually dynamic).

Version floor lag is deliberately *not* drift. A floor states the oldest version that still works, which requires resolving and testing candidate versions — static scanning cannot reach it, so "installed is newer" only means time passed. Raising it automatically would narrow consumer compatibility based on the author's dev-machine state, which is exactly what the codebase already refuses to do for third-party deps.

Both `haywire share` and `haywire deps check` (§6) call the same `detect_share_drift()`, so the two commands always report identically for the same repo state.

### 2.3 Step 3 — Dependencies

Every write to a library's `[project] dependencies` lives in `steps/dependencies.py`, and each apply touches **only the entries it owns** (via `haywire.core.library.dep_edit`). There is no operation that expresses "replace the whole list", which is what makes the ownership rule structural rather than conventional:

- `apply_framework(specifier)` — the `haywire-core` entry, and nothing else. The one authored floor in the flow.
- `apply_removals({lib: [dist, …]})` — drops unused declarations the author ticked.
- `apply_additions({lib: [entry, …]})` — declares undeclared imports with the author's chosen pins. Skips distributions already declared: an addition never restates an existing floor.
- `apply_linked_registrations({lib: [name, …]})` — adds imported haywire libraries to `linked_libraries` in `haybale.toml`. **Applied without asking**, at the framework step so it lands exactly once. There is nothing to decide: `detect_deps` emits a name here only when the source imports it *and* it resolves to an installed registered library, so every entry is provably true, carries no version specifier, and narrows nothing for consumers. It is *reported* on the Findings and Confirm screens rather than done silently, because it edits a hand-authored declaration rather than a generated one.
- `apply_floors({lib: [entry, …]})` — rewrites only the floors the author actively changed.

An empty mapping writes nothing, so "keep them" is a real answer on every screen.

This replaced a whole-list overwrite that caused two bugs. It rewrote the `haywire-core` floor as a side effect of resolving unrelated drift — masked only by step ordering, which meant the framework step's "keep the current declaration" option computed from an already-clobbered value. And it regenerated entries from detection, silently dropping extras (`visiongraph[onnx,openvino,mediapipe]`), environment markers, and direct references.

`acknowledge_undeclared()` records that the author is publishing a knowingly-undeclared import — the one dependency state with no defensible default — without touching disk. Only the Share flow can set it, because only it offers the choice; the CLI declares every detected import instead and never reaches that state.

### 2.4 Step 4 — Version bump (lockstep)

`plan_version()` reports the current lockstep state — every barn library's declared version, whether they agree, and the patch/minor/major targets available from the common version (empty when they disagree, since there is no honest arithmetic to offer).

`apply_bump(spec)` resolves `spec` (`"patch"` / `"minor"` / `"major"`, or an explicit `X.Y.Z`), verifies the target tag doesn't already exist (`check_tag_available()` — checked before anything is written, because rejecting a colliding version is nearly free here versus after a commit already exists), then writes the resolved version into every barn library. A keyword spec against disagreeing versions raises `VersionError` — picking one sibling's version to extrapolate from would silently downgrade the others.

`uv lock` is always attempted afterward (the lockfile records member versions and drifts a release behind otherwise) but never blocks the step; a failure comes back as `BumpResult.lock_warning` instead of an exception.

### 2.5 Step 5 — Regenerate docs

`apply_docs()` always runs — there's no yes/no gate, since a bumped version with stale docs would ship a QUICKREF stating the wrong version. It must run *after* step 3: the doc generator embeds `v{version}` into the rendered output.

The actual generation happens in a subprocess (`haywire docs --all --json <tmp-path>`), not in-process. `docs_command()` builds the argv; `apply_docs()` runs it via `run_streaming()` and reads the coverage JSON back. This is a hard constraint, not an optimization: `generate_docs()` builds a *second* library system whose `initialize()` calls `set_global_injector()`, which in-studio would repoint the live app's DI globals at a throwaway system (DI context is module-level globals, not `ContextVar` — see `.insights/project_di_context.md`). Docs extraction also instantiates every node in a throwaway graph to read its ports, which in-process would construct hardware-touching nodes inside the live running app. See `.insights/project_docs_gen_reentrancy.md`.

Coverage gaps (missing docstrings, etc.) are read-only feedback and never fail the step. Only a non-zero subprocess exit — an actual crash — raises `DocsGenerationError`.

`docs_write_set()` (called by `apply_docs()` to populate the accumulated write set) reads `git status --porcelain -- barn` rather than predicting which files changed, because the generator's output is data-dependent: it writes OVERVIEW/QUICKREF/README plus one file per component, and *deletes* orphaned per-component docs when a component was renamed. Scoped to `barn/` only — nothing outside barn reaches consumers, and sweeping up unrelated working-tree dirt is what would make a flow-authored commit untrustworthy.

### 2.6 Step 6 — Marketstall, commit, tag

`apply_marketstall()` calls `write_marketstall()` (from `share.marketstall`) to fully rebuild `marketstall.toml` from every barn library, and rewrite the `<!-- marketstall:share-url -->` marker block (via `share.readme`) in the root README and every `barn/*/README.md`. Always a *full* rebuild — the feed's contract is "every haybale this repo currently offers," so a partial rebuild would silently delete the entries of libraries not touched in this run.

`plan_commit()` previews exactly what would be staged, committed, and tagged: the pipeline's accumulated write set (`self.written`, appended-to by every apply step so far) plus a diffstat, requires `self.version` to already be set (raises `PipelineStateError` otherwise — step 3 must run first). There is no separate "uncommitted barn content" opt-in step any more — step 1's clean-working-tree precondition guarantees nothing outside `self.written` can be dirty by the time this runs, so `plan.files` is already everything there is to stage.

`apply_commit()` stages exactly `plan.files` — never `git add -A`/`-a` — commits, then tags. There is no separate checkpoint commit: the pre-flow `HEAD` is already the rollback anchor, and the flow authors exactly one commit. The tag is created only after the commit succeeds, since a tag on the wrong commit is worse than no tag.

### 2.7 Step 7 — Push

`verify_push_allowed()` runs `git push --dry-run` immediately *before* the commit step actually commits, closing the race window opened at step 1: someone else may have pushed to the same branch in the meantime, and discovering that after a commit and tag already exist would force the user to clean up. It mirrors the marketplace's `dry_run()` → `install()` pairing — pre-flight verification beats post-failure recovery when nothing needs undoing if nothing was mutated yet.

`apply_push()` pushes the commit and tag to `origin` via `git_remote_streaming()` (env-hardened — see §4). On failure it raises `PushError`, which carries the exact command to retry by hand; the step is safely retryable in place since nothing here mutates pipeline state.

**The reload tail.** After a successful push, the flow (`ShareFlow._hot_swap_bumped_libraries`, `haybale-share`, not the pipeline itself — the pipeline has no live library system to reload) evicts and rescans every barn library the bump touched. `@library(...)` reads `version` out of `haybale.toml` fresh off disk at decoration time (step 4 already wrote the bumped value there — see §2.4 and `write_barn_versions`), so the rescan picks up the new version with no environment sync in between.

**Why after the push rather than beside the bump.** Two reasons, both about the rollback boundary:

- The bump sits *inside* that boundary. Reloading there would strand the registry on a version the tree no longer holds if a later step failed and reverted the manifests.
- Evicting and re-importing libraries mid-flow strands the studio without them across the docs subprocess and the commit, for no benefit — nothing between the bump and the push reads the registry.

The CLI (`haywire share --yes`) has no live library system, so it skips the reload entirely; only the flow performs it. `tests/share_flow/test_refresh_tail.py` covers the tail's placement and failure posture.

## 3. The plan/apply split

Every step that can touch disk or the remote separates a read-only **check/plan** call from a mutating **apply** call:

| Step | Check/plan (read-only) | Apply (mutating) |
|---|---|---|
| 1 | `check_preconditions()` / `require_preconditions()` | `apply_precondition_fix()` — the two/three failures with a mechanical repair (missing origin, invalid `os` declaration, unrecognized host); every other failure is fixed outside the pipeline |
| 2 | `check_drift()` | — (Detect is pure) |
| 3 | `plan_framework()` | `apply_framework()`, `apply_linked_registrations()`, `apply_removals()`, `apply_additions()`, `apply_floors()`, `acknowledge_undeclared()` |
| 4 | `plan_version()`, `check_tag_available()` | `apply_bump()` |
| 5 | `docs_command()` | `apply_docs()` |
| 6 | `plan_commit()` | `apply_marketstall()`, `apply_commit()` |
| 7 | `verify_push_allowed()` | `apply_push()` |

A failure past step 1 has **three** possible outcomes, and conflating them is how the UI once told users something false:

1. **Preflight failed.** Nothing was written, so nothing is reverted. The screen shows the remedy in place.
2. **A writing step failed, before the commit.** `pipeline.rollback()` reverts the whole working tree — safe because step 1's clean-working-tree precondition guarantees nothing else could have been dirty when the run started, so anything dirty now is provably this run's own writes. Reporting "everything was reverted" here is true.
3. **The commit already landed** — a failed tag, or a failed push. The commit and tag are real and are **not** reverted: `revert_working_tree()` is working-tree only by design (`git checkout -- .` + `git clean -fd`), and `tests/share_pipeline/test_rollback.py` asserts committed history survives it. Running the revert here would be a no-op that reports success.

The distinction is load-bearing. An earlier wizard ran the same revert for every failure past step 1 and reported "every change this run made has been reverted — nothing was left behind", which after a failed push was false in exactly the case where the user most needed the truth: they were holding an unpushed release and had just been told the slate was clean. `ShareFlow.fail()` checks `commit_result` **first** for this reason, and the Publish screen then shows the exact command to finish by hand (`PushError.manual_command`, never recomputed — `push_command()` raises on a detached HEAD, which is precisely the kind of state that can coincide with a push failure).

See `steps/rollback.py`.

This split is what lets the Share flow show every finding and its consequence before anything is written, and `haywire share --dry-run` report the same material without writing, while the plain CLI drives the exact same methods and renders none of it.

Step 3's applies take **mappings of what the author chose**, not a mode flag. An empty mapping writes nothing, which is what makes "keep them" a real answer rather than a branch the caller has to remember to skip. `apply_linked_registrations()` is the exception that proves it: nothing about it is chosen, so it is never offered — it runs alongside `apply_framework()` and is reported afterwards.

### 3.1 Collect-then-apply-once

`apply_all(ShareDecisions)` writes every dependency answer in one pass over those same appliers, in the same order. Assembling a `ShareDecisions` touches no file, so a UI can let the author revise freely and commit once.

That is not a convenience. It collapses five writing steps into one, which means a flow abandoned before Publish leaves the tree exactly as it found it, and a failure has a single region to revert. The per-applier methods remain — the CLI still calls them directly, and the order guarantee (framework first, so `plan_framework()` reads the author's real prior declaration) is now covered by a test rather than by convention.

**A prior, now-removed layer once sat on top of this split**: a standalone read-only `plan()` method returning a `SharePlan`, backing a `haywire share --check` CLI mode that reported staleness without publishing. That layer was deleted by the CLI Surface Simplification plan — `--check`'s own preconditions (no detached HEAD, must be on the default branch) made it fail on every PR checkout by construction, since a PR checkout is always one or the other. It has no replacement inside `SharePipeline`; CI-facing drift detection now lives entirely in the separate `haywire deps check` command (§6), which never touches `SharePipeline` at all. The per-step plan/apply split described in the table above is unaffected by that removal — it was never what `plan()`/`--check` was built from.

## 4. The error taxonomy

Every expected pipeline failure raises; successes return frozen dataclasses (`publishing/pipeline/results.py`). This matches the existing idiom in `share.marketstall` (`NoBarnError`) and `share.manifest.errors` (`InvalidOsDeclarationError`) rather than introducing a Result-type wrapper.

All pipeline-level exceptions subclass `ShareError` (`publishing/pipeline/errors.py`):

| Exception | Raised when |
|---|---|
| `PreconditionsError` | One or more step-1 checks failed. Carries the full `list[PreconditionFailure]`, not just the first. |
| `ManifestError` | A library `pyproject.toml` could not be read or is invalid — the pipeline's translation of `share.manifest.errors`'s `ManifestReadError`/`InvalidOsDeclarationError` at the module boundary (see below). |
| `VersionError` | A version string was unparsable, or a lockstep bump had no honest target (disagreeing versions, keyword spec). |
| `TagCollisionError` | The `v<version>` tag already exists, locally or on the remote. |
| `DocsGenerationError` | `haywire docs --all` exited non-zero — an actual crash, not a coverage gap. |
| `MarketstallError` | The marketstall rebuild could not complete — translation of `share.marketstall`'s `NoBarnError` and manifest-failure types. |
| `CommitError` | Staging, committing, or tagging failed. |
| `PushError` | The push failed; carries `manual_command`, the exact command to retry by hand. |
| `PipelineStateError` | A step was called out of order — its inputs hadn't been produced yet (e.g. `plan_commit()` before `apply_bump()`). |

Each caller translates a caught `ShareError` in its own way: the CLI (`run_share_cli`) prints `str(exc)` and exits non-zero; the flow renders inline error state per step. There is no Farmhand-specific translation yet — the errors docstring notes this as a plausible future consumer, not a current one.

### 4.1 The boundary translation

The `share.*` domain modules raise their own, *local* exceptions — `share.manifest.errors.ManifestReadError` and its subclass `InvalidOsDeclarationError` — which are deliberately plain `RuntimeError`s, not `ShareError` subclasses. This keeps the domain modules' exception vocabulary independent of the pipeline's: `share.manifest.errors` has no reason to import anything from `share.pipeline`.

`pipeline.py` is the only place that knows about both taxonomies. It imports the domain modules' exceptions directly and catches them at each step's boundary, re-raising as its own `ShareError` subclass:

```python
_MANIFEST_FAILURE_TYPES = (ManifestReadError, toml.TomlDecodeError, OSError)
```

This tuple is reused across every step that reads or writes a library manifest. For example, `apply_removals()`:

```python
try:
    remove_dependencies(lib_dir, dist_names)
except _MANIFEST_FAILURE_TYPES as exc:
    raise ManifestError(str(exc)) from exc
```

and `apply_marketstall()` additionally folds in `share.marketstall`'s `NoBarnError`:

```python
try:
    result = write_marketstall(self.repo_root, tag=f"v{self.version}")
except (NoBarnError, *_MANIFEST_FAILURE_TYPES) as exc:
    raise MarketstallError(str(exc)) from exc
```

The effect: nothing downstream of `pipeline.py` — a flow step handler's `except ShareError`, or the CLI's single top-level `except ShareError` — ever sees a raw domain-module exception type. Each `share.*` domain module stays independently importable with its own small exception vocabulary; `share.pipeline` is the only consumer that has to know both vocabularies exist.

## 5. The default-branch publishing rule

`check_preconditions()` unconditionally rejects two situations: a detached `HEAD`, and being on any branch other than the remote's default branch. There is no bypass — no `--ref` flag, no keyword argument, nothing. This is deliberate and, as of this document, has no ADR of its own; this section is its canonical home. The [sharing guide, §4.3](../../guides/sharing-libraries.md#42-publish-from-the-default-branch) states the rule and its remedy for authors, and links here for the reasoning.

**Why it existed.** Before the tag-pinning fix, the generated marketstall
entry carried several URLs that were not pinned the same way: `docs_url`,
`examples_url`, and `tests_url` were built from whatever branch was checked
out *at publish time* (`_build_entry_for_library()` in `share.marketstall`,
reading the current ref), while `install_spec` — the actual `pip install`
command a consumer runs — carried **no** ref at all and always resolved to
the remote's default-branch `HEAD`. Publishing from a feature branch meant
those two URL families pointed at two different places from day one, and a
feature branch typically dies the moment it merges, so the doc/example/test
URLs would go dead with no way for the author (who already knows the branch
is gone) to notice.

**Current state.** `_build_entry_for_library()` now accepts an optional
`tag` parameter; `apply_marketstall()` (step 5, before `apply()` creates the
actual git tag later in that same step) always supplies
`f"v{pipeline.version}"` — the version step 3 already resolved and
tag-collision-checked. All four URL families now pin to that same tag, so
they no longer disagree regardless of which branch the tag was cut from.

**This does not relax the default-branch-only rule.** The check in
`check_preconditions()` remains unconditional — no `--ref` flag, no
bypass — even though the specific disagreement that originally motivated it
is gone. Whether to allow publishing from a non-default branch now that the
URLs agree is a separate decision, deliberately not made by the tag-pinning
fix. See `docs/superpowers/plans/2026-08-01-marketstall-tag-pinning.md` for
the fix's scope.

**Why there's no escape hatch.** An earlier design did carry a `--ref` flag as exactly that escape hatch, with a documented remedy ("pass `--ref <default>` so the generated URLs point at the branch that will still exist after this one merges"). A whole-branch review of the codebase found that remedy was simply false: `--ref` never actually reached `_build_entry_for_library()` — the URL-generating code path ignored it entirely, so the flag did nothing but suppress the branch check while still emitting URLs pinned to the wrong branch. Once that was discovered, the CLI Surface Simplification plan removed `--ref` (and its sibling `--tag`) outright rather than fix it, on the basis that neither had a real user depending on it. The rule that replaced the flag is therefore not "the flag was removed and the check just happens to remain" — the check was already correct and unconditional; only the broken bypass was deleted.

**Detached HEAD vs. unborn branch.** The detached-HEAD check specifically avoids a related trap: `git rev-parse --abbrev-ref HEAD` prints the literal string `"HEAD"` in two situations that must not be conflated — a genuinely detached HEAD, and an *unborn* branch (a freshly initialized repo before its first commit), where HEAD still symbolically points at a real branch name that simply has no commit yet. `check_preconditions()` and `barn.current_ref()` both use `git symbolic-ref -q HEAD` instead, which fails only in the genuinely-detached case and succeeds (printing `refs/heads/<name>`) for an unborn branch. Neither ever returns the literal string `"HEAD"` as if it were a branch name — a `pipeline.py` docstring notes that an earlier version of `current_branch()` did exactly that, and it silently corrupted push refspecs downstream (`HEAD:HEAD`).

## 6. The current CI story

There is no single CI gate for sharing. Two independent, purpose-built commands cover what CI needs; neither depends on the other, and neither instantiates `SharePipeline`.

### 6.1 `haywire deps check`

Implemented in `haywire_studio/packaging/deps.py`, dispatched from `haywire deps check` in `app.py`. Its own module docstring states the design intent plainly: "Deliberately independent of SharePipeline: no git, no preconditions, no versioning, no marketstall." It is **not part of "the pipeline"** in any sense — it never constructs a `SharePipeline`, and its only dependency inside `haywire_studio` is `share.drift.detect`'s free function `detect_share_drift()`.

It walks every `barn/*` directory with a `pyproject.toml`, runs `detect_share_drift()` on each (the same function step 2 of the pipeline uses — see §2.2 — so both tools always agree), and prints what it finds. It never writes to disk. Exit code is `EXIT_DRIFT` (1) if any library has an undeclared import; unused declarations, version floor lag and unresolved imports are printed for information but never fail the run, matching the Share flow's own treatment of them. Otherwise it exits `EXIT_OK` (0).

The [sharing guide](../../guides/sharing-libraries.md#7-the-full-author-cycle) recommends running it as a PR gate to catch manifest drift before merging — but that recommendation describes intended usage of a CI-shaped tool, not an existing workflow wired up in this repo's `.github/workflows/`. As of this document, no workflow file invokes it.

### 6.2 `haywire docs --all --json`

Dispatched from the `docs` subcommand in `app.py`, calling `generate_all_docs()` (`haywire_studio.docs_gen.generate`). This regenerates every in-repo library's generated docs (README/OVERVIEW/QUICKREF/`docs/*.md`) for real — it is the same subprocess `SharePipeline.apply_docs()` shells out to in step 4 (§2.4), for the same reentrancy reasons (`.insights/project_docs_gen_reentrancy.md`).

Unlike `deps check`, this is a "generate and commit" job, not a staleness gate: coverage gaps are printed but never fail the run, and the command exits non-zero only if generation itself crashes. `--json <path>` writes the coverage map to a file (`{library_id: [gap lines]}`) rather than stdout, since a library-system boot prints freely to stdout during the run and not all of it is safe to parse as the report. Run in CI, the intended pattern is: run the command, then commit whatever it produced — it is not a check that something else is stale, it's the thing that keeps docs from *becoming* stale.

As with `deps check`, this describes what the command does and how it's meant to be used, not a claim that a workflow file in this repo currently runs it on a schedule or on every PR.

## Key files

- `packages/haywire-core/src/haywire/core/publishing/pipeline/pipeline.py` — `SharePipeline`, every step plus `apply_all()`.
- `packages/haywire-core/src/haywire/core/publishing/pipeline/steps/` — one module per step (`preconditions.py`, `detect.py`, `dependencies.py`, `framework.py`, `version.py`, `docs.py`, `commit.py`, `push.py`) that `SharePipeline` delegates to.
- `packages/haywire-core/src/haywire/core/publishing/pipeline/errors.py` — `ShareError` and its subclasses.
- `packages/haywire-core/src/haywire/core/publishing/pipeline/results.py` — the frozen result dataclasses each step returns.
- `packages/haywire-core/src/haywire/core/publishing/manifest/reader.py` — manifest reading (`read_manifest`); `publishing/manifest/errors.py` — `ManifestReadError`/`InvalidOsDeclarationError`.
- `packages/haywire-core/src/haywire/core/publishing/drift/detect.py` — `detect_share_drift()`; `packages/haywire-core/src/haywire/core/library/dep_edit.py` — the entry-level write operations.
- `packages/haywire-core/src/haywire/core/publishing/marketstall.py` — `write_marketstall()`, `NoBarnError`.
- `packages/haywire-core/src/haywire/core/publishing/git.py` — hardened git subprocess helpers; leaf module.
- `packages/haywire-core/src/haywire/core/publishing/barn.py` — `barn/` shape queries; leaf module.
- `packages/haywire-studio/src/haywire_studio/packaging/deps.py` — `haywire deps check`, decoupled from `SharePipeline`.
- `packages/haywire-studio/src/haywire_studio/packaging/share_cli.py` — `haywire share`'s single non-interactive mode plus `--dry-run`, a thin runner over `SharePipeline`. Lives in haywire-studio, not core: argument parsing and exit codes belong to the app package.
- `barn/haybale-share/haybale_share/` — the Share editor (`editors/share_editor.py`, ACTION slot, status-only) and its three-screen flow (`_flow/`). Depends on `haywire-core` only: the post-bump hot-swap reads a `LibraryRegistry` from core's DI rather than a `LibraryManager`, so this library never reaches into haybale-marketplace.
