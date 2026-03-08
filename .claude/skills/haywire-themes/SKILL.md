---
name: haywire-themes
description: Load Haywire theme system docs into context. Use when the user wants to create a WorkbenchTheme or NodeTheme, register themes from a library, modify CSS tokens, or work with ThemeRegistry.
---

# Load Haywire Theme Docs

Read the following documentation files in order and use them as the authoritative reference for any theme task. After reading, output a brief recap of key patterns before proceeding.

## Files to read

1. `docs/documentation/themes.md/01-overview.md` — architecture: two theme types (WorkbenchTheme / NodeTheme), full CSS token map (`--hw-*` variables), ThemeRegistry API, CSS application via `apply_workbench_theme()`, TOML data files
2. `docs/documentation/themes.md/02-workbench-themes.md` — creating WorkbenchTheme subclasses: `@workbench_theme(id=..., label=...)` decorator, plain string class attributes, partial override via subclassing, `to_css_vars()`, registration
3. `docs/documentation/themes.md/03-node-themes.md` — creating NodeTheme subclasses: `@node_theme(id=..., label=...)` decorator, available token names, `get_color(token)`, partial override
4. `docs/documentation/themes.md/04-library-themes.md` — shipping themes from a haybale library: file layout, `register_components()` wiring, hot-reload, testing

## After reading

Summarise in 6–8 bullet points:
- Two independent theme types: `WorkbenchTheme` (app-shell CSS vars) and `NodeTheme` (node renderer tokens) — a user can mix any combination
- Fields are **plain string class attributes** (not `setting()` descriptors); `__init_subclass__` wraps them into `_FieldProxy` objects in `cls._fields`
- `@workbench_theme(id=..., label=...)` / `@node_theme(id=..., label=...)` set `class_identity` — required for `ThemeRegistry` registration
- `WorkbenchTheme.to_css_vars()` returns `{--hw-token: value}` for all tokens in `_CSS_TOKEN_MAP`; missing fields are silently skipped
- `NodeTheme.get_color(token)` returns the colour string or `''` for unknown tokens — safe to call unconditionally
- Active theme is session-scoped (`context.active_workbench_theme_id`), initialised from `workbench.theme` global setting on page load
- Theme ids must be globally unique — prefix with library name (e.g. `mylib-dark`) to avoid clashes with built-ins (`haywire-dark`, `haywire-light`, `default`)
- Partial theme: subclass an existing theme and override only the fields you need — all other tokens inherit from the parent class

Then proceed with the user's task using these patterns as the guide.
