# Settings System Overview

Haywire's settings system manages configuration at three levels: global/workspace application defaults, per-node instance overrides, and transient runtime data.

## The Three Containers

Every node instance exposes three containers:

| Container | Serialized | GUI-visible | Hierarchical |
|-----------|-----------|-------------|--------------|
| `self.cache` | No | No | No |
| `self.store` | Yes | No | No |
| `self.settings` | Yes (local overrides only) | Yes | Yes |

**Use `self.cache`** for transient computation data (lookup tables, buffers, memoization).
**Use `self.store`** for persistent internal state users don't see (counters, accumulators, state machines).
**Use `self.settings`** for anything users should be able to see and configure.

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
├── Library LibrarySettings schemas (discovered via @library_settings decorator)
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

### Node Settings Schema

Nodes declare their settings as an inner `Settings` class:

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color

@node(label="My Node")
class MyNode(BaseNode):

    class Settings(NodeSettings):
        # Local setting — stored in graph, shown in properties panel
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')

        # Shadow — inherits global default; per-node override shown with reset affordance
        bg_color: Color = shadow(NodeUISettings.bg_color)

        # Watch — read-only cache of a global; invisible in panel, never serialized
        verbose: bool = watch(DebugSettings.verbose_logging)
```

`BaseNode.__init_subclass__` detects the inner `Settings` class, derives a namespace from the node class name (`my_lib.my` for `MyNode`), and sets `_full_key` on each descriptor (`my_lib.my.threshold`, etc.).

### NodeInstanceSettings — Framework-Provided Fields

Every node automatically receives a set of framework-level instance settings via `NodeInstanceSettings` (namespace `'node'`). These are injected as an *extra schema* alongside the node's own `Settings` class and participate in the full resolution chain.

| Field | Full key | Type | Default | Purpose |
|-------|----------|------|---------|---------|
| `skin` | `node.skin` | str or None | `None` | Skin used to render this node |
| `muted` | `node.muted` | bool | `False` | Skip during execution |
| `collapsed` | `node.collapsed` | bool | `False` | Collapse to header only |
| `condensed` | `node.condensed` | bool | `False` | Condensed view |
| `pinned` | `node.pinned` | bool | `False` | Prevent auto-layout movement |
| `color_override` | `node.color_override` | Color or None | `None` | Per-node background colour |
| `comment` | `node.comment` | str | `''` | Comment text |
| `show_comment` | `node.show_comment` | bool | `False` | Show comment bubble |

Access is via the short attr name (same as any other schema field):

```python
# In node code
self.settings.skin = 'my_lib:skin:MyCustomSkin'
self.settings.muted        # → bool
self.settings.color_override  # → str | None

# Dict-style via full key also works
self.settings['node.muted']
```

Because they are proper schema fields, global defaults can be set in TOML:

```toml
# ~/.haywire/settings.toml
[node]
collapsed = true          # start all nodes collapsed by default
```

### Per-Node Resolution Chain

Each node instance has a `ResolutionChain` that resolves values in priority order:

```
self.settings.threshold
        │
        ▼
1. Global tier OVERRIDE for 'my_lib.my.threshold'?    → return it (admin policy, hand-edited)
        │ No
        ▼
2. Workspace tier OVERRIDE for 'my_lib.my.threshold'? → return it (workspace-wide force)
        │ No
        ▼
3. Local value in this instance?                      → return it (per-node override)
        │ No
        ▼
4. Workspace tier SET for 'my_lib.my.threshold'?      → return it (set via UI, saved to workspace TOML)
        │ No
        ▼
5. Global tier SET for 'my_lib.my.threshold'?         → return it (user global default)
        │ No
        ▼
6. Descriptor _default                                → return it
```

---

## Descriptor Types

| Descriptor | Panel visible | Stored in graph | Read-only |
|------------|--------------|-----------------|-----------|
| `setting()` | Yes | Yes, when locally set | No |
| `shadow()` | Yes, with reset affordance | Yes, when locally overridden | No |
| `watch()` | No | Never | Yes |

### `setting()` — Local node setting

```python
class Settings(NodeSettings):
    threshold:   float = setting(0.5, min=0.0, max=1.0, label='Threshold')
    algorithm:   str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
    bg_color:    Color = setting('#ffffff', label='Background Color', widget='color')
    verbose:     bool  = setting(False, label='Verbose Output')
    on_change_cb: float = setting(1.0, label='Scale', on_change='hb_on_scale_change')
```

Widget is inferred from type: `bool` → toggle, `int`/`float` with range → slider, `Color` → color picker, `str` with `choices` → dropdown, plain `str` → text input.

### `shadow()` — Mirror a global setting

```python
class Settings(NodeSettings):
    # Inherits global value by default; user can override per-node
    bg_color: Color = shadow(NodeUISettings.bg_color)
```

`shadow(SomeGlobalSettings.field)` takes the descriptor at class-access time (returns the descriptor object itself) and stores its `_full_key` as a string. The `_label`, `_default`, and widget metadata are inherited from the global descriptor.

### `watch()` — Read-only cached global reference

```python
class Settings(NodeSettings):
    # Invisible in panel; cache invalidated automatically on global change
    verbose: bool = watch(DebugSettings.verbose_logging)
```

Useful for settings that control node behavior but shouldn't be per-node configurable.

---

## Accessing Settings in Node Code

```python
def worker(self, context, value: float):
    # Dot-notation access (preferred)
    if self.settings.verbose:
        context.log(f"Processing: {value}")

    result = value * self.settings.threshold
    self.out('result', result)
```

Access is always by the **short attr name** (`threshold`, `bg_color`), not the full key.

---

## Serialization

Only locally-overridden schema values are serialized with the node. Global values are **not** stored in the graph.

```json
{
  "node_id": "abc123",
  "settings": {
    "schema_values": {
      "threshold": 0.8,
      "bg_color": "#ff0000"
    }
  },
  "store": { "execution_count": 42 }
}
```

`schema_values` maps attr name → locally set value. Fields still at their default (resolved from global or descriptor default) are omitted.

---

## Next Steps

- **[Node Development Guide](02-node-development.md)** — Defining and using settings in nodes
- **[Library Development Guide](03-library-development.md)** — Creating `LibrarySettings` for your library
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
