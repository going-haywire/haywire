# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | — |
| Commit | b2e5340bb3df15ca29a38dbf452e97c8f7235eeb |
| Branch | master |
| Generator | codebase-cartographer |
| Modules mapped | 9 |
| Cross-cuts mapped | 3 |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation/refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | (see packages hash) | 2026-05-16 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | (see packages hash) | 2026-05-16 |
| haywire-core (whole pkg) | `packages/haywire-core` | 520f7ab7cac4798334fe611c45c3f477d6469fdf | 2026-05-16 |
| haywire-studio | `packages/haywire-studio` | 32290f54f1e21c75972b6712c4e7576c2bbd360f | 2026-05-16 |
| haybale-core | `barn/haybale-core` | ffdb3bd4b9a2cb415b44ba1c6bf80940c1f71b9c | 2026-05-16 |
| haybale-studio | `barn/haybale-studio` | c078cfd5c9f5c182d90f41eb3875c83aab4eea45 | 2026-05-16 |
| haybale-haystack | `barn/haybale-haystack` | 8cf999805307f19446a7a078734ff2f5d153092e | 2026-05-16 |
| haybale-example | `barn/haybale-example` | 3e3e0f04d707fa659e7b5af80fbc50d965571de4 | 2026-05-16 |
| haybale-testing | `barn/haybale-testing` | 5c7b7f51d60a5c4f6eb196ccf52943ddb09f8e0c | 2026-05-16 |
| haybale-visiongraph | `barn/haybale-visiongraph` | 672b016394931e32c08f4ad724a52e969d96484c | 2026-05-16 |
| tests | `tests` | 1da071a192c24726d6469d584ac89a084dd18794 | 2026-05-16 |
| docs | `docs` | 3af7cd1f25ad8f108543b468ccb69602f019bb5c | 2026-05-16 |

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

Last check: ~20 files with deleted/modified status (prior `.codemap/`, `.docmeta/`, refreshing-docs skill files) — not part of current source modules.

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
