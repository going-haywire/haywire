# Map Metadata

| Field | Value |
|-------|-------|
| Generated at | 2026-05-16 10:25 UTC |
| Last refreshed at | 2026-11-10 (8th refresh) |
| Commit | 9b104fd36 (`git rev-parse HEAD`, full hash `9b104fd36b0b6cc67cccb755b245f23475517a4f`) |
| Branch | feat/exec-audio (earlier refreshes were on master) |
| Generator | codebase-cartographer |
| Modules mapped | 15 |
| Cross-cuts mapped | 3 (refreshed 2026-11-10, paths verified at 9b104fd36) |
| Git tracked | Yes |

## Module Tree Hashes

This table enables incremental refresh. Each hash is the output of `git rev-parse HEAD:{module-path}` at generation or refresh time. If a module's current tree hash differs from the value below, its manifest is stale and should be regenerated.

| Module | Path | Tree hash | Last updated |
|--------|------|-----------|--------------|
| haywire-core-engine | `packages/haywire-core/src/haywire/core` | 50bc578ca0b79a8ea76b7bfd84bcf7e950c463a1 | 2026-11-10 |
| haywire-core-ui | `packages/haywire-core/src/haywire/ui` | 2908b8b7a84b83893cbfb034dbb997722a88ee0f | 2026-11-10 |
| haywire-core (whole pkg) | `packages/haywire-core` | 8ff0e57aa42151afb5f8edbb718ee235683a5e29 | 2026-11-10 |
| haywire-studio | `packages/haywire-studio` | 81feaf694f950d4b3dfd276b19deb1bec3303f26 | 2026-11-10 |
| haybale-core | `barn/haybale-core` | adf6753cb31f46fd6e3aeaab8741529bff65fc68 | 2026-11-10 |
| haybale-studio | `barn/haybale-studio` | 643acc424dff795f8d4b21a132f1d869c8a54a30 | 2026-11-10 |
| haybale-graph-editor | `barn/haybale-graph-editor` | dae828f6da44fd3c28b493432e5ce193fafc70f6 | 2026-11-10 |
| haybale-haystack | `barn/haybale-haystack` | 9822bf3beebf6f86833e457b46afac6d293b8989 | 2026-11-10 |
| haybale-marketplace | `barn/haybale-marketplace` | e4c453c9170503694a7161719b25c7cac519d304 | 2026-11-10 |
| haybale-audio | `barn/haybale-audio` | 58d1e97e1f959095d744a7671e7014244f75b62b | 2026-11-10 (new) |
| haybale-image | `barn/haybale-image` | ccfaa1943ac6c3c9b11403cf193f2c51948a6075 | 2026-11-10 (new) |
| haybale-models | `barn/haybale-models` | 1d0650db8cc3858b04766e0159878973bd4176dd | 2026-11-10 (new) |
| haybale-share | `barn/haybale-share` | c09cf21410b7fbe60c4c4a4380f9259bc5e95a7f | 2026-11-10 (new) |
| haybale-example | `barn/haybale-example` | aac17609a94449af6ac9befb55a8fa33cc41ced0 | 2026-11-10 |
| haybale-testing | `barn/haybale-testing` | e9c4c353edbb3ebfed55aa128a0155a99207469e | 2026-11-10 |
| haybale-TEST_A | `barn/haybale-TEST_A` | 07a979e8ef318a2da1210d2f1693d26b0a5a4f57 | 2026-11-10 |
| tests | `tests` | db337c6bfd89c189b239a5975f3ce71fd48a55ed | 2026-11-10 |
| docs | `docs` | 622d2aeda8c1c2465c997d564918eef2edbc7d83 | 2026-11-10 |

> `barn/haybale-visiongraph`, `barn/haybale-comfyui`, `barn/haybale-spandrel` and `barn/haybale-stream` are **gitignored** (`.gitignore:224-227`) and untracked in HEAD. They exist on disk as local-only libraries and are not hash-tracked or mapped.

> `haybale-audio`, `haybale-image`, `haybale-models` and `haybale-share` have no manifests before this refresh. Their tree hashes were computed here, not from an earlier map.

## Refresh Instructions

To refresh this map:

1. Run the codebase-cartographer skill. It detects this META.md and performs an incremental update.
2. Or manually:
   a. Run `git rev-parse HEAD:{module-path}` for each module above.
   b. Compare against the stored tree hash.
   c. Rewrite only the manifests whose hashes changed.
   d. Update this table and the Change Log below.

## Uncommitted Changes

Last check (2026-11-10, 8th refresh): 3 entries in `git status --porcelain`, none under a mapped module path:

- ` M graphs/audio.haywire`
- ` M haystacks/Single.toml`
- `?? graphs/comfyui.haywire`

The map reflects the last committed state (HEAD `9b104fd36`).

## Change Log

| Date | Commit | Summary |
|------|--------|---------|
| 2026-05-16 | b2e5340b | Initial generation — 9 modules + 3 cross-cuts mapped |
| 2026-05-31 | 4e5c1da7 | Full refresh — all modules changed. Added `haybale-marketplace`. Dropped `haybale-visiongraph` (now gitignored). |
| 2026-05-31 | a08a6931 | 2nd refresh — content updates to `haywire-core-engine`, `haybale-studio`, `docs`, `tests`. Hash-only refresh on 7 modules. |
| 2026-06-10 | b5068ae7 | 3rd refresh — full refresh across all modules (ADRs 0003–0008, widget unification, clipboard, marketplace UX). |
| 2026-06-13 | 8cc9ff00 | 4th refresh — all 12 modules updated (graph-editor refactor, rename CLI, marketplace refactor, panel rendering). |
| 2026-06-17 | 51d1ac64 | 5th refresh — all 11 modules refreshed. No modules added or removed. |
| 2026-06-25 | 45140b27 | 6th refresh — all 11 modules refreshed. Reroute node and reroute skin added to haybale-core. |
| 2026-07-05 | b07aca75 | 7th refresh — all 14 tracked paths refreshed. Settings↔DataField unification (ADRs 0011–0017). ADRs 0015/0016 folded into 0014/0013 as amendments. |
| 2026-11-10 | 9b104fd36 | 8th refresh (branch feat/exec-audio) — all 14 prior paths changed. 4 new manifests (haybale-audio, haybale-image, haybale-models, haybale-share). Manifests rewritten from current trees: stale references removed (e.g. `library/loader.py`, `marketstall/marketstall.py`, `focuses.py`, `haybale-studio` loop scheduler, graph-editor `panels/graph/menu/node/`). haybale-core: reroute node/skin gone; primitives in `haywire.barn.builtin`. haybale-libs-other: current example/testing/TEST_A layout. 2378 files changed since b07aca75. Cross-cuts refreshed in a follow-up pass (PortType replaces FlowType; signal, library and EXEC references verified). |

### Diff since b07aca75 (7th refresh)

`2378 files changed, 264306 insertions(+), 27609 deletions(-)` over the tracked module paths.

Largest churn: `packages/haywire-core` (501 files), `tests/core` (339), `tests/ui` (262), `barn/haybale-graph-editor` (203), `barn/haybale-testing` (139), `barn/haybale-studio` (100), `barn/haybale-core` (81), `docs/adr` (71), `packages/haywire-studio` (66), `barn/haybale-models` (61), `barn/haybale-image` (60), `barn/haybale-marketplace` (59).

Changed modules: **all 14 tracked paths**. New modules: **haybale-audio, haybale-image, haybale-models, haybale-share**.
