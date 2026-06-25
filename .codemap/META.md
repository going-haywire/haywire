# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-06-25 (6th refresh) |
| Commit | 45140b27f02a1516c2d3cf719badeaf41da19085 |
| Branch | master |
| Generator | codebase-cartographer |
| Modules mapped | 11 |
| Cross-cuts mapped | 3 |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation/refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | 5cd252d120509ae2bed07e37e4d195cba73569cb | 2026-06-25 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | 5cd252d120509ae2bed07e37e4d195cba73569cb | 2026-06-25 |
| haywire-core (whole pkg) | `packages/haywire-core` | 5cd252d120509ae2bed07e37e4d195cba73569cb | 2026-06-25 |
| haywire-studio | `packages/haywire-studio` | 04f329fb834520fcdc93e1db63af333b92af648c | 2026-06-25 |
| haybale-core | `barn/haybale-core` | 17d68a970a077ff8d587c46046adf97a98be1241 | 2026-06-25 |
| haybale-studio | `barn/haybale-studio` | c4c7b200fa76b7d83eee6b0bfd0813efc65c8caf | 2026-06-25 |
| haybale-graph-editor | `barn/haybale-graph-editor` | d1e7f8e40aaa4cf960d5444f223fe184cee4161d | 2026-06-25 |
| haybale-haystack | `barn/haybale-haystack` | ebc1fcd79d16a78301f79ef0ec8ec67f803fc51e | 2026-06-25 |
| haybale-marketplace | `barn/haybale-marketplace` | 398a83862e5630e49590315f59dd91f0ea73dc2f | 2026-06-25 |
| haybale-example | `barn/haybale-example` | ccee5c0d10069a1083e10b22bf9cf2af68e3d84f | 2026-06-25 |
| haybale-testing | `barn/haybale-testing` | cdffd8ee45bd84376fe2be947c705fa68d0209ad | 2026-06-25 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 4b2222974a3934381d48d49d0557ffc75e4e697c | 2026-06-25 |
| tests | `tests` | 913f908e64c21e868b03a406cbcb7ac5a135c7c7 | 2026-06-25 |
| docs | `docs` | 43b5880dab4f32da585a1d6ff1a188e4ff9d3e32 | 2026-06-25 |

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

Last check (2026-06-25, 6th refresh): 1 file with uncommitted changes (`.claude/settings.json`).

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

### Diff since b2e5340b

`659 files changed, 248733 insertions(+), 13065 deletions(-)` (major expansion: widget unification, clipboard, compatibility warnings, new docs/architecture/ADRs).

Changed modules: **all** (every module touched).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).
