# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-06-13 (4th refresh) |
| Commit | 8cc9ff0050817291327f8b048b75a2ececd93d9d |
| Branch | master |
| Generator | codebase-cartographer |
| Modules mapped | 11 |
| Cross-cuts mapped | 3 |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation/refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | (part of haywire-core) | 2026-05-31 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | (part of haywire-core) | 2026-05-31 |
| haywire-core (whole pkg) | `packages/haywire-core` | b5c34c5e844d66ff65094794f7a0788d65037601 | 2026-06-13 |
| haywire-studio | `packages/haywire-studio` | 20bbe022dc12c9c81034118099e2eb94e277e00c | 2026-06-13 |
| haybale-core | `barn/haybale-core` | f162721166d4a0e58ba36ee7d928977b6656e054 | 2026-06-13 |
| haybale-studio | `barn/haybale-studio` | d727087122d07c3d6667f2ea71e3578c22d5578e | 2026-06-13 |
| haybale-graph-editor | `barn/haybale-graph-editor` | b55488bdffaf1f3d04ad79b47ac916f18627e1e0 | 2026-06-13 |
| haybale-haystack | `barn/haybale-haystack` | 5055151cc310d0139ee9202f14f9a6e36eee5ea4 | 2026-06-13 |
| haybale-marketplace | `barn/haybale-marketplace` | c900f290ca958fa19a13fc066897fd83d9e4d9a1 | 2026-06-13 |
| haybale-example | `barn/haybale-example` | 05e467083afbdd17c2c384c12f1e349576e2c5a3 | 2026-06-13 |
| haybale-testing | `barn/haybale-testing` | b0361d3ec32a2dc8af4f00ded1451e2464f1f801 | 2026-06-13 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 888346ad871164af7ae20baac6ec9b38d4fbb564 | 2026-06-13 |
| tests | `tests` | 2c93c41eb5f8100ad6d98ebeac37be857b153623 | 2026-06-13 |
| docs | `docs` | 226e9f95b1f2f661e98c1f101218bdcaa026d9ba | 2026-06-13 |

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

Last check (2026-06-10, 3rd refresh): clean working tree.

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). Reflected `core/marketstall` + `core/host` engine subsystems and the move of `library_manager.py` out of haywire-studio. |
| 2026-05-31 | a08a6931 | 2nd refresh — content updates to `haywire-core-engine` (new `graph/scheduler.py`, ADR 0002), `haybale-studio` (new `loop_scheduler.py`), `docs` (docs/components/{libraries,haybale-package} → docs/haybale/; library-manager → marketplace), `tests` (scheduler + dirty-sync + editor-base tests). Hash-only refresh on 7 modules; no module added/removed. |
| 2026-06-10 | b5068ae7 | 3rd refresh — full refresh across all modules. Major: ADRs 0003–0008, widget unification + BaseWidget, clipboard (copy/paste), node warnings/compatibility, ShowWidget strategy, Ports panel rendering, graph canvas selection rewrite, marketplace editor UX. Tests: 15+ new test files (widget, clipboard, compatibility, show-widget, scheduler-wait, etc.). UI: debug overlay, canvas/pan/zoom updates, nicegui-patches. Docs: 6 new ADRs, widget-canon rewrite, design-guide updates. |
| 2026-06-13 | 8cc9ff00 | 4th refresh — all 12 modules updated. Major: graph-editor refactored with `graph_save_as.py` extraction, haywire-studio new `rename.py` CLI, marketplace major refactor with 4 new editor submodules (`_overview_actions`, `_overview_edit_dialog`, `_overview_install_flow`, `_registry_utils`), panel rendering refactored (new `host_rendering.py`, `redraw_coordinator.py`), haybale-studio code/properties editor refactored, core new `storage.py`. Tests: 10+ new files (rename, library manager, workspace storage, panel rendering, etc.). Docs: ADR 0009, new `state-canon.md`, panel-canon updates. |

### Diff since b2e5340b

`659 files changed, 248733 insertions(+), 13065 deletions(-)` (major expansion: widget unification, clipboard, compatibility warnings, new docs/architecture/ADRs).

Changed modules: **all** (every module touched).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).
