# Handoff: Deferred work after the editor-quality refactor lands

**Created:** 2026-06-10
**Repo:** `/Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo` (branch `master`)
**Purpose:** Track the follow-up work that was deliberately deferred while scoping/planning the editor-quality refactor, so a fresh agent can pick it up **once that plan has landed**.

---

## Precondition

This handoff assumes the implementation plan **`docs/superpowers/plans/2026-06-10-editor-quality-refactor.md`** is merged. Do not start the items below until that plan's Part A (rename CLI) + Part B (Phases 0–6) are complete and the CI-parity gate is green. The plan and the design rationale behind it live in:

- Plan: `docs/superpowers/plans/2026-06-10-editor-quality-refactor.md`
- Design decisions / interview record: `internals/handoff/handoff-editor-quality-refactor-20260610.md` (the per-phase `RESOLVED DECISIONS` blocks)
- Memories: `project_haywire_rename_cli`, `project_per_library_storage_dir` (in the auto-memory dir)

Do not duplicate those here — read them first.

---

## Deferred items (priority order)

### 1. `check-rename` sweep — mechanical, do FIRST after merge
The refactor moves methods across module boundaries (`rename_project_library_streaming` leaves `LibraryManager` → `haywire_studio.rename`; the marketplace HTTP fetch → `MarketplaceState`). The IDE updates Python imports but misses string-based references (`patch("module.Symbol")`, `patch.object`, `importlib.import_module`, doc citations).

- **Action:** run `/check-rename` across `tests/`, `barn/`, `docs/`.
- **Why now:** a stale `patch(...)` makes the suite red; this is cleanup *of* the plan, not new work.
- **Note:** the plan's Task B6 Step 4 does a *targeted* grep, but a full sweep is broader. If the plan added a `check-rename` task as its final step (was offered), this may already be done — verify before repeating.

### 2. Disentangle `haybale_graph_editor` from `haywire-studio`
User's stated goal (surfaced during the Phase-4 interview). `haybale-graph-editor` already declares `dependencies=[]`, so any coupling is at the **import** level, not declared. The Phase-4 decision (save-dir helper → `haywire-core`, not studio) already avoids *adding* coupling.

- **First action (diagnostic, not a fix):** run `/haywire-dep-check` to surface actual cross-package imports from graph-editor into studio.
- **Then:** decide per-import whether it moves to core, gets inverted, or is acceptable. This is a scoping task — expect a `design` or `writing-plans` pass before touching code.
- **Entangled with item 3** (both are about library boundaries).

### 3. Per-library `db/<library>/` persistent-storage mechanism — UNDESIGNED, needs a design session
Generalize the hardcoded `GLOBAL_MARKETPLACE_DIR` (`packages/haywire-studio/src/haywire_studio/config.py:23`, currently `GLOBAL_CONFIG_DIR / "db" / "haybale-marketplace"`) into a managed mechanism so **any** haybale library can claim/access `~/.haywire/db/<library>/` for persistent files.

- **Status:** intent only — NOT designed. Full open-questions list is in the `project_per_library_storage_dir` memory (allocation/ownership, lifecycle-on-uninstall, hot-reload interaction, naming key = id vs module_name, home = core vs studio).
- **First action:** a `design` interview (this is a new subsystem touching DI/lifecycle — CLAUDE.md requires confirming architectural decisions). Entangled with the `project_install_hotreload_fix` memory (uninstall already touches library dirs) and item 2.

### 4. ADR(s) — optional, author's call
Two decisions from the planning interview meet all three ADR criteria (hard to reverse, surprising without context, real trade-off with genuine alternatives):

- **(a)** `module_name` (top-package-normalized) as the canonical `@library` dependency-matching key — rejecting `distribution_name` and short-`id`. Touches core + marketplace + load-time validation.
- **(b)** Relocating library rename to an out-of-process `haywire rename` CLI (studio stopped) — chosen for the `uv sync`/hot-reload-corruption hazard.

- **Suggested shape:** one ADR for (b) (the meatier, more surprising decision); fold (a) into it or leave it documented in `glossary.md` (already updated). Author was offered this during planning and deferred the decision.
- **Format:** `docs/adr/NNNN-*.md` (see existing ADRs for the template; CLAUDE.md references ADR 0002).

---

## NOT in scope here / already handled
- The two bug fixes (module_name dep matching; cross-session haystack rename) are **in the plan** (Tasks B1, B3) — not deferred.
- `glossary.md` is already updated (module_name canonical key) — committed as part of the interview, no further glossary work needed for item 4(a).

---

## Suggested skills for the next session
- **`check-rename`** — item 1 (run first).
- **`haywire-dep-check`** — item 2 (diagnostic first step).
- **`design`** — item 3 (new subsystem; mandatory architectural confirmation per CLAUDE.md). Possibly item 2 if the disentangle turns structural.
- **`writing-plans`** — after the design interviews for items 2/3, to produce executable plans.
- **`haywire-libs`** — load library-plugin-system docs if item 3 touches `register_components` / DI wiring.
- **`verify` / `haywire-codesanitizer`** — gate between items.
