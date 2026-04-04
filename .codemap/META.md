# Codemap Metadata

## Generation Info

| Field | Value |
|-------|-------|
| Generated | 2026-04-04 |
| Commit | `1b3f73e85724c8b4c247518d7f12b1902885a6f6` |
| Branch | `code_refactoring` |
| Generator | codebase-cartographer skill (Claude Code) |

---

## Module Hash Table

Used for incremental refresh — compare against current tree hashes to detect stale manifests.

| Module | Manifest | Path | Tree Hash |
|--------|---------|------|-----------|
| haywire-core/engine | `modules/core-engine.md` | `packages/haywire-core/src/haywire/core` | `ad1aa888fafc4cb2168feb2bbee438f433017cab` |
| haywire-core/ui | `modules/core-ui.md` | `packages/haywire-core/src/haywire/ui` | `92c20fc3668052eec24dc61c146a69846ed018c3` |
| haywire-studio | `modules/haywire-studio.md` | `packages/haywire-studio/src/haywire_studio` | `539c18eb7f53ba69faead0bdbef450d694cada49` |
| haybale-studio | `modules/haybale-studio.md` | `barn/haybale-studio` | `9b75ed48b68a1ae26bf54545cc6c5e2c872d7f10` |
| haybale-core | `modules/haybale-core.md` | `barn/haybale-core` | `a74ca98dbb235747ed99a487d135407dd08d1ce4` |
| barn/other | `modules/barn-other.md` | `barn` | `a60775dd6fa60c7b2eb7ece9789b9651535b178e` |
| tests | `modules/tests.md` | `tests` | `cd3b82945efa6e6737374a429f98a14d0adc80d4` |

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
| 2026-04-04 | Refreshed all 7 modules (all stale — 422 files changed). Key structural changes: `property/` removed; settings three-class model (`descriptor.py`, `settings.py`); `debug/` added; `app_shell.py` → `app/shell.py`; `pan_zoom/` → `components/zoom/` + `components/minimap/`; `graph_canvas/handlers/` extracted; `elements.py` + `panel/render_utils.py` added; haybale-studio gained `themes/`; haybale-core `panels/` expanded with context menu + edge panels; `tests/ui/harness/` + `tests/ui/test_canvas_handlers/` added. Commit `1b3f73e`. |
