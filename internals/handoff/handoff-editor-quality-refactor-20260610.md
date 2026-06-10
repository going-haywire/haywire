# Handoff: Editor architecture code-quality refactor (haybale libraries)

**Created:** 2026-06-10
**Repo:** `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo` (branch `master`, clean at start)
**Origin:** A `/thermo-nuclear-code-quality-review` of the editor module + its haybale implementations. This doc captures the agreed remediation plan so a fresh agent can execute it.

---

## Context & verdict (one paragraph)

The **core editor framework** (`packages/haywire-core/src/haywire/ui/editor/`) is solid — keep it. The problems are all in the **haybale implementations**, concentrated in the marketplace editor. The single worst offender is a 1739-line god-object editor that mixes UI rendering with filesystem I/O, package-management orchestration, dependency detection, graph-file patching, and HTTP fetching — none of which has direct test coverage. Two more cross-cutting issues: editors reaching into private service/slot internals where a public API should exist, and a busy-wait polling loop awaiting a modal result.

**Important correction surfaced mid-review:** a `LibraryManager` *already exists* at `barn/haybale-marketplace/haybale_marketplace/library_manager.py` (928 lines) and already owns install/uninstall/rename/dep orchestration. So the plan is **NOT** to create a new service — it is to move the editor's homeless logic *into the existing `LibraryManager`* (or `marketstall`/`share` where a closer home exists) and to make the editor call the manager's already-public API instead of its privates.

---

## Key files

| File | Lines | Role |
|---|---|---|
| `barn/haybale-marketplace/haybale_marketplace/editors/library_overview_editor.py` | **1739** | The god-object editor. Primary target. |
| `barn/haybale-marketplace/haybale_marketplace/library_manager.py` | 928 | **Existing** service — the correct home for moved logic. Already has `dry_run`, `install`, `uninstall_streaming`, `rename_project_library_streaming`, `update_library_identity`, `get_missing_dependencies`, `get_installed_dependents`, `is_installed`, `list_installed`, `_invalidate_caches`, `_sync_install_to_pyproject`. |
| `barn/haybale-haystack/haybale_haystack/editors/haystack_editor.py` | 877 | Cohesive but near the 1k boundary; needs the shared-modal + dedup extractions. |
| `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_editor.py` | 563 | Has a bespoke Save-As dialog + `set_dirty`/`_refresh_bar` private reach. |
| `barn/haybale-studio/haybale_studio/editors/code_editor.py` | 443 | Second consumer of the `set_dirty`/`_refresh_bar` private reach (lines 265–271). |
| `packages/haywire-core/src/haywire/ui/editor/wrapper.py` | 651 | `EditorWrapper.set_dirty` (line 227) — deliberately does NOT refresh the bar; this is the API gap. |
| `packages/haywire-core/src/haywire/ui/app/slot.py` | — | `_refresh_bar` (line 337, private); public `close_binding`, `repayload` exist. |
| `barn/haybale-studio/haybale_studio/editors/properties_editor.py` | 301 | The *good* reference editor. Aspire to this altitude. |

Canonical contract doc: `docs/components/editors/editor-canon.md`. Codemap: `.codemap/modules/haybale-graph-editor.md`.

---

## Implementation phases (ordered for safety: cheap wins → encapsulation fixes → the big extraction)

Each phase is independently shippable and testable. Run the baseline before any phase that touches signatures/types (see "Quality gates" below).

### Phase 0 — Safety net first
The marketplace orchestration/filesystem helpers have **no direct tests** (`grep` for `_install_package`, `_patch_graph_files`, `_detect_dependencies` in `tests/` returns nothing). Before moving logic, add unit tests against the *current* behavior of the functions that will move, so the extraction is provably behavior-preserving:
- `_patch_graph_files(graphs_dir, old_id, new_id)` — already a `@staticmethod`, trivially testable as-is.
- pyproject read/write round-trip (`_write_pyproject_deps`, the read in `_detect_dependencies`).
- dependency-blocking computation (the manual `_missing_deps` set at lines 477–485).
These tests then ride along to the new home unchanged.

### Phase 1 — Stop bypassing the existing `LibraryManager` public API

**NOT pure "no behavior change" — see RESOLVED DECISIONS below; it carries one intentional bug fix in the dependency-matching key.**

- Replace the manual missing-dep computation at `library_overview_editor.py:477-485` with a **new** public method `manager.get_missing_dependencies_for_package(pkg: Haybale, *, require_enabled: bool) -> list[str]` (the existing `get_missing_dependencies(lib_id, ...)` answers a *different* question — post-install health of an installed lib, not pre-install gating of a not-yet-installed `marketplace_pkg`). Editor calls the new method with `require_enabled=False` (matches current "installed-at-all" gating). See Q2.
- Replace `manager._norm` direct calls (lines 478, 484) — folded into the new method; no `_norm` reach left at the UI.
- The post-rename/identity rescan dance in the editor (lines 1270-1272) duplicates the manager's internal rename/identity paths. **Verify `rename_project_library_streaming`/`update_library_identity` internals before folding** — risk is dropping a rescan the editor relies on vs. de-duping a double-rescan. Split into its own commit so a regression is bisectable.

#### RESOLVED DECISIONS (inquisition 2026-06-10) — read before coding Phase 1

The review surfaced a **second, deeper bug** in dependency matching, fixed inline as part of this work (user chose strictness + loud diagnostics):

1. **Canonical dependency key = top-level `module_name`, not `distribution_name` or short `id`.** `@library(dependencies=[...])` entries are top-level Python package names (e.g. `"haybale_core"`), equal to the dependency's `LibraryIdentity.module_name` top package. This was *already* the documented contract (glossary "Dependency manifests" row; `detect_deps` already emits module names) — the bug is purely in the marketplace **consumer** code, which matches against the wrong field.
2. **`_lib_norm_aliases` (library_manager.py:715-726) is built on the wrong field** — it uses `distribution_name` + short-id fallback. `distribution_name` is **empty for folder installs** (`info.py:23-24`, `discovery.py:109`), so the id-fallback exists only to paper over that gap, and it leniently accepts malformed bare-id declarations. Rewrite it to match against **`module_name`, top-package-normalized** (`module_name.split(".")[0]`, then `_norm`). This drops the id-alias (the strictness goal) WITHOUT regressing folder installs, because `module_name` is populated for every install type. Rename it to reflect reality (e.g. `_lib_module_norm`). All three consumers (`get_installed_dependents`, `get_missing_dependencies`, new `get_missing_dependencies_for_package`) flow through it.
3. **`module_name` matching must be top-package-normalized** (Q5 = A) — `__module__` may be a submodule (`haybale_x.library`); the declared dep is the top package. Split on `.`, take `[0]`, both in the gate and validation.
4. **Behavior change introduced (a bug fix):** fewer false "dependency missing" install blocks in the dist-name/short-id mismatch case; folder-installed dependencies now correctly recognized. Strict superset of "satisfied" — can never *add* a block. Phase 0 test for this is **red→green** (Q3 = A): write the test against the correct module_name-aware expectation; it fails on current code, passes after the fix. Phase 0/Phase 1 are not cleanly separable for this one function (adjacent commits).
5. **Core-layer touches (confirm shape before deep impl per CLAUDE.md — DONE here):**
   - `base.py:876` comment lies ("Dependencies are library IDs") — the *code* is already correct (uses `module_name`); fix only the comment.
   - **Load-time validation:** warn when a declared dependency matches no installed library's top-`module_name` and isn't an importable package — makes the silent-hot-reload-break class loud.
   - Correct the "distribution name" docstrings at `library_manager.py:718` and `registry.py` (they contradict the glossary).
6. **Glossary updated inline** (`docs/reference/glossary.md`, "Dependency manifests & drift" row) — sharpened to name `module_name` as canonical key and flag dist-name/short-id as wrong keys. No new term needed.

### Phase 2 — Close the `set_dirty` / `_refresh_bar` API gap (core framework, 2 consumers)
- Add a public way to refresh the tab bar after a dirty change. Options: `EditorWrapper.set_dirty(value, *, refresh: bool = False)` OR a separate `EditorWrapper.refresh_bar()`. `set_dirty` is intentionally lazy (see wrapper.py:227 docstring) — keep the lazy default, make refresh opt-in.
- Delete the duplicated `getattr(self.wrapper, "_slot", None); slot._refresh_bar()` dance in **both** `graph_editor.py:334-337` and `code_editor.py:265-271`.
- This is a core-framework change touching 2 libraries; run the full suite.

#### RESOLVED DECISIONS (inquisition 2026-06-10)

- **API shape = Option A (Q6):** `EditorWrapper.set_dirty(value, *, refresh: bool = False)`. Lazy default preserved; eager refresh opt-in. Consumers collapse to one call: `self.wrapper.set_dirty(is_dirty, refresh=True)`. Wrapper already owns `self._slot` (wrapper.py:137), so the refresh lives in the wrapper: `if refresh and self._slot is not None: self._slot._refresh_bar()` (optionally promote `Slot._refresh_bar` → public `refresh_bar()` so the wrapper→slot call is clean too).
- **Error handling = Option B (Q7): swallow-with-log, not bare swallow, not propagate.** Rationale: `_refresh_bar` re-renders the *whole* tab bar, and `TabSlot._render_bar_contents` calls `wrapper.render_tab_into()` for **every** bound editor (tab_slot.py:84) — so one editor's buggy `draw_tab` can break an *unrelated* editor's save flow. Genuine cross-editor blast radius justifies resilience; the `logger.warning(...)` stops it being silent. `_refresh_bar` already self-guards the `_bar_container is None` case (slot.py:339-340), so that benign path needs no catch.
- **Implementer heads-up:** the existing bare `except Exception: pass` may be masking a pre-existing silent `render_tab_into` failure. Adding the log could surface a real, currently-hidden exception the moment this lands — that's correct (it's a real bug to fix), not a regression introduced by the refactor.

### Phase 3 — Push state-keeping into the state object (atomicity + cross-session correctness)

- `haystack_editor.py:842-843` mutates `hs._haystack_settings.last_haystack_name` after `rename_haystack` to keep it in lockstep (the comment admits the coupling). Move this into `HaystackState.rename_haystack` so the rename is atomic and the editor stops touching `_haystack_settings`. Also remove the `hs._haystack_dirty` private read at `haystack_editor.py:126` if a public accessor can be added.

#### RESOLVED DECISIONS (inquisition 2026-06-10)

- **Scope clarification:** Phase 3 is the **haystack (graph-selection TOML file) rename**, NOT a library rename. A *Haystack* is a named curated selection of open graphs in `haystacks/*.toml` (glossary line 259). Don't conflate with the marketplace library rename (Phase 1/6) or graph Save-As (Phase 4).
- **Decision = Option B (Q8): fold BOTH the `last_haystack_name` lockstep AND the cross-session broadcast into `HaystackState.rename_haystack`.** After a successful `_rename`: (a) if `last_haystack_name == old_name`, set it to `new_name`; (b) call `self._broadcast_data_mutated()`.
- **This fixes a latent cross-session bug, not just a smell.** Every OTHER `HaystackState` mutator (`add_entry`, `remove_entry`, reassembly path: lines 175, 224, 251, 300, 326…) calls `_broadcast_data_mutated()` — `rename_haystack` (state/haystack_state.py:468-473) is the **lone exception** that doesn't broadcast. Today the editor compensates with a session-*local* `_notify_data_mutated(context)` (editor:847), so **peer sessions never learn about a rename** — session B keeps showing the old name after session A renames. Folding the broadcast into the state method fixes this (peers are `@redraw_on(... GraphDataMutated ...)`, editor:68). `_broadcast_data_mutated` is documented as the "centralising" broadcast point (state:141).
- **`last_haystack_name` is shared single state** (lives in `_haystack_settings`, an AppState field — not per-session), so updating it once in `rename_haystack` fixes the pointer for ALL sessions. No per-session fixup needed.
- **Editor collapse:** lines 839-847 reduce to `rename_haystack(...)` + the success toast (toasts are legitimately session-local UI). Drop the editor's local `_notify_data_mutated` for rename — the broadcast covers this session too.
- **(2) Dirty accessor:** add a public `is_haystack_dirty` property on `HaystackState`; editor reads it at line 126 instead of `_haystack_dirty`. (`_mark_haystack_dirty`'s docstring already says it's "Consumed by HaystackEditor" — formalize that with a getter.)
- **NOTE — original Q8 recommendation was reversed during the interview:** I first recommended NOT broadcasting from rename on the false premise that mutators don't broadcast. They do. Rename was simply missing it. Don't reintroduce the "keep broadcast in editor" idea.

### Phase 4 — De-duplicate save-path logic + unify Save-As UI
- `_default_save_dir` is duplicated verbatim in `graph_editor.py:374` and `haystack_editor.py:486` (and a near-copy in `haystack_state.py:463`). Extract one helper (`workspace_root/graphs` fallback) to a shared home.
- `GraphEditor` has a bespoke ~140-line Save-As dialog (`_build_save_as_dialog`, `_do_save_as`, `_clear_exists_warning`, `_open_save_as_dialog`, lines 422-546) while `HaystackEditor` already uses the canonical `save_as_modal` + `confirm_modal` overwrite flow from `haywire.ui.modals`. Migrate `GraphEditor` onto `save_as_modal`; delete the bespoke dialog and its 5 instance fields (`_save_base_dir`, `_save_base_dir_label`, `_save_path_input`, `_save_exists_warning`, `_save_as_dialog`).
- After this, `haystack_editor.py` falls comfortably back under 1k.

#### RESOLVED DECISIONS (inquisition 2026-06-10)

- **Shared home = `haywire-core` (Q10 = A).** Put the `_default_save_dir` helper (`workspace_root/graphs` with fallback to `workspace_root`) in core (e.g. `haywire.core.workspace` / a path-utils module). Rationale: the `graphs/` directory convention is part of the framework workspace model, and core is importable by every barn lib with **no new dependency edges**.
- **Do NOT put it in `haywire-studio` (Q10 = B rejected) — user intent is to DISENTANGLE `haybale_graph_editor` from studio, not couple them.** `haybale-graph-editor` declares `dependencies=[]`; adding a studio dep just to share a 4-line path helper would push it the wrong way. (Studio-home was the tempting "studio owns workspace config" option — explicitly declined.)
- **Fold `haystack_state.py:463` in too** — its inline `workspace/graphs` resolution should use the same core helper for the *base dir*, even though its operation (`rglob` scan) differs from the editors' (default-dir pick). One source of truth for "where graphs live."
- **Save-As unification unchanged from original plan:** migrate `GraphEditor` onto the canonical `save_as_modal` + `confirm_modal` overwrite flow (as `HaystackEditor` already does); delete the bespoke ~140-line dialog + its 5 instance fields.

#### RELATED FUTURE WORK surfaced during this interview (OUT OF SCOPE — separate sessions)

These came up while resolving Phase 4. They are **not** part of this editor refactor; captured here + in memory so they aren't lost.

- **Thread 2 — disentangle `haybale_graph_editor` from `haywire-studio`.** graph-editor already declares `dependencies=[]`, so any studio coupling is at the *import* level, not declared. Phase 4's core-home decision avoids *adding* coupling. A full audit/disentangle is its own task. (Run `haywire-dep-check` to surface actual cross-package imports.)
- **Thread 3 — per-library persistent-storage mechanism under `GLOBAL_CONFIG_DIR / "db" / "<haybale-library>"`.** Today only `GLOBAL_MARKETPLACE_DIR` (`studio/config.py:23`) exists — hardcoded for one library. Intent: a managed mechanism so ANY haybale library can claim/access `db/<library>/` for persistent files. This is a new subsystem (allocation, lifecycle, ownership-on-uninstall, hot-reload interaction) — deserves its own `design` session. Entangled with Thread 2 (both about library boundaries) and the existing `project_install_hotreload_fix` memory (uninstall already touches library dirs). **May reshape what Phase 6 should relocate — but per the Q11 decision, Phase 6 proceeds as planned and Thread 3 is designed separately.**

### Phase 5 — Replace the busy-wait modal poll (correctness)
- `_install_package` at `library_overview_editor.py:1519-1540` uses a `confirmed = {"value": False}` dict polled in a `for _ in range(600): await asyncio.sleep(0.1)` loop to await the upgrade-impact modal decision. It can't distinguish cancelled vs timed-out (both abort silently), and the button enable/disable cleanup is copy-pasted 3×.
- Replace with an `asyncio.Future`/`Event` the modal resolves (or make `upgrade_impact_modal` awaitable and return the decision). Wrap button enable/disable in a single `try/finally`.

#### RESOLVED DECISIONS (inquisition 2026-06-10)

- **Decision = Option A (Q9): `asyncio.Future` bridged to the modal's existing callbacks.** `fut = asyncio.get_event_loop().create_future()`; pass `on_continue=lambda: fut.set_result(True)` and `on_cancel=lambda: fut.set_result(False)` (the modal *already* accepts `on_cancel` — the editor just never passed it, which is why cancel vs. timeout were indistinguishable). `decision = await fut`. **Drop the artificial 60s timeout** — a user-decision modal shouldn't time out. Single `try/finally` for button enable/disable.
- **Do NOT make the modal awaitable (Option B)** — every modal in the codebase is callback-based (`confirm_modal`, `save_as_modal`, `install_safety_modal`); an awaitable modal would be a one-off inconsistent pattern. If awaitable modals are ever wanted, that's a separate codebase-wide decision (ADR-worthy), not a Phase-5 side effect.
- **Do NOT move the post-decision logic into the `on_continue` callback (Option C)** — actively contraindicated. See context below.
- **CONTEXT — the await chain is deliberate UX architecture, not just a slot-context hack (do not "simplify" it away):**
  - Call chain: Install button → `_install_with_safety_check` → `install_safety_modal(on_install=...)` where `_on_install` **returns** the `_install_package` coroutine → the safety modal **awaits** it. This deliberate return-don't-schedule keeps everything on **one asyncio task** so the NiceGUI slot stack stays valid (slot stack is per-task; `ensure_future` starts empty — `.insights/feedback_nicegui_async.md`, Case 1).
  - `_install_package` is a 3-step coroutine: `await dry_run` → upgrade-impact gate (the busy-wait) → `await library_operation_progress_modal(...)`. **Step 3 streams a live progress popup for the (slow) install** — the await chain is what keeps the coroutine alive to drive that progress feedback. Option C (fire-and-forget callback) would break the progress UX, not just the notify.
  - Option A preserves this backbone exactly: `_install_package` stays a single awaited coroutine; only the upgrade-impact gate changes from poll → `await fut`. Steps 1 and 3 untouched.
  - **Alternative considered & rejected for Phase 5:** capture `client = ui.context.client` then `with client: ui.notify(...)` (the `.insights/feedback_nicegui_redraw_deletes_handler_slot.md` pattern) *could* free `ui.notify` from the await chain — but the progress-modal *creation* (Case 2: creating UI in a task) still needs live context, and you'd have to audit every notify site in `_install_package`. Bigger/riskier than the busy-wait fix and unnecessary. Documented so a future agent knows it's possible if the await chain ever becomes a real constraint.

### Phase 6 — The big extraction: shrink `LibraryOverviewEditor` under 1000 lines
Now that tests exist (Phase 0) and the manager is the agreed home (correction above), move the homeless logic out:
- **Filesystem/orchestration → `LibraryManager`** (or `marketstall`/`share`):
  - `_patch_graph_files` (staticmethod, line 1395) + the patching half of `_build_graph_patch_dialog`. NOTE: it walks `graphs/**/*.json` — graph-domain territory. `LibraryManager` is defensible (it performs the rename that necessitates the patch); the closer alternative is `marketstall`/`share` (the editor already imports `haywire_studio.share.union_pyproject_deps` at line 1119). Pick one, document why.
  - `_detect_dependencies` (143 lines) pyproject diffing + `_write_pyproject_deps` → fold into `haywire.core.library.dep_detect` / the manager.
  - The HTTP fetch `_fetch_marketplace_overview` / `_github_raw_base` / `_load_marketplace_overview` (lines 1620-1740) → a `MarketplaceState` / service method. The editor should render the result, not fetch from GitHub/PyPI.
- **Collapse repetition inside `_render_center` (the 480-line method, lines 214-696):**
  - Action-button block (337-520): four near-identical *blocked-button* branches (disable/enable/uninstall/install) each wiring an inline `info_modal`. Extract one `_action_button(label, icon, *, block_reason, on_click, color)` helper. Deletes ~120 lines.
  - The 12 `_make_tab_panel(...)` calls (587-677) iterate `(tab, registry, TabConfig)` — `TabConfig` already exists. Build a list and loop. ~90 lines → ~10.
- Target: editor well under 1000 lines, doing only render + dispatch.

#### RESOLVED DECISIONS (inquisition 2026-06-10) — MAJOR scope change to the rename path

The original Phase 6 assumed library rename stays in the editor and only the graph-patch *helper* relocates. **User redirected: remove library rename from the editor entirely and relocate the whole operation to a new `haywire rename` CLI.** The graph-patch foot-gun (blunt `old_id:`→`new_id:` string replace across all `graphs/**/*.json`, mutating unopened user files in place with no rollback) dissolves into the CLI, done properly.

**Confirmed-safe homes for the OTHER two extracted chunks (Q12, unchanged):**
- HTTP fetch (`_fetch_marketplace_overview`/`_github_raw_base`/`_load_marketplace_overview`, 1620-1740) → **`MarketplaceState`** (already an `AppState` with `refresh()`/`get_global()`/`get_project_haybales()` — the data layer). Editor renders, doesn't fetch.
- `_detect_dependencies` + `_write_pyproject_deps` → **`haywire_studio.share`** (already owns `union_pyproject_deps`, `_read_library_dependencies`, `_norm_dep`).

**Rename removal from editor (Q14 = B):**
- Remove the full rename path: `_do_rename` (1290), the rename branch of the edit dialog, AND the graph-patch code (`_patch_graph_files` 1395, `_build_graph_patch_dialog` 1342) + its call site (1323-1336).
- **Also pull `rename_project_library_streaming` OUT of `LibraryManager`** into the new CLI (verified: it has **exactly one caller**, editor:1308 — safe to relocate). `update_library_identity` **stays** on `LibraryManager` (one caller, editor:1260) — identity-only edits (label/desc/url) remain in the editor and are safe in-app (no dir rename, no `uv sync`).
- Name field → **read-only + info button**.

**Editor info-button UX (Q17):**
- (a=A) **`info_modal`** (the editor's existing pattern) with step-by-step: stop studio → `uv run haywire rename haybale-<current> <new-name>` (command **pre-filled with this library's current dist-name**, copyable) → restart.
- (b=A) Include a **one-line why:** renaming rewrites installed packages and runs `uv sync`, which isn't safe while studio is running (hot-reload corruption hazard — see `project_install_hotreload_fix` memory).

### NEW FEATURE (designed this session, BUILD SEPARATELY): `haywire rename` CLI

A new studio CLI subcommand. **Designed in the inquisition 2026-06-10; not yet built.** See `project_haywire_rename_cli` memory.

- **(Q15a = A) Lives in `packages/haywire-studio/src/haywire_studio/rename.py`** (sibling of `share.py`), wired into the `app.py:272` argparse router as a `rename` subparser (alongside `init`/`share`). Rename is studio/workspace-shaped (touches `barn/`, project `pyproject.toml`, `.haywire/marketplace.toml`, runs `uv sync`) — studio's domain, not core.
- **(Q15b = A) Signature: `haywire rename <old-library> <new-name>`** — both explicit (destructive + rare ⇒ no auto-detect magic; may borrow `share`'s single-library auto-detect only as a convenience default for `<old>`).
- **Reuses the relocated `rename_project_library_streaming` logic** (dir renames + 4-file rewrites + `uv sync`). Runs with **studio stopped** — which is the architecturally correct way to do it (no live registry/DI/hot-reload state to corrupt; sidesteps the whole `project_install_hotreload_fix` hazard class).
- **Graph-patch step — bundled into `rename` as one atomic operation (Q16), done right:**
  - (a = C) **JSON-aware key-scoped replace** (replace `old_id:` only in registry-key fields, NOT anywhere the substring appears — eliminates false-match on user values) **+ dry-run preview + backup** before writing.
  - (b = A) **Dry-run by default; `--apply`/`--write` required to mutate.** Print every file+change, exit. Honors the "stop silent rewrites" goal that motivated moving this out of the editor.

---

## Quality gates (from CLAUDE.md)

Before substantial phases, establish a baseline, then re-run after:
```sh
uv run ruff check <path>
uv run mypy <path>
```
Full repo gates (CI parity):
```sh
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/haywire-core/src/ packages/haywire-studio/src/ barn/haybale-core/haybale_core/ barn/haybale-studio/haybale_studio/ barn/haybale-testing/haybale_testing/ barn/haybale-example/haybale_example/ barn/haybale-TEST_A/haybale_test_a/
uv run pytest        # full suite after every multi-file change
```
Test-file gotcha: import `haywire.core.graph.editor` before other haywire modules (circular import). See CLAUDE.md "Testing".

The codebase starts with **zero** ruff/mypy errors — anything new is introduced by this work. If the baseline is dirty, stop and surface it interactively (per CLAUDE.md).

---

## Guardrails / things NOT to do

- **Do not create a new service** — `LibraryManager` already exists; use it. (This was a live correction during the review.)
- **Do not special-case `GraphEntry` in `haybale-graph-editor`** — the `GraphContainer`/`GraphAppState` boundary is deliberately source-agnostic and is the strongest abstraction in the area. Keep it intact.
- Don't switch the DI context to `ContextVar` (breaks hot-reload — see `.insights/project_di_context.md`).
- Watch the redraw-deletes-handler-slot trap when a row handler mutates state then redraws its own container — capture `ui.context.client` first (`.insights/feedback_nicegui_redraw_deletes_handler_slot.md`). The haystack editor already does this correctly at lines 327-333, 684-687; preserve that pattern when refactoring.
- Architecture changes that touch class hierarchies / DI / ownership: confirm with the user first (CLAUDE.md). Phases 2 and 6 (new public API; moving logic across package boundaries) qualify — get a thumbs-up on the *shape* before deep implementation.

---

## What's confirmed good (leave alone)

`EditorWrapper` error-phase isolation + `_make_handler_closure` late-binding fix; `GraphContainer`/`GraphAppState`; `PropertiesEditor` + `PanelRedrawCoordinator`; `NodePortsPanel._anchor_cleanup_to_element`.

---

## Suggested skills for the next session

- **`writing-plans`** — if the user wants this handoff turned into a tracked, checkbox plan before coding.
- **`design`** — BEFORE Phase 2 (new `EditorWrapper` public API) and Phase 6 (cross-package logic relocation). These touch ownership/API boundaries; CLAUDE.md requires confirming architectural decisions. The design interview is the right gate.
- **`subagent-driven-development`** or **`executing-plans`** — to run the independent phases.
- **`haywire-codesanitizer`** / **`verify`** — run the full lint+type+test suite to confirm clean between phases.
- **`haywire-libs`** — load the library-plugin-system docs if touching `LibraryManager` / `register_components` wiring.
- **`check-rename`** — after any method/class moves between modules (catches string-based `patch(...)` / doc references the IDE misses).

---

## First action for the next agent

Confirm with the user which phase to start (recommend Phase 0 then Phase 1 — lowest risk, immediate payoff). Phase 1 is pure reuse cleanup against `LibraryManager`'s existing public API and needs no new design decisions.
