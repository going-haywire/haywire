---
name: project_haybale_studio_haywire_studio_layering
description: Handoff — investigate whether haybale-studio (barn library) should depend on haywire_studio (app package) for NetworkSettingsPanel
metadata:
type: project
status: open
---

# Handoff: haybale-studio → haywire_studio dependency

## Where this came from

Dependency audit (DEP003) flagged `haybale-studio: haywire_studio missing`. Confirmed real:
[`NetworkSettingsPanel.draw`](../../barn/haybale-studio/haybale_studio/panels/properties/setting/app.py#L98-L108)
does a local (in-method) import of `FarmhandSettings` and `NetworkSettings` from the `haywire_studio`
app package (`packages/haywire-studio/src/haywire_studio/{farmhand,network}/settings.py`), unconditional,
not guarded by try/except.

This is the **only** place in `haybale-studio` that reaches into `haywire_studio`
(`grep -rln "^from haywire_studio\|^import haywire_studio" barn/haybale-studio/` returns nothing else).
Everything else in that file (`ThemeSettingsPanel`, `NodeSkinDefaultPanel`, `EditorSettingsPanel`) renders
settings owned by `haywire-core` or `haybale-studio` itself — `EditorSettings` in particular lives at
`haywire.ui.prefs.editor` (framework-owned), which is the pattern the other three panels follow.

The `haybale_haystack` half of the same DEP003 finding was resolved separately by deleting the
open-graph-count feature from `StudioStatusTool` — marketplace library has its own farmhand for that,
so haystack was dropped from `status.py` entirely.

## The question

Barn libraries (`haybale-*`) are meant to be library plugins on top of the `haywire-core` framework —
none of them currently depend on `haywire-studio` (the app package). This one method is a layering
exception: a library reaching "up" into the app.

Two ways to resolve it, neither obviously right:

1. **Declare the dependency.** Add `haywire-studio` to `haybale-studio/pyproject.toml` `dependencies`.
   Simple, but makes `haybale-studio` require the *app*, not just the framework — a barn library that
   can no longer be used against a bare `haywire-core` embed. Check whether anything currently assumes
   `haybale-studio` is embeddable without the full studio app (tests, docs, other consumers).

2. **Move `FarmhandSettings`/`NetworkSettings` down into `haywire-core`** (or somewhere `haybale-studio`
   already legitimately depends on), so the panel renders framework-owned settings like its three
   siblings do. Also not obviously right — Farmhand/network config feel like studio-app concerns
   (MCP server enable/auth, studio port/loopback), not generic framework settings every embedder needs.

## What to investigate

- Why does `NetworkSettingsPanel` exist in `haybale-studio` rather than `haywire-studio` in the first
  place — was this an oversight, or is there a reason app-scope settings panels are meant to live in
  the barn library layer?
- Are there other `AppFocus` panels (in this file or elsewhere) that *should* be rendering
  `haywire_studio`-owned settings but currently don't, i.e. is this one panel an outlier bug or the
  first instance of a pattern that needs a real seam?
- If moving settings down: what's the blast radius of `FarmhandSettings`/`NetworkSettings` — anything
  in `haywire_studio` itself importing them that would need to follow, or CLI/MCP code assuming their
  current module path?
- Whichever direction: check `barn/haybale-studio/pyproject.toml` dependency list and hot-reload/library
  dependency tracking (`@library(dependencies=[...])` uses Python package names — see
  [project_library_dependencies_use_package_names.md](../../.insights/project_library_dependencies_use_package_names.md))
  for whatever the fix implies.

Do not implement either option without confirming direction with the user first — this affects the
barn library / app package dependency boundary, which is an architectural decision per CLAUDE.md
(ask for confirmation before implementing anything touching class hierarchies or DI/dependency wiring).
