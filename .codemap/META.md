# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-07-05 (7th refresh) |
| Commit | b07aca751da0cd2fa28ea169498c90f3bc1c6c09 |
| Branch | master |
| Generator | codebase-cartographer |
| Modules mapped | 11 |
| Cross-cuts mapped | 3 |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation/refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | 9abfb988f88b5f930ab41264fc2905884347e8ec | 2026-07-05 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | 5935247b3cc5f4cc6d1b65b06a43ea5ee3927b68 | 2026-07-05 |
| haywire-core (whole pkg) | `packages/haywire-core` | ffe5e5a40b5e8d37573fb4f22b147e24e163265f | 2026-07-05 |
| haywire-studio | `packages/haywire-studio` | bb703738bbcbcba1a6a1ec17889b5a21f32f9c99 | 2026-07-05 |
| haybale-core | `barn/haybale-core` | 3900ec57b9c6fa1cbb1ba40297e0d415aacacb97 | 2026-07-05 |
| haybale-studio | `barn/haybale-studio` | 6fd3252213b0846f34a3e2fb02773c1cd3c5d449 | 2026-07-05 |
| haybale-graph-editor | `barn/haybale-graph-editor` | 4e89edbaafbda81088f411c9e9768a6f5d788393 | 2026-07-05 |
| haybale-haystack | `barn/haybale-haystack` | 287501d31bbab15842e74c0a8abce2394052d9d4 | 2026-07-05 |
| haybale-marketplace | `barn/haybale-marketplace` | a5292f21b198862dd9f659c0569f3e4a05f01bb7 | 2026-07-05 |
| haybale-example | `barn/haybale-example` | ad4b7776cb469462c779abb6fe1e7c89b91c7348 | 2026-07-05 |
| haybale-testing | `barn/haybale-testing` | 41a98cec3ae7197fd5b9af5468533b22aaad211b | 2026-07-05 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 728840422d66a22446f0321ff9e012baac74a2ea | 2026-07-05 |
| tests | `tests` | e8bb12b9d62fd0e27d696c12467be824f930037f | 2026-07-05 |
| docs | `docs` | 6bd22598222b26ed28aaff7df7d4a09d0e594201 | 2026-07-05 |

> `barn/haybale-visiongraph` was tree `672b0163…` at the initial generation but is now **gitignored** (`.gitignore:211`) and untracked in HEAD — removed from hash tracking. It still exists on disk as a local-only library.

## Refresh Instructions

To refresh this map:

1. Run the codebase-cartographer skill — it will detect this META.md and perform an incremental update automatically.
2. Or manually:
   a. Run `git rev-parse HEAD:{module-path}` for each module above.
   b. Compare against the stored tree hash.
   c. Rewrite only the manifests whose hashes changed.
   d. Update this table and the Change Log below.

## Uncommitted Changes

If `git status --porcelain` shows uncommitted changes at refresh time, the map only reflects the last committed state.

Last check (2026-07-05, 7th refresh): clean (`git status --porcelain` empty at refresh time — the ADR-consolidation session's edits had already been committed as `b07aca75` before the refresh ran).

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). Reflected `core/marketstall` + `core/host` engine subsystems and the move of `library_manager.py` out of haywire-studio. |
| 2026-05-31 | a08a6931 | 2nd refresh — content updates to `haywire-core-engine` (new `graph/scheduler.py`, ADR 0002), `haybale-studio` (new `loop_scheduler.py`), `docs` (docs/components/{libraries,haybale-package} → docs/haybale/; library-manager → marketplace), `tests` (scheduler + dirty-sync + editor-base tests). Hash-only refresh on 7 modules; no module added/removed. |
| 2026-06-10 | b5068ae7 | 3rd refresh — full refresh across all modules. Major: ADRs 0003–0008, widget unification + BaseWidget, clipboard (copy/paste), node warnings/compatibility, ShowWidget strategy, Ports panel rendering, graph canvas selection rewrite, marketplace editor UX. Tests: 15+ new test files (widget, clipboard, compatibility, show-widget, scheduler-wait, etc.). UI: debug overlay, canvas/pan/zoom updates, nicegui-patches. Docs: 6 new ADRs, widget-canon rewrite, design-guide updates. |
| 2026-06-13 | 8cc9ff00 | 4th refresh — all 12 modules updated. Major: graph-editor refactored with `graph_save_as.py` extraction, haywire-studio new `rename.py` CLI, marketplace major refactor with 4 new editor submodules (`_overview_actions`, `_overview_edit_dialog`, `_overview_install_flow`, `_registry_utils`), panel rendering refactored (new `host_rendering.py`, `redraw_coordinator.py`), haybale-studio code/properties editor refactored, core new `storage.py`. Tests: 10+ new files (rename, library manager, workspace storage, panel rendering, etc.). Docs: ADR 0009, new `state-canon.md`, panel-canon updates. |
| 2026-06-17 | 51d1ac64 | 5th refresh — all 11 modules refreshed (hash changes across all). Changes: haywire-core UI updates, studio grid/canvas settings, haybale-core tick_emit node, haybale-marketplace graph_canvas_manager enhancements, haybale-haystack updates, haybale-studio editor refactors, haybale-graph-editor context menu fixes, tests coverage expansion, insights doc additions (nicegui_redraw_deletes_handler_slot.md). No modules added/removed; 3 uncommitted changes present (settings.toml, loop.haywire, Master.toml). |
| 2026-06-25 | 45140b27 | 6th refresh — all 11 modules refreshed (hash changes across all). Changes: haybale-core **new reroute node + reroute_skin** for graph flow management; haywire-core edge wrapper updates; haywire-studio grid/settings refinements; haybale-studio skin refactors (error/default/node skins); haybale-marketplace/haystack/graph-editor enhancements; docs updates (ADRs, glossary, library-canon); new test coverage; benchmark skill added (haywire-benchmark SKILL.md). No modules added/removed; 1 uncommitted change (.claude/settings.json). |
| 2026-07-05 | b07aca75 | 7th refresh — all 14 tracked module paths refreshed (hash changes across all); 11 module manifests. Major: the **settings↔DataField unification arc landed in full** — ADRs 0011 (tier collapse) → 0012 (JSON persistence) → 0013 (single-cell value model) → 0014 (promotion-as-direction), with two follow-up ADRs (0015 storage-key-id, 0016 cell-authoritative reads) fully merged as inline "Amendment" sections into 0014/0013 respectively and their standalone files deleted outright (not stubs) — cite 0013/0014 going forward, 0015/0016 no longer exist as files. New ADR 0017 (widget-selection-as-port-contract) also landed. Ripple effects across nearly every module: haywire-core-engine gained `node/promotion.py`, `settings/persistence.py`, `types/widget_model.py`; haywire-core-ui gained `elements/flyout.py` (hierarchical hover-flyout menus) and rewrote `panel/render_utils.py`/`setting_widget_model.py` around the shared-cell model; haybale-graph-editor's manifest had **stale folder architecture from before this refresh** and was corrected (`panels/graph/menu/{node,port,canvas,edge,selection}/` real structure) plus gained `panels/graph/menu/node/promote.py`; haybale-core saw INT/FLOAT/STRING/BOOL/widgets/adapters **hoisted out to `haywire.barn.builtin`**; haybale-studio/haystack/example/testing all migrated `setting[str]`-style hints to `setting[STRING]`-style IType markers and `choices=` to `widget_config={"options": ...}`; tests gained new ADR-0011–0017 characterization suites (flagged: `tests/core/` now has both legacy-prefixed and new unprefixed sibling dirs for the same areas, intent unclear — `⚠️ TODO`); docs' ADR range is now 0001–0014 + 0017 (0015/0016 retired). No modules added/removed. Working tree was clean at refresh time (ADR-consolidation edits already committed). |

### Diff since b2e5340b

`659 files changed, 248733 insertions(+), 13065 deletions(-)` (major expansion: widget unification, clipboard, compatibility warnings, new docs/architecture/ADRs).

Changed modules: **all** (every module touched).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).

### Diff for 7th refresh (45140b27..b07aca75)

`234 files changed, 24762 insertions(+), 22168 deletions(-)`

Changed modules: **all 14 tracked paths**. No modules added/removed.
Three modules (`haywire-studio`, `haybale-marketplace`, `haybale-TEST_A`) changed only a `pyproject.toml` version bump (0.0.24 → 0.0.25) — their manifests' documented source paths are byte-identical to 45140b27; only their tree hashes moved.
