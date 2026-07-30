# Share wizard — inquisition-settled design

Status: design settled via `/inquisition` (round 2), unimplemented.

Supersedes the library-scoped draft of the same name. The scope reversal
(library → project) is recorded in [ADR 0023](../../docs/adr/0023-project-scoped-lockstep-sharing.md).

## Problem

Publishing is entirely CLI-driven (`haywire share`, `haywire share --save`).
The only touchpoint inside the marketplace editors is the Edit dialog's "Detect
dependencies" flow (`_overview_edit_dialog.py`), which reuses `share.py`'s drift
machinery but never actually shares anything. Users unfamiliar with the CLI have
no path to publish without leaving the GUI. Separately, we want the same
capability reachable from Farmhand (MCP) so an agent can drive a publish on the
user's behalf.

## Goal

One shared pipeline, three thin callers: **CLI / UI / MCP** all drive the same
underlying `SharePipeline`, not three independent implementations.

## The unit of sharing is the project, not the library

A `haywire init` project is a uv **workspace root** (`members = ["barn/*"]`,
`init.py:116`) with a single `marketstall.toml` feed at its root and one git
remote. The artifact being published is repo-shaped: consumers fetch one feed
file and install by git URL from one clone.

Library-scoped sharing fights that shape — every sub-decision kept resolving to
"…but it's actually repo-wide" (the marketstall must aggregate all of `barn/*`
or it deletes sibling entries; `_update_repo_readmes` already rewrites every
`barn/*/README.md`; `uv.lock` is at the root). So the wizard shares the
**project**, and all `barn/*` libraries version in lockstep.

Consequences:

- The Share entry point is **not** on `LibraryOverviewEditor`. It lives in
  `LibraryBrowserEditor`'s burger menu (`library_browser_editor.py:149`),
  alongside the other repo-scoped actions (Refresh, Add Source, Edit File).
- The repo tag `v<version>` is truthful again (lockstep), so no per-library
  tag namespacing is needed.
- Overlap with `/haywire-release` is accepted: same lockstep *mechanic*,
  different artifact and audience. `/haywire-release` ships Tier 1+2 packages
  to PyPI via CI tags for haywire maintainers; this ships one project repo's
  barn feed via git URL for project authors.

## Scope

**In scope:**

- A step-by-step "Share Project…" wizard in `LibraryBrowserEditor`'s burger menu.
- A `SharePipeline` object in `haywire_studio.share` with a `plan()` / `apply()`
  split, driven by the NiceGUI stepper, the CLI, and future Farmhand tools.
- `haywire share` rewritten as an interactive runner over `SharePipeline`,
  plus `--check` and `--yes`.
- `.gitignore` / `.gitattributes` scaffolding fixes in `haywire init`.

**Out of scope (explicitly):**

- Pinning `install_spec` to the release tag — designed, deliberately deferred
  (see "Deferred: install pinning" below).
- Undo/redo integration — no `ctx.fence()`, no rollback beyond pre-flight
  verification.
- History rewriting, retroactive LFS tracking, or LFS at all (see below).
- Retrofitting `.gitignore`/`.gitattributes` fixes into existing projects —
  only new `haywire init` scaffolds get them.
- Anything about *installing*/browsing the marketplace — publish direction only.
- Building the Farmhand tool wrappers — this session designed the pipeline
  shape; a later session builds the callers on top of it.

## Why a stateful pipeline object

Later steps consume earlier steps' outputs (drift resolution precedes docs; the
bumped version feeds both the docs render and the marketstall entry; the final
commit's file list is the union of every step's writes). A stateful object
avoids three callers re-deriving the same sequencing logic, and maps onto
NiceGUI's stepper, which expects a linear resumable step model.

The `plan()` / `apply()` split is load-bearing beyond CI: step 5's file-list
preview *is* a plan, and `--check` is `plan()` with no `apply()`.

## Result/error convention

Matches the existing codebase idiom (`DriftError`, `InvalidOsDeclarationError`,
`NoBarnError` in `share.py` today) rather than a Result-type wrapper:

- **Expected failures raise domain-specific exceptions.** Each caller
  translates: the Farmhand wrapper re-raises as `FarmhandError(code, message,
  ids)`; the stepper renders inline error state; the CLI prints and exits.
- **Successful steps return small dataclasses.**
- **Check/act split where a real decision happens** — drift, version bump.
- **Progress**: coarse (step-level) for the sub-second git calls; **streamed**
  for the two slow subprocesses (docs regen, `uv lock`), mirroring
  `LibraryManager._run_uv_streaming` (`library_manager.py:214`).

## Step sequence

Ordering constraint discovered during design: **the version bump must precede
docs generation**, because `render_quickref` embeds `v{doc.version}`
(`render.py:43`). Generating docs first publishes a QUICKREF stating the
previous version.

### 1. Preconditions

One combined gate, all failures reported together:

- `git --version` (reuses `_check_git_available`) — no git → stop with the
  same install-instructions message `init_project` prints.
- `<root>/barn/` exists and holds ≥1 library with a `pyproject.toml`.
- `git remote get-url origin` is set.
- **`git ls-remote origin`** — exercises the exact credential path `git push`
  uses, so auth failures surface here rather than after a commit and tag exist.

The menu item is always enabled; this step explains why a workspace can't be
shared. (A disabled menu item cannot carry a tooltip — the design guide's
disabled state is `opacity: 0.5` **plus `pointer-events: none`**,
`design-guide.md:725`, which kills hover.)

### 2. Dependency drift

`detect_share_drift()` per barn library, diff-modal (Union/Replace), reusing
the UX already built in `_overview_edit_dialog.py`'s "Detect dependencies"
flow. Must resolve-or-acknowledge before continuing — Replace can destructively
remove declared deps, so it's a real decision, not an auto-fix.

### 3. Version bump (lockstep)

- Writes **every** `barn/*/pyproject.toml`. The root `pyproject.toml` is left
  alone: it's the workspace root at a fixed `0.1.0`, it depends on the library
  **unversioned** (`init.py:110`), and nothing reads its version.
- **When all barn versions agree** (always true after `haywire init`): the
  normal patch/minor/major picker.
- **When they disagree**: show each library's current version, flag the
  disagreement, and require an explicit target. No silent resolution — `bump_version`'s
  "first barn library found" heuristic (`share.py:1037`) would silently
  downgrade a higher-versioned sibling.
- `uv lock` always attempted (the lockfile records member versions and drifts
  one release behind otherwise — `share.py:1073`). On failure: warn and
  continue, matching `bump_version`'s existing posture. Never blocks.
- **Tag-collision check here**, where the fix is cheapest ("pick 0.3.2
  instead"): `git rev-parse -q --verify refs/tags/v<version>` locally and
  `git ls-remote --tags origin` remotely.

This needs its own narrow bump function, not `bump_version()`: different
version-resolution rules, different file set, and commit+tag move to step 4.

### 4. Regenerate docs

`haywire docs --all --json <tempfile>` as a **subprocess** against the project
root. Always runs, no yes/no gate. Coverage report shown as read-only feedback.

Why a subprocess and not an in-process call: `generate_docs()` builds a second
library system via `create_library_system_service()`, whose `initialize()` calls
`set_global_injector()` (`config.py:430`) — in-studio that repoints the live
app's globals at a throwaway system, and DI context is module-level globals, not
`ContextVar`. `extract_library` also instantiates **every node** in a throwaway
graph to read ports (`extract.py:95`), which in-process would construct
hardware-touching nodes inside the live app. See
`.insights/project_docs_gen_reentrancy.md`.

`--all` is one library-system load for the whole barn (vs. N boots for
per-library subprocesses) and its root-relative filter naturally excludes
site-packages installs and `--dev` mode's out-of-tree dev-repo libraries.

`--json <path>` is a new flag writing `{library_id: [coverage_lines]}` to a
file — a file sink rather than stdout, because the library-system boot prints
freely to stdout and not all of it is ours (library `on_enable` hooks print
too). Exit code stays 0 on coverage gaps; only a crash fails the step.

### 5. Marketstall + commit + tag

- **Marketstall**: full `barn/*` rebuild, reusing `share_save_repo`'s existing
  walk. The feed's contract is "every haybale this repo offers", so rebuilding
  from disk is what keeps it true.
- **Before committing, show a `git diff --stat`-style summary.** The write set
  is repo-spanning: every `barn/*/pyproject.toml`, root `uv.lock`, each
  library's `OVERVIEW.md`/`QUICKREF.md`/`docs/*.md` (including **deletions** for
  renamed components, `generate.py:87`) and `README.md`, root
  `marketstall.toml`, and the `<!-- marketstall:share-url -->` marker block in
  the root README **and every `barn/*/README.md`** (`_update_repo_readmes`,
  `share.py:60`).
- **Warn about dirty/untracked content inside `barn/`**, with an opt-in
  "include in this commit" checkbox. Uncommitted barn content is *silently
  absent* for consumers (they install from a clone), which is the one working-tree
  state that corrupts a publish. Dirty files elsewhere in the repo are not
  mentioned — they have no bearing on what consumers get.
- Commit **only the accumulated list plus any checked barn files**, never
  `-a`/`-A`.
- Commit message: pre-filled editable textfield, template `chore: share
  v<version>`.
- Tag `v<version>` on the same commit.
- **`git push --dry-run` immediately before the commit**, closing the race
  window since step 1 (someone else may have pushed meanwhile).

There is **no checkpoint commit**. The pre-wizard `HEAD` is already the rollback
anchor — the wizard authors exactly one commit — and a `-a`-equivalent
checkpoint would sweep the user's unrelated work-in-progress into a
wizard-authored commit.

### 6. Push

Pushes commit + tag to `origin`, for **all three callers**. Env-hardened
(`GIT_TERMINAL_PROMPT=0`, askpass disabled, timeout) so a missing credential
becomes a clean error instead of an indefinite hang with no TTY. On failure,
show the error plus the manual command.

(The repo-local `block-dangerous-git.sh` hook prevents *Claude* from pushing in
this repo. It is not a product policy and does not constrain shipped code.)

## Failure posture

Pre-flight verification over post-failure recovery: nothing needs undoing if
nothing was mutated. Every precondition is checkable without mutation —
`ls-remote` for credentials, `rev-parse --verify` / `ls-remote --tags` for tag
collisions, `push --dry-run` for push acceptance. This mirrors the marketplace's
existing `dry_run()` → `install()` pairing (`library_manager.py:273`).

For genuinely transient failures (network drop mid-push), the failed step is
retryable in place. Where a state change is required first (a tag that already
exists), the error panel shows the exact command.

**The wizard never runs a destructive git command.** Everything it does is
additive: write, add, commit, tag, push.

## CLI

`haywire share` becomes an interactive `SharePipeline` runner, replacing today's
flag-driven shape:

- **interactive** (default) — prompts through the same steps as the wizard.
- **`--check`** — read-only verifier. Runs drift detection and computes what
  docs/marketstall regeneration *would* write, diffs against committed state,
  reports everything stale, exits non-zero. Writes nothing, commits nothing,
  pushes nothing. This is what a PR gate wants; no CI currently calls `share`,
  so there is no compatibility burden.
- **`--yes`** — non-interactive full run with flag-supplied answers, for
  tag-triggered release automation and for the test suite (testing a seven-step
  git-mutating pipeline through a prompt loop is otherwise miserable).

`--ref`/`--tag` survive on `--check`/`--yes` for a poweruser wanting a frozen
feed URL. The default stays branch-live: `marketstall.toml` is a
**subscription feed**, so a branch-pinned URL means a subscriber added once
keeps discovering every future release, while a tag-pinned URL freezes them at
the version they subscribed to.

## Deferred: install pinning

`install_spec` carries **no ref** today
(`git+https://host/repo.git#subdirectory=barn/haybale-x`), so consumers always
install default-branch HEAD regardless of what `min_version` advertises. Pinning
it to the release tag would make published versions genuinely reproducible.

Verified mechanics: the `@tag` suffix must **not** go into the
`[tool.uv.sources]` dict's `git` value — uv treats it as part of the URL path
and the clone 404s. It needs a separate `tag = "v0.3.1"` key, which uv then
locks to the resolved SHA. PEP 508's `git+URL@tag#subdirectory=` spelling is
fine in `install_spec` itself; `_parse_git_install_spec`
(`library_manager.py:38`) must split it out and `_write_install_to_pyproject`
must emit the `tag` key.

Deferred because it changes **what every consumer installs** — a far larger
blast radius than a publish wizard — and needs its own thinking about how a
pinned consumer moves to a new version (presumably feed refresh rewrites the
spec). Folding it in would make the wizard hostage to a marketplace-wide
behaviour change. See `.insights/project_git_url_publishing_traps.md`.

## Adjacent: `haywire init` scaffolding fixes

### `.gitignore`: anchor the root-only patterns

The scaffolded `.gitignore` ships a live trap. `build/`, `dist/`, and `env/` are
unanchored, so they match at **every depth** — including inside
`barn/<lib>/<module>/`, where they silently exclude library content. Since
consumers install from a clone, ignored ⇒ absent for everyone. No user edit is
required to hit this; it ships broken.

Fix: anchor them (`/build/`, `/dist/`, `/env/`, `/venv/`, `/.venv/`).

No share-time detection of ignored files. After anchoring, the patterns that
still match at depth (`__pycache__/`, `*.egg-info/`, `*.egg`) are all
*correctly* ignored, so a warning would fire on every run for a fresh library
and train users to skip it. And an edited `.gitignore` is an expression of
intent — warning about it second-guesses the user.

Instead, two comments (the person about to edit the file is the one who needs
the knowledge):

```gitignore
# Patterns below are anchored with a leading slash (/build/) so they match only
# at the repo root. An unanchored pattern (build/) matches at EVERY depth —
# including inside barn/, where it would silently exclude your library's own
# files. See the note at the end of this file before adding patterns.
```

```gitignore
# ── Before you add a pattern ────────────────────────────────────────────────
# Anything ignored inside barn/<your-library>/ will be MISSING for everyone who
# installs your library — haywire share publishes by git URL, so consumers get
# a clone of this repo, not a built package. If a pattern is only meant for the
# repo root, anchor it with a leading slash: /build/ not build/.
```

### `.gitattributes`: scaffolded, but **no LFS**

The earlier design proposed `git lfs install` plus `*.png filter=lfs`. Testing
killed it: git stores a ~130-byte pointer file, and a consumer **without
git-lfs installed** receives that pointer instead of the asset. The install
*succeeds* and the library breaks at runtime. Whether uv's clone smudges
depends on the consumer's global LFS config — something neither the publisher
nor Haywire controls or can detect. And `*.png` is exactly what a node
library's icons and skins would match, so the trap fires on the most common
case.

So: scaffold `.gitattributes` with text/eol normalization only, plus a comment
documenting the LFS-vs-publish trade-off. Don't arm the trap; document it where
the decision gets made — the same posture as the `.gitignore` comments.

## `SharePipeline` placement

Lives in `haywire_studio.share`, not `haybale-marketplace`. Matches the
established import direction: `_overview_edit_dialog.py` already does `from
haywire_studio.share import union_pyproject_deps`. `haywire_studio` is a
package, not a `@library`-decorated barn library, so Farmhand tool
*registration* still happens from `haybale-marketplace` per the Farmhand canon —
it just calls into `SharePipeline`.

The refactor is a full rewrite of the CLI-shaped functions, not an additive
layer: `share.py` has 10 `sys.exit` sites and 44 print/exit calls, clustered in
`share_library`, `bump_version`, and `_detect_library`. The reusable core
(`_build_entry_for_library`, `detect_share_drift`, `apply_drift_fix`,
`union_pyproject_deps`, `_derive_url`) is already clean. The six
`tests/test_share_*.py` files call `share_save_repo` and `bump_version`
directly and will need updating.

## Open items for the implementation session

- Exact dataclass/exception names for each step's return/error types.
- Farmhand tool granularity — one orchestrating tool vs. one per step (canon
  favors small composable tools; the Union/Replace decision needs a two-call
  detect-then-apply shape like `MarketplaceDryRunInstallTool` /
  `MarketplaceInstallLibraryTool`), and whether `--check`'s plan output is its
  own tool.
- Test plan for the commit file-scoping logic — explicit `git add <list>` vs.
  the barn-include checkbox — the part most likely to hide a git-plumbing
  subtlety.
