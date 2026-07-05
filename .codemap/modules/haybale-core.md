# Module: haybale-core

> The default haybale plugin library: concrete node types, port/value adapters, panels, themes, and skins shipped with every Haywire install.

**Path:** `barn/haybale-core/haybale_core/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `3900ec57b9c6fa1cbb1ba40297e0d415aacacb97`
**Mapped at:** 19bda1e (2026-07-05)

---

## 1. Scope & Purpose

`haybale-core` is the canonical reference for how a haybale library is structured. It registers nodes/adapters/types/widgets/themes/skins/panels/settings via `BaseLibrary.register_components()` and is discovered through the `haywire.libraries` entry point. Other haybale-* libraries should pattern-match this layout. If `haybale-core` were removed, the studio would boot but no useful node would exist.

**Recent shift:** the basic value types (INT/FLOAT/STRING/BOOL), their widgets (Number/Text/Checkbox/Switch/Slider/Select/SimpleLabel), and their conversion adapters have been **hoisted out of this package into the framework's `builtin` library** (`packages/haywire-core/src/haywire/barn/builtin/`). `haybale-core` now imports these from `haywire.barn.builtin.{types,widgets}` instead of owning them; it retains only compound/pooled/array types, the compound adapter, and plugin-specific node/skin content. `haybale_core/widgets/` and `haybale_core/adapters/basic_adapters.py` are now empty shells kept only in case a plugin-specific widget/adapter is added later.

## 2. Folder Architecture

```
haybale_core/
├── __init__.py                 ← exposes `Library` (BaseLibrary subclass)
├── adapters/
│   ├── __init__.py             ← exports only ArrayArrayAdapter (basic_adapters.py removed)
│   └── compound_adapters.py
├── nodes/
│   ├── error_node.py           ← placeholder for a node that failed to load
│   ├── for_loop.py             ← imports INT/NumberWidget from haywire.barn.builtin
│   ├── print_terminal.py       ← imports STRING/TextWidget from haywire.barn.builtin
│   ├── print_ui_log.py
│   ├── switch.py                ← imports INT/FLOAT/STRING/SelectWidget/NumberWidget from haywire.barn.builtin
│   ├── reroute.py               ← reroute/noop node for graph flow
│   └── events/*, emits/*        ← import FLOAT from haywire.barn.builtin where needed
├── panels/                     ← `__init__.py` only; no panel content yet
├── skins/
│   ├── default_skin.py
│   └── reroute_skin.py          ← visual style for reroute nodes
├── themes/                     ← `__init__.py` only; no theme content yet
├── types/
│   ├── array_type.py            ← ArrayField; on_changed.fire now passes (new, old)
│   ├── pooled_type.py           ← PooledField; on_changed.fire now passes (new, old)
│   └── specs.py                 ← GROUP/BYTES/LIST/DICT/EXEC/CALLBACK only (INT/FLOAT/STRING/BOOL moved to builtin)
└── widgets/
    └── __init__.py              ← docstring only; basic_widgets.py removed, hoisted to haywire.barn.builtin.widgets
```

⚠️ TODO: `panels/` and `themes/` are currently empty stubs (`__init__.py` only) despite being registered folders in `Library.register_components()` — confirm whether content is planned or these registrations are vestigial.

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — defines the `Library` class and its `register_components()`.
- `nodes/` (one or two representative files, e.g. `print_terminal.py`) — node authoring template; shows the current import convention (`haywire.barn.builtin.types`/`.widgets` for primitives, local `types.specs` for GROUP/EXEC/etc).

### On-demand

- **`haywire.barn.builtin`** (in `haywire-core-engine`, not this package) — canonical home for INT/FLOAT/STRING/BOOL, basic widgets, and basic type-conversion adapters; read this before touching any node that uses a primitive value type.
- `types/specs.py` — remaining local primitive-ish types (GROUP, BYTES, LIST, DICT, EXEC, CALLBACK); `CALLBACK` subclasses `builtin.types.STRING` but is intentionally widget-less (see in-file comment on `StoreStrategy.should_store`).
- `types/array_type.py`, `types/pooled_type.py` — compound field types; `on_changed.fire()` now takes `(new_value, old_value)` per [ADR 0013](../../docs/adr/0013-settings-single-cell.md)'s cell-authoritative amendment — check callers if adding new fire sites.
- `adapters/compound_adapters.py` — the only adapter left in this package (`ArrayArrayAdapter`); basic scalar adapters live in `haywire.barn.builtin.adapters` now.
- `nodes/reroute.py` / `skins/reroute_skin.py` — reroute node for graph organization and its visual skin.
- `nodes/for_loop.py`, `nodes/switch.py` — representative nodes that mix local EXEC/GROUP types with builtin primitive types; good template for the split-import pattern.
- `themes/`, `skins/` — when modifying visual presentation; coordinate with `docs/reference/design-guide.md`.
- `panels/` — currently empty; when adding inspector content, check whether it should live here or in `haywire.barn.builtin` given the ongoing hoisting trend.

## 4. Rules & Boundaries

- Must register all components in `Library.register_components()`. Side-effect imports for registration are forbidden — see [library plugin system cross-cut](../cross-cuts/library-plugin-system.md).
- Primitive value types/widgets/adapters (INT/FLOAT/STRING/BOOL and their widgets) belong in `haywire.barn.builtin`, not here — do not reintroduce them locally; import from the builtin package instead.
- `DataField.fire()` call sites must pass both new and old values (`fire(new, old)`) — a one-arg call is stale pre-convergence style.
- Class/function renames inside this package need a `check-rename` sweep — string-based references (`patch("haybale_core.X")`, doc citations) won't be caught by IDE rename.
- Top-of-file imports of barn classes go stale after `importlib.reload`. In tests, use `importlib.import_module` + `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Themes/widgets/skins must follow `docs/reference/design-guide.md` (no hardcoded colors, etc.).

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_core/__init__.py` | `Library = BaseLibrary` subclass |
| Entry-point declaration | `barn/haybale-core/pyproject.toml` | `[project.entry-points."haywire.libraries"]`; pinned to `haywire-core~=0.0.25` |
| Node template | `nodes/print_terminal.py`, `nodes/for_loop.py` | Pattern for downstream libraries incl. builtin-type imports |
| Primitive types/widgets/adapters | `haywire.barn.builtin` (`haywire-core-engine` module) | Not owned by this package anymore |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `BaseLibrary`, node base, registries, and now `haywire.barn.builtin` (types/widgets/adapters for primitives).
- [haywire-core-ui](haywire-core-ui.md) — Panel/Editor/Skin/Theme bases.

### Depended on by

- [haywire-studio](haywire-studio.md) — listed as runtime dependency.
- [haybale-studio](haybale-studio.md), [haybale-haystack](haybale-haystack.md), [haybale-marketplace](haybale-marketplace.md), [haybale-libs-other](haybale-libs-other.md) — use shared types/widgets (increasingly via `haywire.barn.builtin` rather than this package directly).
- [tests](tests.md) — `tests/test_libraries`, `tests/libraries/`.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
