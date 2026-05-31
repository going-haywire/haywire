# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-05-31 (2nd refresh) |
| Commit | a08a693148be827b608ee86cab865f6cc9d0983b |
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
| haywire-core (whole pkg) | `packages/haywire-core` | 93e6c623fc9092d45300cc7f3d9173ad63693441 | 2026-05-31 |
| haywire-studio | `packages/haywire-studio` | 087438af63732dd1bd342783491c55fa978d07ea | 2026-05-31 |
| haybale-core | `barn/haybale-core` | 9a75ac86ea0138cde74883f7b3e706ef7d926d5e | 2026-05-31 |
| haybale-studio | `barn/haybale-studio` | ed61ffe797fe53ab3b8c5aa30b73c6fa4121870c | 2026-05-31 |
| haybale-graph-editor | `barn/haybale-graph-editor` | 49b500c3f465d76712dc745b2ca24986897b97a5 | 2026-05-31 |
| haybale-haystack | `barn/haybale-haystack` | 73d73f00b120b5140f992547f83004cd5e047c28 | 2026-05-31 |
| haybale-marketplace | `barn/haybale-marketplace` | 7343cfdffeb8007c634928ebd07bdad322b70188 | 2026-05-31 |
| haybale-example | `barn/haybale-example` | 8b79e5fb383e84e9a998314927b97f10860e2bf7 | 2026-05-31 |
| haybale-testing | `barn/haybale-testing` | 96a5e9e459cc3192a037b873bd6e258a399c6923 | 2026-05-31 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 7794d44c22fe03427f75d3620db65193fb156ba6 | 2026-05-31 |
| tests | `tests` | aca64c64228dd8a4ac1348515225f0ca9915f4ce | 2026-05-31 |
| docs | `docs` | 26b10d7a19ba6492c43f6cbe2ba1e5bbf407f878 | 2026-05-31 |

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

Last check (2026-05-31, 2nd refresh): clean working tree.

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). Reflected `core/marketstall` + `core/host` engine subsystems and the move of `library_manager.py` out of haywire-studio. |
| 2026-05-31 | a08a6931 | 2nd refresh — content updates to `haywire-core-engine` (new `graph/scheduler.py`, ADR 0002), `haybale-studio` (new `loop_scheduler.py`), `docs` (docs/components/{libraries,haybale-package} → docs/haybale/; library-manager → marketplace), `tests` (scheduler + dirty-sync + editor-base tests). Hash-only refresh on 7 modules; no module added/removed. |

### Diff since b2e5340b

`370 files changed, 52389 insertions(+), 8367 deletions(-)` (commits since old: haywire-core 64, tests 50, haybale-studio 44, haywire-studio 43, graph-editor 26, docs 26, marketplace 25, haystack 22).

Changed modules: **all** (every module tree hash moved).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).
