---
name: haywire-themes
description: Load Haywire theme system docs into context. Use when the user wants to create a WorkbenchTheme or NodeTheme, register themes from a library, modify CSS tokens, or work with ThemeRegistry.
---

# Load Haywire Theme Docs

Read the following documentation files in order and use them as the authoritative reference for any theme task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/components/themes/theme-canon.md` — authoring guide: `WorkbenchTheme` (workbench CSS vars) and `NodeTheme` (node renderer tokens), the single `@theme(label=...)` decorator (NOT separate `@workbench_theme` / `@node_theme`), full token reference, `to_css_vars()`, `get_color()`, partial override via subclassing, library registration via `ThemeRegistry`, hot-reload, complete worked example with bundled themes

## After reading

Summarise in 6–8 bullet points:
- Two independent theme types: `WorkbenchTheme` (app-shell CSS vars on `:root`) and `NodeTheme` (node-canvas-side renderer tokens) — a user can mix any combination
- Fields are **plain string class attributes** (not `setting()` descriptors); `__init_subclass__` wraps them into `_FieldProxy` objects in `cls._fields`
- `@theme(label='...')` is the single decorator for both types (sets `class_identity` for `ThemeRegistry` discovery — required)
- `WorkbenchTheme.to_css_vars()` returns `{--hw-token: value}` for all tokens in `_CSS_TOKEN_MAP`; fields not in the map are silently dropped
- `NodeTheme.get_color(token)` returns the colour string or `''` for unknown tokens — safe to call unconditionally
- Active theme is selected via the `workbench.theme` and `node.theme` settings (TOML keys); the studio's `AppShell.apply_workbench_theme()` re-injects CSS vars on switch (live, no reload)
- Imports: `from haywire.ui.themes.workbench import WorkbenchTheme`, `from haywire.ui.themes.node_theme import NodeTheme`, `from haywire.ui.themes.decorator import theme`, `from haywire.ui.themes.registry import ThemeRegistry` (NOT `theme_registry` — that path is out of date in older docs)
- Theme `registry_id`s must be globally unique — prefix with library name (e.g. `mylib-dark`); registration via `theme_registry.register_workbench(Cls)` / `register_node_theme(Cls)` in `Library.register_components()`

Then proceed with the user's task using these patterns as the guide.
