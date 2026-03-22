# Codemap Metadata

## Generation Info

| Field | Value |
|-------|-------|
| Generated | 2026-03-22 |
| Commit | `34e617a0143c372a1b8c443b04894e7b281943ef` |
| Branch | `code_refactoring` |
| Generator | codebase-cartographer skill (Claude Code) |

---

## Module Hash Table

Used for incremental refresh — compare against current tree hashes to detect stale manifests.

| Module | Manifest | Path | Tree Hash |
|--------|---------|------|-----------|
| haywire-core/engine | `modules/core-engine.md` | `packages/haywire-core/src/haywire/core` | `3ae5e9cf3d5a14149ce06f3d3a457f11ba6329fa` |
| haywire-core/ui | `modules/core-ui.md` | `packages/haywire-core/src/haywire/ui` | `36b7220e8f7ab5ac60c04b606acfc1987f66ce1f` |
| haywire-studio | `modules/haywire-studio.md` | `packages/haywire-studio/src/haywire_studio` | `b14f4b5a69b578141150b07684bf54932940fdd5` |
| haybale-studio | `modules/haybale-studio.md` | `barn/haybale-studio` | `8c3ed955ef666097e66f725d663f1789ae0704f7` |
| haybale-core | `modules/haybale-core.md` | `barn/haybale-core` | `6e787ffcbb8d45d76ee17b89caa3f8d734e8b9d0` |
| barn/other | `modules/barn-other.md` | `barn` | `3bd39f2df7750500c2f04899fba7277b581b2b41` |
| tests | `modules/tests.md` | `tests` | `6e086fd81ec0a04cfccffc15ca4a02ea997e0e21` |

---

## How to Refresh

Run `/codebase-cartographer` in Claude Code. The skill detects this META.md, compares
tree hashes against HEAD, and regenerates only stale module manifests.

To force full regeneration, delete this file before running the skill.

---

## Change Log

| Date | Changes |
|------|---------|
| 2026-03-22 | Initial generation — 7 modules, 2 cross-cuts. Commit `34e617a`. |
