# Settings System Overview

Haywire's settings system manages configuration at three levels: global/workspace application defaults, per-node instance overrides, and transient runtime data.

## The Three Containers

Every node instance exposes three containers:

| Container | Serialized | GUI-visible | Hierarchical |
|-----------|-----------|-------------|--------------|
| `self.cache` | No | No | No |
| `self.store` | Yes | No | No |
| `self.<bag_name>` | Yes (local overrides only) | Yes | Yes (optional) |

**Use `self.cache`** for transient computation data (lookup tables, buffers, memoization).
**Use `self.store`** for persistent internal state users don't see (counters, accumulators, state machines).
**Use `self.<bag_name>`** for anything users should be able to see and configure.

---

## Architecture

### Global Registry

At startup, `GlobalSettingsRegistry` is populated from class-based schema definitions:

```
GlobalSettingsRegistry
├── Built-in GlobalSettings schemas (registered via register_schema() in DI)
│   ├── NodeUISettings (namespace='ui.node')  → ui.node.bg_color, ui.node.font_size ...
│   ├── EdgeUISettings (namespace='ui.edge')  → ui.edge.color, ui.edge.width ...
│   ├── DebugSettings  (namespace='debug')    → debug.verbose_logging ...
│   ├── ExecutionSettings (namespace='execution') → execution.auto_execute ...
│   └── EditorSettings (namespace='editor')   → editor.undo_limit ...
│
├── Library LibrarySettings schemas (discovered via @settings decorator)
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

### Node Settings — Bag-Based

Nodes declare settings as inner classes that inherit from `Settings` (an alias for `Bag`). The class name becomes the **accessor name** used to read settings directly from the node instance.

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import Settings, setting, Color

@node(label="My Node")
class MyNode(BaseNode):

    class filter(Settings):
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

The `@node` decorator scans the class body for all `Settings` (= `Bag`) subclasses, assigns a `_field_key` to each `setting()` descriptor (derived from the node's `registry_key`), and binds each bag instance directly on the node object at construction time.

### Per-Node Resolution Chain (Extended Mode)

When a `GlobalSettingsRegistry` is injected, each `setting()` field with a `_field_key` set goes through the full resolution chain:

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
3. Local value in this bag instance?                              → return it
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

Bags without a registry (simple mode) skip steps 1–2 and 4–5 — they read directly from the local store.

---

## Descriptor Parameters

| Parameter | Behaviour |
| --------- | --------- |
| `setting(default)` | Local node setting — stored in graph, shown in panel |
| `setting(mirrors=GlobalSettings.field)` | Inherits global value; override shown with reset affordance |
| `setting(mirrors=..., read_only=True)` | Read-only global cache — invisible in panel, never stored |
| `setting(..., on_change='method_name')` | Fires `method(value, field_name)` on change |

---

## Accessing Settings in Node Code

Access is direct via the **bag name** (inner class name), then the **field name**:

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

The outer key is the **bag name**. The inner dict maps attr name → locally set value. Fields at their default are omitted.

---

## Next Steps

- **[Node Development Guide](02-node-development.md)** — Defining and using settings in nodes
- **[Library Development Guide](03-library-development.md)** — Creating `LibrarySettings` for your library
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
