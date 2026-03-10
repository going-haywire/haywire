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

Nodes declare settings as an inner class that inherits from `NodeSettings`. The class name becomes the **accessor name** used to reach the settings from `self.settings`.

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color

@node(label="My Node")
class MyNode(BaseNode):

    class node(NodeSettings):
        # Local setting — stored in graph, shown in properties panel
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')

        # Shadow — inherits global default; per-node override shown with reset affordance
        bg_color: Color = shadow(NodeUISettings.bg_color)

        # Watch — read-only cache of a global; invisible in panel, never serialized
        verbose: bool = watch(DebugSettings.verbose_logging)

    def worker(self, context):
        result = value * self.settings.node.threshold   # accessor = inner class name
        self.out('result', result)
```

The `@node` decorator scans the class body for all `_SettingsSchema` subclasses, assigns a namespace to each `NodeSettings` subclass (derived from the node's `registry_key` by replacing `:` with `.`), and sets `_field_key` on each descriptor.

A library settings class can also be imported and assigned directly — the accessor name is then the variable name chosen by the developer:

```python
from haybale_imagelib.settings import ImageLibSettings

@node(label="Image Filter")
class ImageFilterNode(BaseNode):

    image = ImageLibSettings           # accessor: 'image'
    class node(NodeSettings):     # accessor: 'node'
        threshold: float = setting(0.5)

    def worker(self, context):
        quality = self.settings.image.jpeg_quality   # from ImageLibSettings
        threshold = self.settings.node.threshold   # own field
```

### NodeInstanceSettings — Framework-Provided Fields

Every node automatically receives a set of framework-level instance settings via `NodeInstanceSettings` (namespace `'node'`). The `@node` decorator always injects it under the reserved accessor `'_node'`.

| Field | Full key | Type | Default | Purpose |
| ----- | -------- | ---- | ------- | ------- |
| `skin` | `node.skin` | str or None | `None` | Skin used to render this node |
| `muted` | `node.muted` | bool | `False` | Skip during execution |
| `collapsed` | `node.collapsed` | bool | `False` | Collapse to header only |
| `condensed` | `node.condensed` | bool | `False` | Condensed view |
| `pinned` | `node.pinned` | bool | `False` | Prevent auto-layout movement |
| `color_override` | `node.color_override` | Color or None | `None` | Per-node background colour |
| `comment` | `node.comment` | str | `''` | Comment text |
| `show_comment` | `node.show_comment` | bool | `False` | Show comment bubble |

Access via the reserved `_node` accessor:

```python
self.settings._node.muted           # → bool
self.settings._node.skin = 'my_lib:skin:MyCustomSkin'
self.settings._node.color_override  # → str | None
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
class node(NodeSettings):
    threshold:   float = setting(0.5, min=0.0, max=1.0, label='Threshold')
    algorithm:   str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
    bg_color:    Color = setting('#ffffff', label='Background Color', widget='color')
    verbose:     bool  = setting(False, label='Verbose Output')
    on_change_cb: float = setting(1.0, label='Scale', on_change='hb_on_scale_change')
```

Widget is inferred from type: `bool` → toggle, `int`/`float` with range → slider, `Color` → color picker, `str` with `choices` → dropdown, plain `str` → text input.

### `shadow()` — Mirror a global setting

```python
class node(NodeSettings):
    # Inherits global value by default; user can override per-node
    bg_color: Color = shadow(NodeUISettings.bg_color)
```

`shadow(SomeGlobalSettings.field)` takes the descriptor at class-access time (returns the descriptor object itself) and stores its `_field_key` as a string. The `_label`, `_default`, and widget metadata are inherited from the global descriptor.

### `watch()` — Read-only cached global reference

```python
class node(NodeSettings):
    # Invisible in panel; cache invalidated automatically on global change
    verbose: bool = watch(DebugSettings.verbose_logging)
```

Useful for settings that control node behavior but shouldn't be per-node configurable.

---

## Accessing Settings in Node Code

Access is via the **accessor name** (inner class name or direct assignment name), then the **short attr name**:

```python
def worker(self, context, value: float):
    s = self.settings.node   # accessor = inner class name
    if s.verbose:
        context.log(f"Processing: {value}")

    result = value * s.threshold
    self.out('result', result)
```

---

## Serialization

Only locally-overridden schema values are serialized with the node. Global values are **not** stored in the graph.

```json
{
  "node_id": "abc123",
  "settings": {
    "Settings": {
      "schema_values": { "threshold": 0.8, "bg_color": "#ff0000" }
    },
    "_node": {
      "schema_values": {}
    }
  },
  "store": { "execution_count": 42 }
}
```

The outer key is the **accessor name**. `schema_values` maps attr name → locally set value. Fields at their default (resolved from global or descriptor default) are omitted.

---

## Next Steps

- **[Node Development Guide](02-node-development.md)** — Defining and using settings in nodes
- **[Library Development Guide](03-library-development.md)** — Creating `LibrarySettings` for your library
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
