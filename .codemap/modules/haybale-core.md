# Module: haybale-core

> The default haybale plugin library: concrete node types, port/value adapters, NiceGUI widgets, panels, themes, and skins shipped with every Haywire install.

**Path:** `barn/haybale-core/haybale_core/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `17d68a970a077ff8d587c46046adf97a98be1241`
**Mapped at:** 45140b27 (2026-06-25)

---

## 1. Scope & Purpose

`haybale-core` is the canonical reference for how a haybale library is structured. It registers nodes/adapters/types/widgets/themes/skins/panels/settings via `BaseLibrary.register_components()` and is discovered through the `haywire.libraries` entry point. Other haybale-* libraries should pattern-match this layout. If `haybale-core` were removed, the studio would boot but no useful node would exist.

## 2. Folder Architecture

```
haybale_core/
├── __init__.py               ← exposes `Library` (BaseLibrary subclass)
├── adapters/compound_adapters.py ← updated for widget unification
├── nodes/
│   ├── for_loop.py (updated) ← loop iteration syntax changes
│   ├── print_terminal.py     ← print to terminal UI (rewritten)
│   ├── print_ui_log.py
│   ├── switch.py
│   ├── reroute.py (new)      ← reroute/noop node for graph flow
│   └── events/*, emits/*
├── panels/
├── settings/
├── skins/
│   ├── default_skin.py
│   └── reroute_skin.py (new) ← visual style for reroute nodes
├── themes/
├── types/pooled_type.py, specs.py
└── widgets/basic_widgets.py (major rewrite) ← BaseWidget unification
```

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — defines the `Library` class and its `register_components()`.
- `nodes/` (one or two representative files) — node authoring template.

### On-demand

- **`widgets/basic_widgets.py`** (major rewrite) — uses new BaseWidget unification (ADR 0007); pattern for downstream libraries.
- `adapters/` — when extending type/port adapter rules (updated for widget unification).
- `types/` — when extending the type system beyond primitives.
- `nodes/reroute.py` (new) — reroute node for graph organization; added in recent refresh.
- `nodes/for_loop.py` — loop iteration syntax; check before using in tests.
- `nodes/print_terminal.py` (rewritten) — print-to-UI output; reuses BaseWidget.
- `skins/reroute_skin.py` (new) — visual rendering for reroute nodes.
- `themes/`, `skins/` — when modifying visual presentation; coordinate with `docs/reference/design-guide.md`.
- `panels/`, `settings/` — when adding inspector content or library/node settings UI.

## 4. Rules & Boundaries

- Must register all components in `Library.register_components()`. Side-effect imports for registration are forbidden — see [library plugin system cross-cut](../cross-cuts/library-plugin-system.md).
- Class/function renames inside this package need a `check-rename` sweep — string-based references (`patch("haybale_core.X")`, doc citations) won't be caught by IDE rename.
- Top-of-file imports of barn classes go stale after `importlib.reload`. In tests, use `importlib.import_module` + `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Themes/widgets/skins must follow `docs/reference/design-guide.md` (no hardcoded colors, etc.).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_core/__init__.py` | `Library = BaseLibrary` subclass |
| Entry-point declaration | `barn/haybale-core/pyproject.toml` | `[project.entry-points."haywire.libraries"]` |
| Node template | `nodes/` (any representative file) | Pattern for downstream libraries |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `BaseLibrary`, node base, registries.
- [haywire-core-ui](haywire-core-ui.md) — Panel/Editor/Skin/Theme bases.

### Depended on by

- [haywire-studio](haywire-studio.md) — listed as runtime dependency.
- [haybale-studio](haybale-studio.md), [haybale-haystack](haybale-haystack.md), other libs — use shared types/widgets.
- [tests](tests.md) — `tests/test_libraries`, `tests/libraries/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
