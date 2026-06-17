# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-06-17 (5th refresh) |
| Commit | 51d1ac649ef2c8c8e7042456ce37415b570022f2 |
| Branch | master |
| Generator | codebase-cartographer |
| Modules mapped | 11 |
| Cross-cuts mapped | 3 |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation/refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | de4de04c7f8081a32fe44fd4b27ebf00449628ef | 2026-06-17 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | de4de04c7f8081a32fe44fd4b27ebf00449628ef | 2026-06-17 |
| haywire-core (whole pkg) | `packages/haywire-core` | de4de04c7f8081a32fe44fd4b27ebf00449628ef | 2026-06-17 |
| haywire-studio | `packages/haywire-studio` | f79ff7a13c7b19d2b912cde2565e80813df686a0 | 2026-06-17 |
| haybale-core | `barn/haybale-core` | b32c728b1b35f6e79686dc6c4e8cbf228657f775 | 2026-06-17 |
| haybale-studio | `barn/haybale-studio` | 18c6dab24dd5fcbdc447687645cc015fc7242829 | 2026-06-17 |
| haybale-graph-editor | `barn/haybale-graph-editor` | 7902ef680586e69c6329bf6de6c9ec35a8db69f8 | 2026-06-17 |
| haybale-haystack | `barn/haybale-haystack` | 6832333f368a9f680a539c016e167be0ba4504e0 | 2026-06-17 |
| haybale-marketplace | `barn/haybale-marketplace` | bcf7bba2f74751d9ee0919fa47f77257ea0417d1 | 2026-06-17 |
| haybale-example | `barn/haybale-example` | 0425b23b96ec267eba8cbc65a0ca9f98e62dc2b8 | 2026-06-17 |
| haybale-testing | `barn/haybale-testing` | 39db23d3fdfd159ba41eba00d12c2c177534a316 | 2026-06-17 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 2e4b71662527809d9bc7b844690e77bb4a4322fe | 2026-06-17 |
| tests | `tests` | 7077a73833c0c609ad9ef0e9ff74e6086267c726 | 2026-06-17 |
| docs | `docs` | 4191941554dd8e97fd63298e43e1f51babf7091a | 2026-06-17 |

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

Last check (2026-06-17, 5th refresh): 3 files with uncommitted changes (`.haywire/settings.toml`, `graphs/loop.haywire`, `haystacks/Master.toml`).

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). Reflected `core/marketstall` + `core/host` engine subsystems and the move of `library_manager.py` out of haywire-studio. |
| 2026-05-31 | a08a6931 | 2nd refresh — content updates to `haywire-core-engine` (new `graph/scheduler.py`, ADR 0002), `haybale-studio` (new `loop_scheduler.py`), `docs` (docs/components/{libraries,haybale-package} → docs/haybale/; library-manager → marketplace), `tests` (scheduler + dirty-sync + editor-base tests). Hash-only refresh on 7 modules; no module added/removed. |
| 2026-06-10 | b5068ae7 | 3rd refresh — full refresh across all modules. Major: ADRs 0003–0008, widget unification + BaseWidget, clipboard (copy/paste), node warnings/compatibility, ShowWidget strategy, Ports panel rendering, graph canvas selection rewrite, marketplace editor UX. Tests: 15+ new test files (widget, clipboard, compatibility, show-widget, scheduler-wait, etc.). UI: debug overlay, canvas/pan/zoom updates, nicegui-patches. Docs: 6 new ADRs, widget-canon rewrite, design-guide updates. |
| 2026-06-13 | 8cc9ff00 | 4th refresh — all 12 modules updated. Major: graph-editor refactored with `graph_save_as.py` extraction, haywire-studio new `rename.py` CLI, marketplace major refactor with 4 new editor submodules (`_overview_actions`, `_overview_edit_dialog`, `_overview_install_flow`, `_registry_utils`), panel rendering refactored (new `host_rendering.py`, `redraw_coordinator.py`), haybale-studio code/properties editor refactored, core new `storage.py`. Tests: 10+ new files (rename, library manager, workspace storage, panel rendering, etc.). Docs: ADR 0009, new `state-canon.md`, panel-canon updates. |
| 2026-06-17 | 51d1ac64 | 5th refresh — all 11 modules refreshed (hash changes across all). Changes: haywire-core UI updates, studio grid/canvas settings, haybale-core tick_emit node, haybale-marketplace graph_canvas_manager enhancements, haybale-haystack updates, haybale-studio editor refactors, haybale-graph-editor context menu fixes, tests coverage expansion, insights doc additions (nicegui_redraw_deletes_handler_slot.md). No modules added/removed; 3 uncommitted changes present (settings.toml, loop.haywire, Master.toml). |

### Diff since b2e5340b

`659 files changed, 248733 insertions(+), 13065 deletions(-)` (major expansion: widget unification, clipboard, compatibility warnings, new docs/architecture/ADRs).

Changed modules: **all** (every module touched).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).
