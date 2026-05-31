# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-05-31 |
| Commit | 4e5c1da7522a14c917d5743305a36e0af1486e8a |
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
| haywire-core (whole pkg) | `packages/haywire-core` | c56f69bcdeda2aa726bdfc4580c22f80d4d9dfe4 | 2026-05-31 |
| haywire-studio | `packages/haywire-studio` | 07bbcb50e32549d38da4c35bde2be49484cd8fc7 | 2026-05-31 |
| haybale-core | `barn/haybale-core` | 565c78a5600104fb5ac0624e2c87bb85c232878b | 2026-05-31 |
| haybale-studio | `barn/haybale-studio` | 87f375f7c060a3115d30a59a0db070cc7f8ae3bb | 2026-05-31 |
| haybale-graph-editor | `barn/haybale-graph-editor` | 49ead920cde1cd306348edc762e472529f36cc70 | 2026-05-31 |
| haybale-haystack | `barn/haybale-haystack` | 7e81488ee91f1a3c54ff7fc15049ff9fe7be1fae | 2026-05-31 |
| haybale-marketplace | `barn/haybale-marketplace` | 0f34300b1cdf312246d8b37385899620552c1912 | 2026-05-31 |
| haybale-example | `barn/haybale-example` | ff804015005f21bd288c6e13802e17bc573637e6 | 2026-05-31 |
| haybale-testing | `barn/haybale-testing` | e0cf3eeb0ffd7d192b8c5e5ec653a039400868c7 | 2026-05-31 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 444fc891ea2e80e60b860657795622ac6e0d1334 | 2026-05-31 |
| tests | `tests` | fb5365bf9b1ff23d177af4855d4d264132c83c65 | 2026-05-31 |
| docs | `docs` | 1b72a3e4ced64c34af43bab1ba30832072d9d78d | 2026-05-31 |

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

Last check (2026-05-31): clean working tree.

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). Reflected `core/marketstall` + `core/host` engine subsystems and the move of `library_manager.py` out of haywire-studio. |

### Diff since b2e5340b

`370 files changed, 52389 insertions(+), 8367 deletions(-)` (commits since old: haywire-core 64, tests 50, haybale-studio 44, haywire-studio 43, graph-editor 26, docs 26, marketplace 25, haystack 22).

Changed modules: **all** (every module tree hash moved).
New module: `haybale-marketplace`.
Removed from tracking: `haybale-visiongraph` (gitignored).
