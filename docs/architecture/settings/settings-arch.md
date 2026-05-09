---
status: draft
doc_template: impl-spec
scope: Settings framework — three-tier model, SettingsRegistry, six-step resolution chain, TOML format, FrameworkSettings, test utilities
see-also:
  - ../../components/settings/setting-canon.md
  - ../hot-reload/hot-reload-arch.md
  - ../library-system/library-system-arch.md
  - ../../reference/glossary.md
---

# Settings — Architecture

## 1. Motivation

A node author writes `bg_color = "#fff"` as a default. The user opens the global settings panel and prefers `#000` everywhere. The user's workspace lead pins it to `#f0f0f0` for that project. A single graph picks one node and overrides the colour locally. And on a shared lab machine, the admin hand-edits a TOML file to *force* `#222` on every node, regardless of what anyone else asked for.

All five claims are legitimate. Exactly one of them must win on every read, deterministically, with no surprises. The settings system exists to resolve that contest.

It does so by:

- giving each claim a well-defined *home* (a tier),
- letting each tier mark a value as either *an opinion* or *a force*, and
- evaluating reads through a fixed precedence chain.

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
              │ global tier   (TOML dict)  │   ← ~/.haywire/settings.toml
              │ workspace tier (TOML dict) │   ← <workspace>/.haywire/settings.toml
              │ schema definitions         │   ← every setting() ever declared
              └────────────────────────────┘
                          ▲
                resolves reads through
                the six-step chain
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
                     _local_store
              (per-instance overrides —
               the third tier, but lives
               on the instance, not the
               registry)
```

Two things to notice:

1. **The first two tiers (global, workspace) live inside `SettingsRegistry`.** They're dicts the registry owns and consults during `resolve()`.
2. **The third tier (per-instance) lives on each `Settings` instance** as `_local_store`. It's passed *into* `resolve()` per call. This asymmetry matters: it's why the resolution chain has to be told about local values explicitly.

A **schema class** (`FrameworkSettings`, `LibrarySettings`, `NodeSettings`) is just a `Settings` subclass that declares typed fields with `setting()`. `SettingsRegistry` is the runtime arbiter, not to be confused with `BaseRegistry` (the library system's class-tracking machinery, which is what registers `LibrarySettings` *classes* with the settings registry — see §6.1).

## 3. How a tier expresses its opinion

Each tier (global, workspace) stores a `SettingValue(mode, value)` per key. The mode says *how strong the claim is*:

```python
class SettingMode(Enum):
    INHERIT  = auto()  # No opinion — defer to next tier up
    EXPLICIT = auto()  # Deliberate value — wins unless OVERRIDE'd from above
    OVERRIDE = auto()  # Forced — beats everything below, including locals
```

The third tier — per-instance `_local_store` — has no mode. Its presence *is* its opinion: if a key is in the dict, the instance has set it; otherwise it hasn't. Conceptually it sits at `EXPLICIT`-strength, between the workspace and global EXPLICITs but beneath any OVERRIDE.

In TOML, `EXPLICIT` is a bare value and `OVERRIDE` uses an inline-table form:

```toml
[ui.node]
bg_color = "#f0f0f0"                              # EXPLICIT — user's preference
font_size = { override = true, value = 14 }       # OVERRIDE — forced from this tier down
```

The asymmetry is deliberate: writing an OVERRIDE is rare and demands a more visible syntax. `save_to_toml()` only ever writes the workspace tier; the global TOML is hand-edited and never touched by the app.

## 4. The resolution chain

Given the three tiers and two strengths, precedence is fully determined: any OVERRIDE from above must beat a local value, and a local value must beat any non-OVERRIDE from below. Six cases fall out:

```text
self.filter.threshold        — look up _setting_key for this descriptor
        │
        ▼
1. Global tier OVERRIDE?       → return it   (admin policy, hand-edited TOML)
        │ no
        ▼
2. Workspace tier OVERRIDE?    → return it   (workspace-wide force)
        │ no
        ▼
3. Local instance value?       → return it   (per-node override)
        │ no
        ▼
4. Workspace tier EXPLICIT?    → return it   (set via UI, saved to workspace TOML)
        │ no
        ▼
5. Global tier EXPLICIT?       → return it   (user's global preference)
        │ no
        ▼
6. Descriptor _default         → return it   (what the author declared)
```

`SettingsRegistry.resolve(name, local=None)` returns `(value, source)`, where `source` is one of `'global_override'`, `'workspace_override'`, `'local'`, `'workspace'`, `'global'`, `'default'` — useful for UIs that want to show *why* a value is what it is.

Instances constructed without a registry skip steps 1–2 and 4–5 and fall through to a direct `_local_store` lookup. That path exists for unit tests; see [§9 Test utilities](#9-test-utilities).

## 5. Worked example

```python
class ExecutionSettings(FrameworkSettings, namespace='execution'):
    max_threads = setting[int](4)

# At app startup, no TOML loaded yet:
#   resolve('execution.max_threads')  →  (4, 'default')           ← step 6

# User edits ~/.haywire/settings.toml:
#   [execution]
#   max_threads = 8
# After load:
#   resolve('execution.max_threads')  →  (8, 'global')            ← step 5

# Workspace TOML adds:
#   [execution]
#   max_threads = 16
# After load:
#   resolve('execution.max_threads')  →  (16, 'workspace')        ← step 4

# A node instance sets a local override (instance._local_store['max_threads'] = 32):
#   resolve('execution.max_threads',
#           local=SettingValue(EXPLICIT, 32))  →  (32, 'local')   ← step 3

# Admin appends OVERRIDE to global TOML:
#   [execution]
#   max_threads = { override = true, value = 2 }
# After load:
#   resolve(...)  →  (2, 'global_override')                       ← step 1 wins,
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

Deep inheritance (subclassing a `FrameworkSettings` or `LibrarySettings` subclass) is blocked by `__init_subclass__` to keep namespaces clean.

### 6.2 The four key identifiers

Four identifiers cooperate to thread a setting from class definition to TOML to panel. You won't normally write any of them by hand — the framework derives them — but you'll see them in tracebacks and registry dumps.

**`namespace`** — dot-separated prefix that identifies a schema. Set by `@settings(namespace='my_lib')` for `LibrarySettings` or `class FooSettings(FrameworkSettings, namespace='execution')` for `FrameworkSettings`.

```text
namespace='execution'   →   TOML section [execution]
```

**`_setting_key`** — full TOML address of one field: `{namespace}.{field_attr_name}`. Set on each `setting()` descriptor by `@settings` / `__init_subclass__` (for global schemas) or by `@node` / `_wire_settings_schemas` (for `NodeSettings`).

```text
namespace='execution', field 'max_threads'
  →  _setting_key='execution.max_threads'

node registry_key='haybale_core:node:filter', accessor 'params', field 'threshold'
  →  _setting_key='haybale_core.node.filter.params.threshold'
```

This is what `SettingsRegistry` stores, resolves, and what `shadow()`/`watch()` reference. Single shared identity between schema, TOML, and registry lookup.

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

## 7. Lifecycle

### 7.1 Registration and `_pending_global`

`FrameworkSettings` is the trickier case (it must self-register before the registry exists):

```text
Module imports FrameworkSettings subclass
  ↓
__init_subclass__ runs:
  - validates namespace=
  - sets _setting_key on every descriptor
  - appends class to schema._pending_global queue
  ↓
... (later, possibly minutes) ...
  ↓
SettingsRegistry.__init__:
  - calls _drain_pending_global()
  - for each queued class:
      - registers the schema
      - sets cls._registry = self
  ↓
Now FooSettings() with no args is fully registry-wired.
```

`LibrarySettings` registers via the `BaseRegistry` hot-reload pipeline when the owning library loads (see [architecture/library-system](../library-system/library-system-arch.md)). The `@settings` decorator sets `class_identity`, which is what `BaseRegistry._class_filter` looks for.

### 7.2 Hot-reload behaviour

When a library reloads (file watcher detects a `.py` change):

1. `BaseRegistry._on_change` re-imports the module.
2. `LibrarySettings` subclasses are re-registered under the same `_setting_key`s.
3. `cls._registry` is re-bound on the new class.
4. Existing `Settings` instances *holding the old class as their type* keep working — their `_local_store` is unchanged, but their `_registry` reference must be re-acquired (the framework re-binds via the node-instance lifecycle).
5. Subscribed mirror callbacks are re-attached on the new class.

The hot-reload pipeline at large is documented in [architecture/hot-reload](../hot-reload/hot-reload-arch.md).

### 7.3 Mirror cache invalidation (`shadow()` / `watch()`)

Mirror fields cache the resolved global value to avoid re-resolving on every read. When the global value changes:

1. `SettingsRegistry.set_global()` (or `set_override`) detects the change.
2. The registry walks `_namespace_subscribers` (a weakref dict keyed by namespace) and fires invalidation callbacks.
3. Each mirror field's cached value is invalidated; the next read re-resolves through the chain.
4. If the field has an `on_change` callback on its node, that callback fires with the new value.

`Settings._subscribe_mirrors()` sets up the weakref subscriptions; called automatically by `BaseNode` after settings construction. `Settings.cleanup()` releases them on node removal.

### 7.4 Serialisation

`Settings.to_dict()` returns only fields whose value differs from the descriptor default. `watch()` fields are never included.

`Settings.from_dict(data, silent=True)` writes directly to `_local_store` without firing callbacks (used during graph load to avoid spurious triggers). `silent=False` uses normal `setattr` semantics.

## 8. Examples

### 8.1 The full registry API

```python
from haywire.core.di.config import get_settings_registry
from haywire.core.settings import SettingMode

registry = get_settings_registry()

# Read with provenance
value, source = registry.resolve('execution.max_threads')
# → (4, 'default')   or   (8, 'global')   etc.

# Programmatic write to the global tier
registry.set_global('execution.max_threads', 8, mode=SettingMode.EXPLICIT)
registry.set_global('debug.verbose_logging', True, mode=SettingMode.OVERRIDE)

# Reset to INHERIT
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

# TOML I/O
registry.load_from_toml('~/.haywire/settings.toml', tier='global')
registry.load_from_toml('<workspace>/.haywire/settings.toml', tier='workspace')
registry.save_to_toml()  # writes workspace tier

# Subscribe (cache-invalidation hook for mirror fields).
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

Isolated registry for unit tests. `predefined_settings` keys are full keys; values are applied in `EXPLICIT` mode at the global tier.

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
assert bag.font_size == 20         # local wins (step 3 of resolution chain)
assert bag.is_locally_set('font_size')

bag.reset('font_size')
assert bag.font_size == 16         # falls back to global (step 5)
```

### 9.3 `SettingsTestContext`

Context manager for temporary registry mutations with auto-restore:

```python
service  = create_test_library_system(load_libraries=False, use_temp_settings=True)
registry = service.get_settings_registry()

with SettingsTestContext(registry) as ctx:
    ctx.set('debug.verbose_logging', True)             # SET mode
    ctx.set_override('ui.node.font_size', 20)          # OVERRIDE mode

    assert registry.resolve('debug.verbose_logging')[0] is True
    assert registry.resolve('ui.node.font_size')[0] == 20

# After block: original values restored automatically
assert registry.resolve('debug.verbose_logging')[0] is False
```

Methods: `set(key, value)`, `set_override(key, value)`, `reset(key)`.

### 9.4 Best practices

- Always pass `use_temp_settings=True` to `create_test_library_system()` so tests don't read from the user's real `~/.haywire/settings.toml`.
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

- **Cross-tier conflict resolution UX.** When global has `OVERRIDE` and workspace has `EXPLICIT`, the global wins silently. There's no in-app affordance that surfaces this to the user (they see a value they can't change but no explanation).
- **Schema migration.** Renaming a `setting()` field is currently unsupported — existing TOML and per-node serialised data still reference the old key, and there's no aliasing layer.
- **Type evolution.** Changing a field's `type_` (e.g. `int` → `float`) is a breaking change for existing graphs. Validators provide some safety but no migration path.
- **Per-graph settings tier.** Currently graphs serialise per-node overrides only; there's no notion of "this graph as a whole forces these settings" beyond the workspace tier. Could be useful for portable graphs that bring their own configuration.
