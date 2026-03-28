# Settings System Overview

Haywire's settings system manages configuration at three levels: global/workspace application defaults, per-node instance overrides, and transient runtime data.

## The Three Containers

Every node instance exposes three containers:

| Container | Serialized | GUI-visible | Hierarchical |
|-----------|-----------|-------------|--------------|
| `self.cache` | No | No | No |
| `self.store` | Yes | No | No |
| `self.<settings_name>` | Yes (local overrides only) | Yes | Yes (optional) |

**Use `self.cache`** for transient computation data (lookup tables, buffers, memoization).
**Use `self.store`** for persistent internal state users don't see (counters, accumulators, state machines).
**Use `self.<settings_name>`** for anything users should be able to see and configure.

---

## Architecture

### Global Registry

At startup, `SettingsRegistry` is populated from class-based schema definitions:

```
SettingsRegistry
├── FrameworkSettings schemas (auto-registered via _pending_global at registry init)
│   ├── EdgeUISettings (namespace='ui.edge')  → ui.edge.color, ui.edge.width ...
│   ├── DebugSettings  (namespace='debug')    → debug.verbose_logging ...
│   ├── ExecutionSettings (namespace='execution') → execution.auto_execute ...
│   └── EditorSettings (namespace='editor')   → editor.undo_limit ...
│
├── LibrarySettings schemas (registered via BaseRegistry hot-reload machinery)
│   └── NodeUISettings (namespace='ui.node')  → ui.node.bg_color, ui.node.font_size ...
│
├── global settings.toml (~/.haywire/settings.toml)           — user VALUES, global tier (hand-edited)
└── workspace settings.toml (<workspace>/.haywire/settings.toml) — workspace VALUES, set via UI
```

Schema classes define the *shape* of settings. TOML files provide *values only*.

```toml
# ~/.haywire/settings.toml
[ui.node]
bg_color = "#f0f0f0"
font_size = { override = true, value = 14 }  # OVERRIDE mode

[debug]
verbose_logging = true
```

### Node Settings

Nodes declare settings as inner classes that inherit from `NodeSettings`. The class name becomes the **accessor name** used to read settings directly from the node instance.

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, Color
from haywire.core.settings.builtins.ui_node import NodeUISettings
from haywire.core.settings.builtins.debug import DebugSettings

@node(label="My Node")
class MyNode(BaseNode):

    class filter(NodeSettings):
        # Local setting — stored in graph, shown in properties panel
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')

        # mirrors= — inherits global default; per-node override shown with reset affordance
        bg_color: Color = setting(mirrors=NodeUISettings.bg_color)

        # mirrors= + read_only=True — read-only cache of a global; invisible in panel
        verbose: bool = setting(mirrors=DebugSettings.verbose_logging, read_only=True)

    def worker(self, context):
        result = value * self.filter.threshold   # direct access — no extra indirection
        self.out('result', result)
```

The `@node` decorator scans the class body for all `NodeSettings` subclasses, assigns a `_field_key` to each `setting()` descriptor (derived from the node's `registry_key`), and binds each settings instance directly on the node object at construction time.

### Per-Node Resolution Chain (Extended Mode)

When a `SettingsRegistry` is injected, each `setting()` field with a `_field_key` set goes through the full resolution chain:

```
self.filter.threshold
        │
        ▼
1. Global tier OVERRIDE for 'my_lib.node.my.filter.threshold'?    → return it (admin policy)
        │ No
        ▼
2. Workspace tier OVERRIDE for the key?                           → return it
        │ No
        ▼
3. Local value in this settings instance?                         → return it
        │ No
        ▼
4. Workspace tier SET for the key?                                → return it (set via UI)
        │ No
        ▼
5. Global tier SET for the key?                                   → return it (user global default)
        │ No
        ▼
6. Descriptor _default                                            → return it
```

Settings instances without a registry (simple mode) skip steps 1–2 and 4–5 — they read directly from the local store.

---

## Descriptor Parameters

| Parameter | Behaviour |
| --------- | --------- |
| `setting(default)` | Local node setting — stored in graph, shown in panel |
| `setting(mirrors=FrameworkSettings.field)` | Inherits global value; override shown with reset affordance |
| `setting(mirrors=..., read_only=True)` | Read-only global cache — invisible in panel, never stored |
| `setting(..., on_change='method_name')` | Fires `method(value, field_name)` on change |

---

## Accessing Settings in Node Code

Access is direct via the **settings accessor name** (inner class name), then the **field name**:

```python
def worker(self, context, value: float):
    s = self.filter
    if s.verbose:
        context.log(f"Processing: {value}")

    result = value * s.threshold
    self.out('result', result)
```

---

## Serialization

Only locally-overridden values are serialized with the node. Global values and `read_only` fields are never stored.

```json
{
  "node_id": "abc123",
  "settings": {
    "filter": { "threshold": 0.8, "bg_color": "#ff0000" }
  },
  "store": { "execution_count": 42 }
}
```

The outer key is the **settings accessor name**. The inner dict maps attr name → locally set value. Fields at their default are omitted.

---

## Key Identifiers: namespace, _field_key, registry_key, and panel routing

Four identifiers cooperate to connect a settings field from its class definition all the way to a panel in the UI. Understanding how they relate prevents confusion.

### `namespace`

The dot-separated prefix that identifies a settings schema in TOML and the registry. Set by the `@settings` decorator (for `LibrarySettings`) or the `namespace=` kwarg (for `FrameworkSettings`).

```text
namespace='execution'   →   TOML section [execution]
namespace='my_lib'      →   TOML section [my_lib]
```

### `_field_key`

The full TOML address of a single field: `{namespace}.{field_attr_name}`. Set on each `setting()` descriptor by `@settings` / `__init_subclass__` (for `FrameworkSettings`/`LibrarySettings`) or by `@node` / `_wire_settings_schemas` (for `NodeSettings`).

```text
namespace='execution', field 'max_threads'  →  _field_key='execution.max_threads'
node registry_key='haybale_core:node:filter', accessor 'params', field 'threshold'
    →  _field_key='haybale_core.node.filter.params.threshold'
```

`_field_key` is what the `SettingsRegistry` stores, resolves, and what `mirrors=` references. It is the single shared identity between schema, TOML, and registry lookup.

### `registry_key`

The `BaseRegistry`-level identifier for the settings *class* (not a field). Set by `@settings` as `reg_key(library_id, "settings", namespace)`. Used internally by `BaseRegistry` for class tracking, hot-reload, and dependency graphs. Not normally used directly by node or library authors.

```text
namespace='my_lib', library_id='haybale_image'
    →  registry_key='haybale_image:settings:my_lib'
```

### How they relate

```text
@settings(namespace='my_lib')          ← sets _namespace on the class
class MyLibSettings(LibrarySettings):
    quality: int = setting(85)         ← _field_key = 'my_lib.quality'
                                          (set by @settings on the descriptor)

    ↓ BaseRegistry registers the class under:
    registry_key = 'haybale_image:settings:my_lib'

    ↓ SettingsRegistry stores the field under:
    _field_key = 'my_lib.quality'

    ↓ TOML resolution reads from:
    [my_lib]
    quality = 90
```

For `NodeSettings` the chain is different — `_field_key` is node-scoped and never entered into the registry as a schema field; it is only used for TOML-tier resolution of that node's local overrides.

### Panel routing and `scope`

`scope` is a **runtime** concept, not a class-level property. It is determined by the UI panel system when rendering settings panels, based on the class type:

| Class type | Panel location | Scope |
|---|---|---|
| `FrameworkSettings` subclass | Global settings panel | `global` |
| `LibrarySettings` subclass | Library section of properties editor | `library` |
| `NodeSettings` instance | Node section of properties editor | `node` |

The properties editor queries registered panels filtered by the active session scope. There is no `scope=` attribute on settings classes — the class hierarchy (`FrameworkSettings` vs `LibrarySettings` vs `NodeSettings`) is the routing signal the panel system reads.

---

## Next Steps

- **[Node Development Guide](02-node-development.md)** — Defining and using settings in nodes
- **[Library Development Guide](03-library-development.md)** — Creating `LibrarySettings` for your library
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
