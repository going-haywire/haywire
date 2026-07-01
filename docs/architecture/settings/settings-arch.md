---
status: draft
doc_template: impl-spec
scope: Settings framework — three-tier model, SettingsRegistry, four-step resolution chain (set-or-unset tiers), JSON format, FrameworkSettings, test utilities
see-also:
  - ../../components/settings/setting-canon.md
  - ../hot-reload/hot-reload-arch.md
  - ../library-system/library-system-arch.md
  - ../../reference/glossary.md
---

# Settings — Architecture

## 1. Motivation

A node author writes `bg_color = "#fff"` as a default. The user opens the global settings panel and prefers `#000` everywhere. The user's workspace lead pins it to `#f0f0f0` for that project. A single graph picks one node and overrides the colour locally.

All four claims are legitimate. Exactly one of them must win on every read, deterministically, with no surprises. The settings system exists to resolve that contest.

It does so by:

- giving each claim a well-defined *home* (a tier),
- treating each tier value as simply *set* (an opinion) or *unset* (no opinion), and
- evaluating reads through a fixed precedence chain: the highest-priority *set* tier wins.

> **Historical note.** Earlier versions added a fifth claim — an admin could *force* a value on a shared lab machine that beat even per-node overrides — implemented as an `OVERRIDE` strength on a tier value. That capability was deliberately removed; tiers are now plain set-or-unset and never "force." See [ADR 0011 — Collapse settings tiers](../../adr/0011-collapse-settings-tiers.md) for the rationale and what was lost.

What the system is **not** for:

- A general-purpose key-value store. Use `self.store` (per-node, persistent, hidden) or `self.cache` (per-node, transient, hidden). See [components/settings §3](../../components/settings/setting-canon.md#3-important-concepts).
- Live mutable state shared between editors and panels. Use `@state` and `LibraryStateContainer`. See [components/states](../../components/states/state-canon.md).
- A reactive UI primitive. Settings emit change callbacks; the rendering pipeline lives elsewhere.
- Per-node-class metadata (icon, colour, label) — that's `@node` decorator parameters, not a setting.

Author-facing concerns (declaring NodeSettings, `setting()` parameters, `shadow()`/`watch()`, panel rendering) live in [components/settings](../../components/settings/setting-canon.md). This document covers what happens *under* that surface.

## 2. The picture

Three things hold values, plus one central object that arbitrates between them.

```text
              SettingsRegistry
              ┌────────────────────────────┐
              │ global tier   (JSON dict)  │   ← ~/.haywire/settings.json
              │ workspace tier (JSON dict) │   ← <workspace>/.haywire/settings.json
              │ schema definitions         │   ← every setting() ever declared
              └────────────────────────────┘
                          ▲
                resolves reads through
                the four-step chain
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
 FrameworkSettings   LibrarySettings   NodeSettings
   (one per ns,        (one per ns,     (one per node
   auto-wired at       per loaded       instance, wired
   import time)        library)         by @node)
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                per-field DataField cells
              (per-instance overrides — the
               third tier, but lives on the
               instance as one cell per field,
               not on the registry)
```

Two things to notice:

1. **The first two tiers (global, workspace) live inside `SettingsRegistry`.** They're dicts the registry owns and consults during `resolve()`.
2. **The third tier (per-instance) lives on each `Settings` instance** as a per-field `DataField` cell — the same cell a port uses (see [§6.4 Single-cell value model](#64-single-cell-value-model) and [ADR 0013](../../adr/0013-settings-single-cell.md)). The cell's value is passed *into* `resolve()` per call. This asymmetry matters: it's why the resolution chain has to be told about local values explicitly.

A **schema class** (`FrameworkSettings`, `LibrarySettings`, `NodeSettings`) is just a `Settings` subclass that declares typed fields with `setting()`. `SettingsRegistry` is the runtime arbiter, not to be confused with `BaseRegistry` (the library system's class-tracking machinery, which is what registers `LibrarySettings` *classes* with the settings registry — see §6.1).

## 3. How a tier expresses its opinion

Each tier (global, workspace) stores a `SettingValue` per key. A tier value has exactly two states — **set** (it carries a value and is eligible to win) or **unset** (it has no opinion and defers down the chain):

```python
@dataclass
class SettingValue(Generic[T]):
    is_set: bool = False
    value: T | None = None

    @classmethod
    def unset(cls): ...          # no opinion — defer to the next tier
    @classmethod
    def of(cls, value): ...      # holds a value — eligible to win
```

There is no strength axis: a value is either an opinion or it isn't. The third tier — the per-instance field cell — works the same way, but the *opinion* is tracked separately from the *value*: a `DataField` cell always holds *a* value (its default), so membership can't stand in for set-ness. The instance keeps a `_set_keys: set[str]`; a field is locally set iff its `storage_key ∈ _set_keys` (mirroring the registry tiers' set-or-unset shape). See [§6.4](#64-single-cell-value-model).

In JSON, a set value is serialized through its IType's `to_dict` — a `{"value": …}` table nested by the dotted key:

```json
{ "ui": { "node": { "bg_color": { "value": "#f0f0f0" } } } }
```

`save_to_json()` only ever writes the workspace tier; the global JSON is hand-edited and never touched by the app. Each value is written as its IType's `to_dict` form and rehydrated via `from_dict` on load, so complex types (`COLOR`, `VEC2I`, `VEC3F`, …) round-trip losslessly — see [§8.3 Disk-edge serialization](#83-disk-edge-serialization) and [ADR 0012](../../adr/0012-settings-json-persistence.md). A legacy `{ "override": true, "value": X }` table left over from a pre-collapse file still loads — it is read as a plain *set* of `X`, with the `override` flag ignored.

## 4. The resolution chain

With set-or-unset tiers, precedence is simply *the highest-priority set tier wins*. Four cases fall out:

```text
self.filter.threshold        — look up _setting_key for this descriptor
        │
        ▼
1. Local instance value set?   → return it   (per-node override)
        │ no
        ▼
2. Workspace tier set?         → return it   (set via UI, saved to workspace JSON)
        │ no
        ▼
3. Global tier set?            → return it   (user's global preference)
        │ no
        ▼
4. Descriptor _default         → return it   (what the author declared)
```

`SettingsRegistry.resolve(name, local=None)` returns `(value, source)`, where `source` is one of `'local'`, `'workspace'`, `'global'`, `'default'` — useful for UIs that want to show *why* a value is what it is.

Instances constructed without a registry skip steps 2–3: a locally-set field returns its cell value, otherwise the descriptor default. That path is the common case for plain `Settings`/`NodeSettings` and for unit tests; see [§9 Test utilities](#9-test-utilities).

## 5. Worked example

```python
class ExecutionSettings(FrameworkSettings, namespace='execution'):
    max_threads = setting[int](4)

# At app startup, no JSON loaded yet:
#   resolve('execution.max_threads')  →  (4, 'default')           ← step 4

# User edits ~/.haywire/settings.json:
#   { "execution": { "max_threads": { "value": 8 } } }
# After load:
#   resolve('execution.max_threads')  →  (8, 'global')            ← step 3

# Workspace JSON adds:
#   { "execution": { "max_threads": { "value": 16 } } }
# After load:
#   resolve('execution.max_threads')  →  (16, 'workspace')        ← step 2

# A node instance sets a local override (writes the field's cell, marks _set_keys):
#   resolve('execution.max_threads',
#           local=SettingValue.of(32))  →  (32, 'local')          ← step 1 wins,
#                                                                    beats all below
```

Each step of the chain corresponds to one line above. If you can predict the `(value, source)` for each line without looking at the comments, you understand the system.

## 6. Contract details

The earlier sections give you the model; this one is reference material you can skip on a first read.

### 6.1 Three schema classes

All inherit from `Settings` (`packages/haywire-core/src/haywire/core/settings/settings.py`). They differ only in *how* they get wired to the registry:

| Class | File | Registration | When `cls._registry` is set |
| --- | --- | --- | --- |
| `FrameworkSettings` | `settings/schema.py` | Auto-register via `_pending_global` queue at registry init | Drained by `SettingsRegistry.__init__` → `_drain_pending_global()` |
| `LibrarySettings` | `settings/schema.py` | Via `BaseRegistry` hot-reload machinery (`_class_filter` picks up `class_identity`) | Set when the registry processes the class on library load |
| `NodeSettings` | `settings/node_settings.py` | Never registered as a *class* — settings *instances* are bound per-node by `@node` | Per-instance: `__init__` accepts `registry`; `@node` injects it from the node's wrapper |

Field descriptors on `FrameworkSettings` and `LibrarySettings` are auto-promoted to `persistent_setting` (a `setting` subclass that routes writes through `registry.set_global` + `save_to_json_debounced`). The swap happens during field setup — in `__init_subclass__` for the class-signature `namespace=` form, and in the `@settings` decorator for the decorator form. `NodeSettings` fields are NOT promoted; node-local settings persist with the graph, not the workspace JSON, so instance-local (cell) semantics is correct for them.

Deep inheritance (subclassing a `FrameworkSettings` or `LibrarySettings` subclass) is blocked by `__init_subclass__` to keep namespaces clean.

### 6.2 The four key identifiers

Four identifiers cooperate to thread a setting from class definition to JSON to panel. You won't normally write any of them by hand — the framework derives them — but you'll see them in tracebacks and registry dumps.

**`namespace`** — dot-separated prefix that identifies a schema. Set by `@settings(namespace='my_lib')` for `LibrarySettings` or `class FooSettings(FrameworkSettings, namespace='execution')` for `FrameworkSettings`.

```text
namespace='execution'   →   JSON object { "execution": { … } }
```

**`_setting_key`** — full address of one field: `{namespace}.{field_attr_name}`. Set on each `setting()` descriptor by `@settings` / `__init_subclass__` (for global schemas) or by `@node` / `_wire_settings_schemas` (for `NodeSettings`). For `FrameworkSettings` and `LibrarySettings`, the same setup pass also swaps the descriptor's `__class__` to `persistent_setting` so writes route through the registry (see [6.3 The write path](#63-the-write-path)).

```text
namespace='execution', field 'max_threads'
  →  _setting_key='execution.max_threads'

node registry_key='haybale_core:node:filter', accessor 'params', field 'threshold'
  →  _setting_key='haybale_core.node.filter.params.threshold'
```

This is what `SettingsRegistry` stores, resolves, and what `shadow()`/`watch()` reference. Single shared identity between schema, JSON, and registry lookup.

**`registry_key`** — `BaseRegistry`-level identifier for the *class* (not a field). Set by `@settings` as `reg_key(library_id, "settings", namespace)`. Used internally by `BaseRegistry` for class tracking, hot-reload, and dependency graphs. Not normally used directly by authors.

```text
namespace='my_lib', library_id='haybale_image'
  →  registry_key='haybale_image:settings:my_lib'
```

**`scope`** — runtime concept, not a class attribute. The properties-panel system reads class hierarchy at render time:

| Class type | Panel location | Scope label |
| --- | --- | --- |
| `FrameworkSettings` subclass | Global settings panel | `global` |
| `LibrarySettings` subclass | Library section of properties editor | `library` |
| `NodeSettings` instance | Node section of properties editor | `node` |

There is no `scope=` attribute on any settings class.

### 6.3 The write path

Section 4 traced how a `setting` value is *read* through the tier chain. Writes are simpler but have a comparable structural twist: which descriptor handles `__set__` depends on the schema class.

#### `setting.__set__` — instance-local

For `NodeSettings` and any plain `Settings` subclass, `setting.__set__` is the descriptor that runs. It writes the value into the field's `DataField` cell (`obj._cell_for(self).set_value(value)`), records the override in `obj._set_keys`, and fires `_on_property_change` to notify subscribers. The registry is not consulted; the write is invisible to peer instances and is never serialised to the workspace JSON. (An object-typed field with no IType keeps a narrow `_plain` dict instead of a cell — see [§6.4](#64-single-cell-value-model).)

#### `persistent_setting.__set__` — registry-backed

For `FrameworkSettings` and `LibrarySettings`, the descriptor is promoted to `persistent_setting` (a `setting` subclass) during field setup. Its `__set__` routes writes through the registry:

```python
# Roughly:
registry.set_global(setting_key, value)
registry.save_to_json_debounced()
```

Two consequences flow from this:

- The value lands in the registry's workspace tier, so a freshly-constructed peer instance sees it on its next read.
- `save_to_json_debounced` schedules a write to `<workspace>/.haywire/settings.json`, so the value survives restart.

The author never sees `persistent_setting`. They write `settings.field = value`; the framework's class swap ensures the right descriptor runs transparently:

```python
# Library settings panel writes this:
my_settings.api_url = "https://example.com"

# Because api_url's descriptor was promoted to persistent_setting at
# class-definition time, this call fans out to:
#   registry.set_global('my_lib.api_url', 'https://example.com')
#   registry.save_to_json_debounced()
# …rather than writing the instance-local cell.
```

#### Three places the class swap happens

Field descriptors get their `__class__` rewritten to `persistent_setting` in three places, depending on how the schema is registered:

1. `FrameworkSettings.__init_subclass__` — when a subclass uses class-signature `namespace=`.
2. `LibrarySettings.__init_subclass__` — same, for library-side schemas using the class-signature form.
3. `@settings(namespace=...)` decorator — the canonical pattern for `LibrarySettings`.

All three paths iterate `cls._property_settings()` and set `descriptor._setting_key` + `descriptor._mirror_key` + `descriptor.__class__ = persistent_setting` in one pass. Keeping the three paths in sync matters: missing the swap in one path silently restores the instance-local-only (cell) semantics for any schema registered through that path.

#### Why the descriptor does NOT call `_on_property_change`

`persistent_setting.__set__` deliberately omits the `_on_property_change` call that the base `setting` makes. `registry.set_global` fans out to every subscriber registered for that namespace — including the writing instance, if it subscribed via `Settings.subscribe(...)`. The chain there is `_notify_subscribers → _on_field_change → _on_property_change → user callback`. If the descriptor also called `_on_property_change` directly, any subscribed user callback would fire twice for the same write.

Instances that never subscribed receive no callback either way — neither from the descriptor nor from the registry. That is intentional: the writer just performed the write, so it does not need to be told what changed. Code that does want to react to its own writes (e.g. a panel that re-renders) must call `Settings.subscribe(...)` to opt in.

#### Fallback when no registry is wired

In test fixtures or unsaved workspaces, `persistent_setting.__set__` may run on an instance whose `_registry` is `None` or whose `_setting_key` is empty. In both cases it delegates to `super().__set__` — the base `setting`'s cell write — so existing test fixtures and no-registry usage are unaffected.

A related guard sits in `save_to_json_debounced` itself: when the registry has no workspace path configured (unsaved workspace), the debounce is a no-op rather than scheduling a timer whose firing would raise an error on a background thread. `set_global` still updates the in-memory workspace tier, so cross-instance visibility works even without disk persistence.

### 6.4 Single-cell value model

The per-instance value does **not** live in a loose dict. Every declared field owns one `DataField` **cell** on its `Settings` instance — the *same* cell class a node port uses — built lazily from the field's IType by `Settings._cell_for(descriptor)` and cached in `self._cells` keyed by `storage_key`. A setting and a port are two views of one value ([ADR 0013](../../adr/0013-settings-single-cell.md)). This is plan **P4** of the settings↔DataField unification arc (canonical-key → tier-collapse → TOML→JSON → **single-cell** → promotion-as-direction).

Three properties follow:

- **`cell ?? default` resolution.** `setting.__get__` returns the cell value when the field is locally set, else the per-kind default (a plain literal, or `registry.resolve(...)` for a shadow/watch/extended field). There is one instance-local store (cells), not a dual `_registry is None` split; the old "simple vs extended mode" branch collapses to "is this field locally set?".
- **The cell holds its value.** A local override is not recomputed on every read — the cell *holds* the value it was set to, so `__get__` returns it directly and only walks the chain when the field is unset.
- **`_set_keys` carries the opinion, not the cell.** A `DataField` always holds *a* value (its default), so cell membership cannot mean "overridden" the way dict membership did. `Settings._set_keys: set[str]` records the set-or-unset opinion explicitly: `__set__`/`from_dict` add the `storage_key`, `reset` discards it, and `is_locally_set(name)` ⇔ membership. Do **not** infer set-ness from `cell.get_value() != default` — that would misread "set to the default on purpose" and re-introduce the phantom-override bug P2 fixed at the tier level.

**Cell-mutation spine.** No *structural* action ever resets a cell. Once created, a field's cell persists for the life of the bag; its **value** returns to the default only on an explicit `reset()` (or moves by edit, or — in P5 — by edge-drive). `reset` clears `_set_keys` and calls `cell.reset()` (value → default); it never removes the cell. This is what makes the cell a stable identity a future port can bind to.

**Serialization stays bare.** The graph settings block keeps its existing wire shape — `bag.to_dict()` emits `{attr_name: bare_value}` per locally-set field (via `cell.get_value()`, not the IType `to_dict` dict), and `from_dict` writes each value back into the cell. Complex ITypes still round-trip losslessly because the *cell* guarantees the IType round-trip; the settings-block shape is unchanged, so existing saved graphs load. See [§7.4](#74-serialisation).

**Object-typed escape hatch.** A field with no IType (`_type is object`) cannot build a cell, so `_cell_for` returns `None` and those fields fall back to a narrow `_plain: dict`. In practice `SettingDescriptor.__set_name__` enforces an IType on every declared field, so `_plain` stays empty — it is a defensive path, not a revived general store.

**Promotion builds on this cell (P5, landed).** *Promotion* — a field + a direction — makes a port a second view of this same cell. See [§6.5 Promotion = field + direction](#65-promotion--field--direction) and [ADR 0014](../../adr/0014-promotion-as-direction.md). P5 also retired the UI's throwaway-`DataField` bridge (`SettingWidgetModel`), which now binds this cell directly for display.

### 6.5 Promotion = field + direction

*Promoting* a setting assigns it a **direction** and surfaces it as a DATA port. A promoted port and the setting it binds are **one cell, two views**: the port borrows the setting's [§6.4 cell](#64-single-cell-value-model) *by reference* via `DataPort.bind_field`, so there is no second value and no read-tier bridge ([ADR 0014](../../adr/0014-promotion-as-direction.md)).

**Two directions, two verbs.** `promote_setting(node, accessor, field, direction)` takes a `PortType ∈ {INLET, OUTLET}`; `demote_setting` removes it. There is no in-place redirect — redirect is demote + re-promote, and the cell (and its value) survives both, per the cell-mutation spine. The port id encodes the binding (`setting__<accessor>__<field>`) and, with `DataPort.promoted`, is the *whole* binding signal — the setting descriptor carries no port back-reference.

**Eligibility is two flag checks, not a per-kind matrix.**

1. `descriptor._read_only` (a `watch()` field) ⇒ **outlet only** — a read-only field has no write path in, only a read path out.
2. `direction == OUTLET` ⇒ the port sets `is_linked_lazy` **and** subscribes `on_changed → propagate`. This holds for *every* promoted outlet (plain, shadow, watch), because a promoted outlet is never worker-`out()`-driven; it is written by widget / registry / edge, all *outside* the scheduler frame.

Everything else (mirror vs plain, set vs unset) rides that one `on_changed → propagate` mechanism — there is no per-kind propagation logic. Plain and `shadow` fields are eligible for either direction; `watch` for outlet only.

**Freshness — the two-part `is_linked_lazy` mechanism.** An out-of-frame write is unsafe to propagate eagerly. So (1) a linked edge on an `is_linked_lazy` outlet is forced `is_lazy`, deferring each consumer's pull to its next execution; and (2) `bind_field` on an outlet subscribes `field.on_changed → self._pipes.propagate()`, which *triggers* that lazy pull (the flag alone is inert — a lazy pipe only pulls once its sink is marked dirty). Downstream is "fresh as of the consumer's next execution"; idle-liveness is out of scope.

**Mirror-cell authority.** For a promoted mirror to read correctly headless, the setting keeps a **cross-mirror** field's cell synced to the resolved global (`_cell_for` seeds it, `_on_field_change` writes it, `reset` re-seeds, `__get__` reads it, `cleanup` unsubscribes). "Cross-mirror" = a `shadow`/`watch` of *another* setting (`_mirror_key != storage_key`); a self-namespaced persistent field mirrors itself for resolution and is unaffected (its value lives in the registry tier).

**Value-less serialization; settings-first load.** A promoted port serializes as `promoted:true` + `id` + `port_type` + display kwargs — no `recipe`, no `field_data`; the value round-trips through the settings block only. On load, settings bags restore *before* ports, so `from_spec`'s promoted branch binds a cell already at its loaded value — no propagation mid-load.

**Freeze-on-disconnect.** Demote never resets the value (§C3): whatever the shared cell holds at demote stays. If that value diverges from the un-overridden resolution, the field is marked locally-set so the setting's own read returns it; recovery is an explicit `reset`.

## 7. Lifecycle

### 7.1 Registration and `_pending_global`

`FrameworkSettings` is the trickier case (it must self-register before the registry exists):

```text
Module imports FrameworkSettings subclass
  ↓
__init_subclass__ runs:
  - validates namespace=
  - sets _setting_key on every descriptor
  - swaps each descriptor's __class__ to persistent_setting
  - appends class to schema._pending_global queue
  ↓
... (later in startup, when DI assembles the registry) ...
  ↓
SettingsRegistry.__init__:
  - calls _drain_pending_global()
  - for each queued class:
      - registers the schema
      - sets cls._registry = self
  ↓
Now FooSettings() with no args is fully registry-wired.
```

`LibrarySettings` registers via the `BaseRegistry` hot-reload pipeline when the owning library loads (see [architecture/library-system](../library-system/library-system-arch.md)). The `@settings` decorator sets `class_identity`, which is what `BaseRegistry._class_filter` looks for. The decorator also performs the descriptor `__class__ = persistent_setting` swap that `LibrarySettings.__init_subclass__` would do for the class-signature `namespace=` form — both paths must keep their field-setup loops symmetric.

### 7.2 Hot-reload behaviour

When a library reloads (file watcher detects a `.py` change):

1. `BaseRegistry._on_change` re-imports the module.
2. `LibrarySettings` subclasses are re-registered under the same `_setting_key`s.
3. `cls._registry` is re-bound on the new class.
4. Existing `Settings` instances *holding the old class as their type* keep working — their per-field cells (and `_set_keys`) are unchanged, but their `_registry` reference must be re-acquired (the framework re-binds via the node-instance lifecycle).
5. Subscribed mirror callbacks are re-attached on the new class.

The hot-reload pipeline at large is documented in [architecture/hot-reload](../hot-reload/hot-reload-arch.md).

### 7.3 Change notification (`shadow()` / `watch()`)

There is no cached resolved value — `setting.__get__` calls `obj._resolve()` → `registry.resolve()` on every read. What the framework propagates is *change callbacks*, not cache invalidations.

The flow when a global value changes:

1. `SettingsRegistry.set_global()` updates the in-memory tier and calls `_notify_subscribers`.
2. `_notify_subscribers` walks `self._subscribers` — a dict of `namespace → list[weakref[callback]]` — and fires every callback whose namespace prefix matches the changed key.
3. For a `Settings` instance that has subscribed via `Settings.subscribe(user_callback)`, the registry-side callback is the instance's `_on_field_change`. It identifies which mirrored field changed, re-reads the resolved value through the chain, and calls `_on_property_change` → `user_callback`.
4. If the field has an `on_change` method on its node, `_on_property_change` calls it with the new value.

Important: callbacks fire only for instances that have explicitly called `Settings.subscribe(...)`. An instance that holds settings but never subscribed will not receive notifications when other code changes the underlying JSON value — its next read will resolve to the new value, but no callback runs in the meantime.

`Settings._subscribe_settings()` (plural — wires every field with a `_mirror_key`) and `_subscribe_setting()` (singular — wires one field) set up the weakref subscriptions; both are called from `Settings.subscribe()`. `Settings.cleanup()` clears the local callback list and marks the instance as torn down; the registry-side weakrefs are dropped when the instance is garbage-collected.

### 7.4 Serialisation

`Settings.to_dict()` returns only fields that are locally set (`_set_keys`) and whose value differs from the descriptor default, reading each value from the field's cell (`cell.get_value()`). `watch()` fields are never included. The emitted shape is the bare value per field (`{attr_name: value}`), matching the graph settings block that `NodeBase._to_dict` writes.

`Settings.from_dict(data, silent=True)` writes each value into the field's cell and marks it in `_set_keys` without firing callbacks (used during graph load to avoid spurious triggers). `silent=False` uses normal `setattr` semantics. Because the value round-trips through the field's `DataField` cell — the same IType `to_dict`/`from_dict` contract the registry uses at the disk edge ([ADR 0012](../../adr/0012-settings-json-persistence.md)) — complex ITypes (`COLOR`, `VEC2I`, …) survive a save/load cycle losslessly. See [§6.4 Single-cell value model](#64-single-cell-value-model) and [ADR 0013](../../adr/0013-settings-single-cell.md).

## 8. Examples

### 8.1 The full registry API

```python
from haywire.core.di.config import get_settings_registry

registry = get_settings_registry()

# Read with provenance
value, source = registry.resolve('execution.max_threads')
# → (4, 'default')   or   (8, 'global')   etc.

# Programmatic write — marks the tier *set* (workspace tier by default)
registry.set_global('execution.max_threads', 8)
registry.set_global('debug.verbose_logging', True)

# Reset to unset
registry.reset_global('execution.max_threads')

# Schema introspection
registry.has_definition('execution.max_threads')   # True
descriptor = registry.get_definition('execution.max_threads')
all_settings = registry.all_definitions()           # dict[str, setting]

# Programmatic schema definition (rarely needed)
new_setting = registry.define(
    'my.dynamic_setting',
    default=42,
    type_=int,
    label='My Dynamic Setting',
)

# JSON I/O
registry.load_from_json('~/.haywire/settings.json', tier='global')
registry.load_from_json('<workspace>/.haywire/settings.json', tier='workspace')
registry.save_to_json()  # writes workspace tier

# Subscribe (change-notification hook).
# `namespace=None` fires on every key; 'execution' fires on any
# 'execution.*' key; 'execution.max_threads' fires only on that exact key.
# Pass a plain callable — the registry stores it as a weakref internally,
# so the caller must keep a strong reference (hold `self`, or assign the
# function to a module-level name).
def on_namespace_change(key, value):
    print(f'{key} = {value}')

registry.subscribe('execution', on_namespace_change)
```

### 8.2 Reactive non-node access

Library/UI code that wants live access to a `LibrarySettings` field instantiates the schema directly. Once the library has loaded and `cls._registry` is set, no explicit injection is needed:

```python
from my_lib.settings import MyLibSettings

class MyRenderer:
    def __init__(self):
        self.settings = MyLibSettings()        # auto-wired to registry
        self.settings.subscribe(self._on_change)

    def render(self):
        url = self.settings.api_url            # resolves through chain on every read

    def _on_change(self, name, value, old):
        if name == 'api_url':
            self._reconnect()
```

For a one-off read without subscription:

```python
registry = get_settings_registry()
url, _ = registry.resolve('my_lib.api_url')
```

### 8.3 Disk-edge serialization

Both tiers persist as JSON (`~/.haywire/settings.json`, `<workspace>/.haywire/settings.json`). The serialization contract lives entirely **at the disk edge** — the in-memory tier holds the live Python value (a `str`, a `Vec2i`, …) and `resolve()` returns it unchanged. Conversion to and from JSON happens only inside `save_to_json` / `load_from_json`, keyed by each setting's declared IType:

- **Write** — `save_to_json` runs each set value through `_value_to_jsonable(name, value)`, which wraps it in the setting's `_type` and stores `IType(value).to_dict()` (a `{"value": …}` table). Keys with no code definition pass through as a plain scalar.
- **Read** — `load_from_json` runs each `{"value": …}` entry through `_value_from_jsonable(name, raw)`, which calls `IType.from_dict(raw)` to rehydrate the live value before it lands in the tier. The flatten/auto-define machinery (`_flatten_toml`, `_process_entry`) is reused unchanged; only the parse (`json.load`) and the value rehydration differ.

Because the conversion is keyed by IType, complex types round-trip losslessly — `COLOR`, `VEC2I`, `VEC3F`, … all serialize and rehydrate through the same `to_dict`/`from_dict` pair that graph JSON uses. This is a **hard cutover with no migration**: pre-existing `.toml` files are not read or converted. See [ADR 0012](../../adr/0012-settings-json-persistence.md).

## 9. Test utilities

All test helpers live in `haywire.core.di.test_config`:

```python
from haywire.core.di.test_config import (
    create_test_injector,
    create_test_library_system,
    create_test_settings_registry,
    create_test_bag,
    SettingsTestContext,
)
```

### 9.1 `create_test_settings_registry(predefined_settings=None, register_builtins=True)`

Isolated registry for unit tests. `predefined_settings` keys are full keys; values are *set* at the global tier.

```python
registry = create_test_settings_registry({'ui.node.bg_color': '#ff0000'})
value, source = registry.resolve('ui.node.bg_color')
# → ('#ff0000', 'global')

registry = create_test_settings_registry()  # default builtins, no overrides
value, source = registry.resolve('ui.node.bg_color')
# → ('#ffffff', 'default')
```

The framework's built-in `FrameworkSettings` schemas live under `haywire.ui.prefs` (`CanvasSettings`, `EdgeUISettings`, `EditorSettings`), `haywire.core.execution.settings` (`ExecutionSettings`), and `haywire.core.debug.debug_settings` (`DebugSettings`), plus skin/minimap/zoom variants under `haywire.ui.*`. `create_test_settings_registry` accepts a `register_builtins` parameter for opt-out, but at the time of writing the parameter is not yet wired through the function body — pass `predefined_settings` if you need specific keys pre-defined.

### 9.2 `create_test_bag(bag_cls=None, predefined_local=None, predefined_global=None)`

Returns `(registry, bag)` — a settings instance wired to an isolated registry. Default `bag_cls` is a minimal class with `bg_color`, `font_size`, `verbose`.

- `predefined_local` keys are **attr names** (`'bg_color'`)
- `predefined_global` keys are **full keys** (`'test.global.bg_color'`)

```python
registry, bag = create_test_bag(
    predefined_global={'test.global.font_size': 16},
    predefined_local={'font_size': 20},
)
assert bag.font_size == 20         # local wins (step 1 of resolution chain)
assert bag.is_locally_set('font_size')

bag.reset('font_size')
assert bag.font_size == 16         # falls back to global (step 3)
```

### 9.3 `SettingsTestContext`

Context manager for temporary registry mutations with auto-restore:

```python
service  = create_test_library_system(load_libraries=False, use_temp_settings=True)
registry = service.get_settings_registry()

with SettingsTestContext(registry) as ctx:
    ctx.set('debug.verbose_logging', True)             # mark the tier set
    ctx.set('ui.node.font_size', 20)

    assert registry.resolve('debug.verbose_logging')[0] is True
    assert registry.resolve('ui.node.font_size')[0] == 20

# After block: original values restored automatically
assert registry.resolve('debug.verbose_logging')[0] is False
```

Methods: `set(key, value)`, `reset(key)`.

### 9.4 Best practices

- Always pass `use_temp_settings=True` to `create_test_library_system()` so tests don't read from the user's real `~/.haywire/settings.json`.
- `predefined_local` uses attr names; `predefined_global` and `registry.set_global()` use full keys. Mismatches fail silently.
- Test both default values and local overrides on the same field.
- Test `read_only=True` fields raise `AttributeError` on write.

### 9.5 UI test harness

The settings UI harness in `tests/ui/harness/` lets Playwright tests verify rendered panel behaviour without spinning up the full Haywire app. It is a standalone NiceGUI app exposing three routes:

- `GET /node?class=<dotted.ClassName>&bag=<bag_name>` — renders a `NodeSettings` bag via `render_reactive()`
- `GET /schema?class=<dotted.ClassName>` — renders a `LibrarySettings` schema via `render_schema()`
- `POST /api/set?key=<key>&value=<value>` — writes to the registry (for mirror propagation tests)

The pytest fixture in `tests/ui/harness/conftest.py` starts the harness as a subprocess and shares one server across the session. Tests use `data-field` and `data-value` DOM attributes:

```python
from playwright.sync_api import Page, expect

def test_float_renders_default(page: Page, harness):
    page.goto('http://localhost:8090/node?class=...&bag=example')
    page.wait_for_selector('[data-field]')
    nd = page.locator('[data-field="example_float"] [data-number_drag]')
    expect(nd).to_have_attribute('data-value', '0.5')
```

For mirror propagation tests, `reset_setting` fixture restores after the test:

```python
import requests

def test_global_change_propagates(page, harness, reset_setting):
    reset_setting('testing.default_intensity', 0.5)
    requests.post('http://localhost:8090/api/set',
                  params={'key': 'testing.default_intensity', 'value': '0.9'})
    page.goto('...')
    nd = page.locator('[data-field="intensity"] [data-number_drag]')
    expect(nd).to_have_attribute('data-value', '0.9')
```

DOM contract for tests:

| Attribute | Element | Value |
| --- | --- | --- |
| `data-field="<attr>"` | row container `div` | field name as declared on the `Settings` class |
| `data-value="<v>"` | widget element | current rendered value as a string |
| `data-number_drag=""` | `NumberDrag` root | present on all `NumberDrag` widgets |
| `data-error="true"` | error label | present when last write was rejected by validator |

## 10. Open questions

- **Tier provenance UX.** `resolve()` returns the winning tier as `source`, but there's no in-app affordance that surfaces *why* a value resolved the way it did (e.g. "this came from the workspace JSON, not your global preference").
- **Schema migration.** Renaming a `setting()` field is currently unsupported — existing JSON and per-node serialised data still reference the old key, and there's no aliasing layer.
- **Type evolution.** Changing a field's `type_` (e.g. `int` → `float`) is a breaking change for existing graphs. Validators provide some safety but no migration path.
- **Per-graph settings tier.** Currently graphs serialise per-node overrides only; there's no notion of "this graph as a whole forces these settings" beyond the workspace tier. Could be useful for portable graphs that bring their own configuration.
