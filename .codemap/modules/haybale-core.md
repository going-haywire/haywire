# Module: haybale-core

> The default haybale plugin library: concrete node types (flow control, file/path utilities, widget nodes, emitters), compound/array types and adapters, and the widget-node skin shipped with every Haywire install.

**Path:** `barn/haybale-core/haybale_core/`
**Language:** Python 3.10+
**Owner:** Haywire core team (bundled plugin)
**Tree hash:** `adf6753cb31f46fd6e3aeaab8741529bff65fc68`
**Mapped at:** 9b104fd36 (2026-11-10, branch feat/exec-audio)

---

## 1. Scope & Purpose

`haybale-core` is the canonical reference for how a haybale library is structured. It registers nodes, adapters, types, widgets and skins via `BaseLibrary.register_components()` and is discovered through the `haywire.libraries` entry point. Other haybale-* libraries should follow this layout. Removing it leaves the studio booting with no useful nodes.

**Primitive value types have moved out.** INT/FLOAT/STRING/BOOL, their basic widgets, and the scalar adapters live in the framework's `haywire.barn.builtin` package (`packages/haywire-core/src/haywire/barn/builtin/`). This library imports them from there and owns only compound/array/pooled types, the compound adapter, and plugin-specific nodes and skins.

## 2. Folder Architecture

```
haybale_core/
├── __init__.py          ← exposes `Library` (BaseLibrary subclass)
├── adapters/
│   └── compound_adapters.py ← ArrayArrayAdapter (only adapter kept here)
├── types/
│   ├── array_type.py    ← ArrayField (on_changed.fire passes (new, old))
│   ├── pooled_type.py   ← PooledField
│   └── specs.py         ← GROUP/BYTES/LIST/DICT/EXEC/CALLBACK (primitives come from builtin)
├── widgets/
│   └── array_widget.py  ← array widget
├── nodes/
│   ├── events/          ← begin_play, shutdown, tick_event
│   ├── emits/           ← run_button, tick_emit
│   ├── widgets/         ← widget nodes: base, menu, number, slider, text, toggle
│   ├── for_loop.py, for_each_file.py, loop_array.py, step_array.py
│   ├── switch.py        ← flow switch (mixes local EXEC/GROUP with builtin primitives)
│   ├── print.py, logger.py
│   ├── create_folder.py, list_files.py, path_exists.py, resolve_path.py,
│   │   split_path.py, output_path.py
│   └── …
├── skins/
│   └── widget_node_skin.py ← skin for widget nodes
├── array_ports.py       ← array port helpers
├── file_listing.py      ← file listing helpers used by file nodes
├── keys.py              ← shared keys
├── loop_settings.py     ← loop settings
├── haybale.toml         ← library manifest
├── panels/              ← `__init__.py` only (empty)
└── themes/              ← `__init__.py` only (empty)
```

⚠️ TODO: `panels/` and `themes/` are empty `__init__.py` stubs though registered by `Library.register_components()`. Confirm whether content is planned or the registration is vestigial.

## 3. Always-load vs On-demand

### Always-load

- `__init__.py` — `Library` class and `register_components()`.
- `nodes/print.py` or `nodes/for_loop.py` — node authoring template; shows the split-import convention (`haywire.barn.builtin` for primitives, local `types.specs` for GROUP/EXEC).

### On-demand

- `haywire.barn.builtin` (in [haywire-core-engine](haywire-core-engine.md), not this package) — canonical home for INT/FLOAT/STRING/BOOL, their widgets and scalar adapters. Read before touching any node that uses a primitive.
- `types/specs.py` — GROUP, BYTES, LIST, DICT, EXEC, CALLBACK. `CALLBACK` subclasses `builtin` STRING and is intentionally widget-less.
- `types/array_type.py`, `types/pooled_type.py` — compound field types. Check callers when adding `on_changed.fire` sites.
- `nodes/widgets/` — widget nodes; pair with `widgets/array_widget.py` and `skins/widget_node_skin.py`.
- `nodes/events/`, `nodes/emits/` — event and emitter nodes; see the dual-flow cross-cut.
- File and path nodes — when touching `file_listing.py` or path resolution.

## 4. Rules & Boundaries

- Register every component in `Library.register_components()`. Side-effect imports for registration are forbidden. See [library plugin system](../cross-cuts/library-plugin-system.md).
- Primitive types, widgets and adapters (INT/FLOAT/STRING/BOOL) belong in `haywire.barn.builtin`. Do not reintroduce them locally.
- `DataField.fire()` call sites pass both new and old values.
- Renames here need a `check-rename` sweep: string references like `patch("haybale_core.X")` and doc citations are invisible to IDE rename.
- Top-level imports of barn classes go stale after `importlib.reload`. In tests use `importlib.import_module` and `patch.object` (see `.insights/feedback_barn_module_reload_test_trap.md`).
- Themes, widgets and skins follow `docs/reference/design-guide.md`.

## 5. Source of Truth

| Concept | Canonical file | Notes |
|---------|---------------|-------|
| Library entry | `haybale_core/__init__.py` | `Library = BaseLibrary` subclass |
| Entry-point declaration | `barn/haybale-core/pyproject.toml` | `haywire.libraries` entry point |
| Library manifest | `haybale_core/haybale.toml` | Plugin metadata |
| Node template | `nodes/print.py`, `nodes/for_loop.py` | Split-import pattern |
| Primitive types/widgets/adapters | `haywire.barn.builtin` (in haywire-core-engine) | Not owned by this package |

---

## Dependencies

### Depends on

- [haywire-core-engine](haywire-core-engine.md) — `BaseLibrary`, node base, registries, `haywire.barn.builtin`.
- [haywire-core-ui](haywire-core-ui.md) — Panel, Editor, Skin, Theme bases.

### Depended on by

- [haywire-studio](haywire-studio.md) — runtime dependency.
- [haybale-studio](haybale-studio.md), [haybale-haystack](haybale-haystack.md), [haybale-marketplace](haybale-marketplace.md), [haybale-audio](haybale-audio.md), [haybale-image](haybale-image.md), [haybale-models](haybale-models.md), [haybale-share](haybale-share.md), [haybale-libs-other](haybale-libs-other.md) — share types, widgets and nodes.
- [tests](tests.md) — library tests.

---

## Key Entry Points

| Entry point | File | Description |
|-------------|------|-------------|
| Library plugin | `__init__.py:Library` | Discovered via `haywire.libraries` entry point |
| Widget-node skin | `skins/widget_node_skin.py` | Visual style for widget nodes |
