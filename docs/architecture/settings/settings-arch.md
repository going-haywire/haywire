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

## 1. Mental model

The settings system manages configuration at three levels: **global** application defaults, **workspace** overrides, and **per-node-instance** overrides. Schema classes (`FrameworkSettings` / `LibrarySettings` / `NodeSettings`) define the *shape*; TOML files (`~/.haywire/settings.toml`, `<workspace>/.haywire/settings.toml`) and per-node serialised dicts provide the *values only*. A central `SettingsRegistry` resolves any field through a six-step chain that mixes both sources with explicit precedence rules.

The system is bimodal:

- **Simple mode** — a `Settings` instance constructed without a registry reads/writes only its `_local_store`. Zero overhead, no resolution chain. Useful for unit tests and standalone use.
- **Extended mode** — a `Settings` instance constructed with a registry (or whose class auto-wires `cls._registry`) goes through the full resolution chain on every read.

Author-facing concerns (declaring NodeSettings, `setting()` parameters, `shadow()`/`watch()` mirror behaviour, panel rendering rules) live in [components/settings](../../components/settings/setting-canon.md). This file documents what happens *under* that surface.

## 2. Contract

### 2.1 Three schema classes

All inherit from `Settings` (`packages/haywire-core/src/haywire/core/settings/settings.py`).

| Class | File | Registration | When `cls._registry` is set |
|---|---|---|---|
| `FrameworkSettings` | `settings/schema.py` | Auto-register via `_pending_global` queue at registry init | Drained by `SettingsRegistry.__init__` → `_drain_pending_global()` |
| `LibrarySettings` | `settings/schema.py` | Via `BaseRegistry` hot-reload machinery (`_class_filter` picks up `class_identity`) | Set when the registry processes the class on library load |
| `NodeSettings` | `settings/node_settings.py` | Never registered as a *class* — settings *instances* are bound per-node by `@node` | Per-instance: `__init__` accepts `registry`; `@node` injects it from the node's wrapper |

Deep inheritance (subclassing a `FrameworkSettings` or `LibrarySettings` subclass) is blocked by `__init_subclass__` to keep namespaces clean.

### 2.2 The four key identifiers

Four identifiers cooperate to thread a setting from class definition to TOML to panel:

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
|---|---|---|
| `FrameworkSettings` subclass | Global settings panel | `global` |
| `LibrarySettings` subclass | Library section of properties editor | `library` |
| `NodeSettings` instance | Node section of properties editor | `node` |

There is no `scope=` attribute on any settings class.

### 2.3 `SettingMode` enum

```python
class SettingMode(Enum):
    INHERIT  = auto()  # No opinion — defer to next tier up
    EXPLICIT = auto()  # Deliberate value — wins unless OVERRIDE'd
    OVERRIDE = auto()  # Forced — wins over everything below
```

Each tier (global, workspace) holds a `SettingValue(mode, value)` per key. `INHERIT` is the absence of an opinion; `EXPLICIT` is "set deliberately"; `OVERRIDE` is "force this regardless of lower tiers."

### 2.4 TOML format

```toml
# ~/.haywire/settings.toml
[ui.node]
bg_color = "#f0f0f0"                                # EXPLICIT
font_size = { override = true, value = 14 }          # OVERRIDE

[debug]
verbose_logging = true                               # EXPLICIT
```

`save_to_toml(path)` writes only the workspace tier — the global tier is hand-edited and never overwritten by the application.

## 3. Lifecycle

### 3.1 Six-step resolution chain (extended mode)

For every read of a registry-wired field:

```text
self.filter.threshold        — looks up _setting_key for the descriptor
        │
        ▼
1. Global tier OVERRIDE present?    → return it (admin policy, hand-edited TOML)
        │ no
        ▼
2. Workspace tier OVERRIDE present? → return it (workspace-wide force)
        │ no
        ▼
3. Local instance value present?    → return it (per-node override)
        │ no
        ▼
4. Workspace tier EXPLICIT present? → return it (set via UI, saved to workspace TOML)
        │ no
        ▼
5. Global tier EXPLICIT present?    → return it (user global default)
        │ no
        ▼
6. Descriptor _default              → return it
```

`SettingsRegistry.resolve(name, local=None)` returns `(value, source)` where source is one of `'global_override'`, `'workspace_override'`, `'local'`, `'workspace'`, `'global'`, `'default'`. Simple-mode instances skip steps 1–2 and 4–5.

### 3.2 Registration and `_pending_global`

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

### 3.3 Hot-reload behaviour

When a library reloads (file watcher detects a `.py` change):

1. `BaseRegistry._on_change` re-imports the module.
2. `LibrarySettings` subclasses are re-registered under the same `_setting_key`s.
3. `cls._registry` is re-bound on the new class.
4. Existing `Settings` instances *holding the old class as their type* keep working — their `_local_store` is unchanged, but their `_registry` reference must be re-acquired (the framework re-binds via the node-instance lifecycle).
5. Subscribed mirror callbacks are re-attached on the new class.

The hot-reload pipeline at large is documented in [architecture/hot-reload](../hot-reload/hot-reload-arch.md).

### 3.4 Mirror cache invalidation (`shadow()` / `watch()`)

Mirror fields cache the resolved global value to avoid re-resolving on every read. When the global value changes:

1. `SettingsRegistry.set_global()` (or `set_override`) detects the change.
2. The registry walks `_namespace_subscribers` (a weakref dict keyed by namespace) and fires invalidation callbacks.
3. Each mirror field's cached value is invalidated; the next read re-resolves through the chain.
4. If the field has an `on_change` callback on its node, that callback fires with the new value.

`Settings._subscribe_mirrors()` sets up the weakref subscriptions; called automatically by `BaseNode` after settings construction. `Settings.cleanup()` releases them on node removal.

### 3.5 Serialisation

`Settings.to_dict()` returns only fields whose value differs from the descriptor default. `watch()` fields are never included.

`Settings.from_dict(data, silent=True)` writes directly to `_local_store` without firing callbacks (used during graph load to avoid spurious triggers). `silent=False` uses normal `setattr` semantics.

## 4. Boundary

The settings system is **not**:

- A general-purpose key-value store. Use `self.store` (per-node, persistent, hidden) or `self.cache` (per-node, transient, hidden) for that — see [components/settings §3](../../components/settings/setting-canon.md#3-important-concepts).
- A way to share live mutable state between editors and panels. Use the `@state` decorator and `LibraryStateContainer` instead — see [components/states](../../components/states/state-canon.md).
- A reactive UI primitive. Settings emit change callbacks, but the rendering pipeline that paints panels lives elsewhere.
- A way to define schema attributes that aren't user-configurable values. For per-node-class metadata (icon, colour, label), use the `@node` decorator parameters; for runtime-only flags, use `self.behavior`.

## 5. Examples

### 5.1 The full registry API

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

# Subscribe (cache-invalidation hook for mirror fields)
def on_namespace_change(name, value, old):
    print(f'{name} changed from {old} to {value}')

import weakref
registry.subscribe_namespace('execution', weakref.WeakMethod(on_namespace_change))
```

### 5.2 Resolution chain in practice

```python
# Framework default
class ExecutionSettings(FrameworkSettings, namespace='execution'):
    max_threads = setting[int](4)

# At app startup, registry contains:
#   execution.max_threads → SettingValue(INHERIT) on both tiers
#   resolve('execution.max_threads') → (4, 'default')

# User edits ~/.haywire/settings.toml:
#   [execution]
#   max_threads = 8
# After load:
#   resolve('execution.max_threads') → (8, 'global')   ← step 5 hit

# Workspace TOML overrides:
#   [execution]
#   max_threads = 16
# After load:
#   resolve('execution.max_threads') → (16, 'workspace')   ← step 4 hit

# A node instance sets a local override:
#   instance._local_store['max_threads'] = 32
# resolve called WITH local override:
#   resolve('execution.max_threads', local=SettingValue(EXPLICIT, 32)) → (32, 'local')   ← step 3 hit

# Admin force in global TOML:
#   [execution]
#   max_threads = { override = true, value = 2 }
# After load:
#   resolve(...) → (2, 'global_override')   ← step 1 wins, beats everything below
```

### 5.3 Reactive non-node access

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

## 6. Test utilities

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

### 6.1 `create_test_settings_registry(predefined_settings=None, register_builtins=True)`

Isolated registry for unit tests. `predefined_settings` keys are full keys; values are applied in `EXPLICIT` mode at the global tier.

```python
registry = create_test_settings_registry({'ui.node.bg_color': '#ff0000'})
value, source = registry.resolve('ui.node.bg_color')
# → ('#ff0000', 'global')

registry = create_test_settings_registry()  # default builtins, no overrides
value, source = registry.resolve('ui.node.bg_color')
# → ('#ffffff', 'default')
```

`register_builtins=False` skips registering `NodeUISettings` / `EdgeUISettings` / `DebugSettings` / `ExecutionSettings` / `EditorSettings` — useful when testing in pure isolation.

### 6.2 `create_test_bag(bag_cls=None, predefined_local=None, predefined_global=None)`

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

### 6.3 `SettingsTestContext`

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

### 6.4 Best practices

- Always pass `use_temp_settings=True` to `create_test_library_system()` so tests don't read from the user's real `~/.haywire/settings.toml`.
- `predefined_local` uses attr names; `predefined_global` and `registry.set_global()` use full keys. Mismatches fail silently.
- Test both default values and local overrides on the same field.
- Test `read_only=True` fields raise `AttributeError` on write.

### 6.5 UI test harness

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
|---|---|---|
| `data-field="<attr>"` | row container `div` | field name as declared on the `Settings` class |
| `data-value="<v>"` | widget element | current rendered value as a string |
| `data-number_drag=""` | `NumberDrag` root | present on all `NumberDrag` widgets |
| `data-error="true"` | error label | present when last write was rejected by validator |

## 7. Open questions

- **Cross-tier conflict resolution UX.** When global has `OVERRIDE` and workspace has `EXPLICIT`, the global wins silently. There's no in-app affordance that surfaces this to the user (they see a value they can't change but no explanation).
- **Schema migration.** Renaming a `setting()` field is currently unsupported — existing TOML and per-node serialised data still reference the old key, and there's no aliasing layer.
- **Type evolution.** Changing a field's `type_` (e.g. `int` → `float`) is a breaking change for existing graphs. Validators provide some safety but no migration path.
- **Per-graph settings tier.** Currently graphs serialise per-node overrides only; there's no notion of "this graph as a whole forces these settings" beyond the workspace tier. Could be useful for portable graphs that bring their own configuration.
