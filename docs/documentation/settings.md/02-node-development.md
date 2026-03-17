# Node Development Guide

This guide covers how to use `self.cache`, `self.store`, and `self.settings` when developing Haywire nodes.

---

## Quick Start

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color
from haywire.core.settings.builtins.debug import DebugSettings
from haywire.core.settings.builtins.ui_node import NodeUISettings

@node(label="Quick Start")
class QuickStartNode(BaseNode):

    class node(NodeSettings):
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        bg_color:  Color = shadow(NodeUISettings.bg_color)
        verbose:   bool  = watch(DebugSettings.verbose_logging)

    def init(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        self.cache.memo = {}
        self.store.call_count = 0

    def worker(self, context, value: float):
        self.store.call_count += 1
        result = value * self.settings.node.threshold   # accessor = inner class name
        self.cache.memo[value] = result
        self.out('result', result)
```

---

## Declaring Settings: the Inner Settings Class

Node settings are declared as an inner class that inherits from `NodeSettings`. The class name becomes the **accessor name** used to reach the settings from `self.settings`.

```python
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color, Icon

@node(label="My Node")
class MyNode(BaseNode):

    class node(NodeSettings):
        # Local setting — stored in graph when set, shown in properties panel
        threshold:  float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        algorithm:  str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
        bg_color:   Color = setting('#ffffff', label='Background Color')
        verbose:    bool  = setting(False, label='Verbose Output')
        icon:       Icon  = setting('star', label='Icon')

        # Shadow — inherits global default; per-node override shown with reset affordance
        node_bg:    Color = shadow(NodeUISettings.bg_color)

        # Watch — read-only cache of a global; invisible in panel, never serialized
        debug_mode: bool  = watch(DebugSettings.verbose_logging)
```

Access in worker code via the inner class name:

```python
def worker(self, context, value: float):
    threshold = self.settings.node.threshold
    verbose   = self.settings.node.debug_mode
```

### Namespace Derivation

The namespace is derived automatically from the node's `registry_key` by replacing `:` with `.`:

```text
registry_key: haybale_core:node:transform
  → namespace: haybale_core.node.transform
  → full keys: haybale_core.node.transform.threshold, etc.
```

You can override it explicitly:

```python
class node(NodeSettings, namespace='my_lib.filter'):
    threshold: float = setting(0.5)
```

---

## Multiple Settings Schemas

A node can declare settings from multiple schemas. Each schema gets its own **accessor name** — the variable name in the class body.

### Inner Class Form

```python
@node(registry_id='image_filter')
class ImageFilterNode(BaseNode):

    class node(NodeSettings):          # accessor: 'Settings'
        threshold: float = setting(0.5)

    def worker(self, context, img):
        t = self.settings.node.threshold
```

### Direct Assignment Form

Import a pre-defined schema class and assign it directly. The accessor name is the variable name you choose — the schema's own namespace and full keys are unchanged.

```python
from haybale_imagelib.settings import ImageLibSettings

@node(registry_id='image_filter')
class ImageFilterNode(BaseNode):

    image = ImageLibSettings               # accessor: 'image'

    class node(NodeSettings):          # accessor: 'Settings'
        threshold: float = setting(0.5)

    def worker(self, context, img):
        quality = self.settings.image.jpeg_quality   # from ImageLibSettings
        t       = self.settings.node.threshold   # own field
```

**Rules:**

- The accessor name is the variable name in the class body (inner class name or direct assignment name)
- `LibrarySettings` schemas already have their namespace and full keys set by `@library_settings` — no override happens
- `_node` is a **reserved** accessor name (see below). Using it raises `ValueError` at decoration time

---

## The `_node` Accessor — NodeInstanceSettings

`self.settings._node` is always injected by the `@node` decorator. It holds the framework-managed `NodeInstanceSettings` fields (`muted`, `skin`, `collapsed`, etc.).

```python
# Node developers can read these (advanced use):
is_muted   = self.settings._node.muted
skin_name  = self.settings._node.skin
collapsed  = self.settings._node.collapsed
```

> **Reserved name:** using `_node` as the name of your own inner class or direct assignment raises `ValueError` at decoration time.

---

## Descriptor Types

### `setting()` — Local node setting

Stored in the graph when locally set. Shown in properties panel.

```python
class node(NodeSettings):
    threshold:   float = setting(0.5, min=0.0, max=1.0, label='Threshold')
    algorithm:   str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
    bg_color:    Color = setting('#ffffff', label='Background Color')
    verbose:     bool  = setting(False, label='Verbose Output')
    scale:       float = setting(1.0, label='Scale', on_change='hb_on_scale_change')
```

Widget is inferred from type unless overridden:

- `bool` → toggle
- `int`/`float` with `min`/`max` → slider
- `Color` → color picker
- `Icon` → icon picker
- `str` with `choices` → dropdown
- plain `str` → text input

#### The `choices` parameter

`choices` accepts three forms:

```python
# Static list — value shown and stored as-is
algorithm: str = setting('fast', choices=['fast', 'accurate'])

# Dict {stored_value: display_label} — label shown, value stored
algorithm: str = setting('fast', choices={'fast': 'Fast Mode', 'accurate': 'High Accuracy'})

# Callable — evaluated at render time (use for dynamic lists from a registry)
theme: str = setting('', choices=lambda: get_theme_registry().list_workbench_keys())

# Callable returning a dict
theme: str = setting('', choices=lambda: {k: lbl for k, lbl in get_theme_registry().list_workbench_themes()})
```

The callable form is evaluated fresh on every panel render, so entries added by plugins after startup appear automatically. Use it whenever the valid options come from a registry or other runtime source.

### `shadow()` — Mirror a global setting

Inherits the global value by default. User can override per-node; shown with a reset affordance in the panel. Target must be a `LibrarySettings` or `GlobalSettings` field.

```python
from haywire.core.settings.builtins.ui_node import NodeUISettings

class node(NodeSettings):
    bg_color: Color = shadow(NodeUISettings.bg_color)
```

### `watch()` — Read-only cached global reference

Invisible in panel. Never stored. Cache is invalidated automatically when the global value changes.

```python
from haywire.core.settings.builtins.debug import DebugSettings

class node(NodeSettings):
    verbose: bool = watch(DebugSettings.verbose_logging)
```

---

## Accessing Settings in Node Code

Access is always via the **accessor name** (inner class name or direct assignment name), then the **short attr name** — never the full key.

```python
def worker(self, context, value: float):
    # Dot notation (preferred)
    if self.settings.node.verbose:
        context.log(f"Processing: {value}")

    result = value * self.settings.node.threshold
    self.out('result', result)
```

Sub-holder methods:

```python
# Set a local override
self.settings.node.threshold = 0.8
self.settings.node.set('threshold', 0.8)

# Reset to global/default
self.settings.node.reset('threshold')

# Check if locally overridden
is_local = self.settings.node.is_locally_set('threshold')

# Introspect for UI
info = self.settings.node.get_info('threshold')
print(info.source, info.is_overridden, info.value)
```

---

## `on_change` Callbacks

Triggered when a setting value changes (local set or global cache invalidation):

```python
class node(NodeSettings):
    scale: float = setting(1.0, label='Scale', on_change='hb_on_scale_change')

def hb_on_scale_change(self, value: float, field: str = '') -> None:
    # value: new resolved value
    # field: attr name (e.g. 'scale')
    self.cache.scale_cached = value
```

---

## The Cache Container

`self.cache` is a `SimpleNamespace`-like container for **transient** runtime data.

- Not serialized — lost on save/load
- Not GUI-visible
- Any Python object

```python
def init(self):
    self.cache.memo = {}
    self.cache.last_result = None

def worker(self, context, x: float):
    if x in self.cache.memo:
        self.out('result', self.cache.memo[x])
        return
    result = self._compute(x)
    self.cache.memo[x] = result
    self.out('result', result)
```

---

## The Store Container

`self.store` is a **persistent** internal state container.

- Serialized — survives save/load
- Not GUI-visible
- JSON-serializable types only

```python
def init(self):
    self.store.execution_count = 0
    self.store.running_sum = 0.0
    self.store.history = []

def worker(self, context, value: float):
    self.store.execution_count += 1
    self.store.running_sum += value
    self.store.history.append(value)
    self.out('average', self.store.running_sum / self.store.execution_count)
```

---

## Serialization

Only locally-overridden schema values are serialized. Global defaults and `watch()` values are never stored.

```json
{
  "settings": {
    "Settings": {
      "schema_values": {
        "threshold": 0.8,
        "bg_color": "#ff0000"
      }
    },
    "_node": {
      "schema_values": {}
    }
  },
  "store": { "execution_count": 42 }
}
```

---

## Complete Example

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color
from haywire.core.settings.builtins.ui_node import NodeUISettings
from haywire.core.settings.builtins.debug import DebugSettings

@node(label="Signal Processor", is_stateful=True)
class SignalProcessorNode(BaseNode):

    class node(NodeSettings):
        filter_strength: float = setting(0.5, min=0.0, max=1.0, label='Filter Strength',
                                         on_change='hb_on_filter_change')
        filter_type:     str   = setting('exponential',
                                         choices=['none', 'exponential', 'moving_average'],
                                         label='Filter Type')
        window_size:     int   = setting(10, min=2, max=100, label='Window Size')
        bg_color:        Color = shadow(NodeUISettings.bg_color)
        verbose:         bool  = watch(DebugSettings.verbose_logging)

    def init(self):
        self.add(FLOAT.as_inlet('signal'))
        self.add(FLOAT.as_outlet('filtered'))

        self.cache.last_filtered = 0.0
        self.cache.history_buffer = []

        self.store.sample_count = 0
        self.store.running_sum = 0.0

    def hb_on_filter_change(self, value: float, field: str = '') -> None:
        self.cache.last_filtered = 0.0  # reset filter state on change

    def worker(self, context, signal: float):
        s = self.settings.node
        if s.verbose:
            context.log(f"Signal: {signal}")

        filtered = self._apply_filter(signal)
        self.store.sample_count += 1
        self.store.running_sum += signal
        self.out('filtered', filtered)

    def _apply_filter(self, signal: float) -> float:
        s = self.settings.node
        if s.filter_type == 'none':
            return signal
        elif s.filter_type == 'exponential':
            alpha = s.filter_strength
            result = alpha * self.cache.last_filtered + (1 - alpha) * signal
            self.cache.last_filtered = result
            return result
        elif s.filter_type == 'moving_average':
            buf = self.cache.history_buffer
            buf.append(signal)
            w = s.window_size
            if len(buf) > w:
                self.cache.history_buffer = buf[-w:]
            return sum(self.cache.history_buffer) / len(self.cache.history_buffer)
        return signal
```

---

## Next Steps

- **[Library Development Guide](03-library-development.md)** — Creating `LibrarySettings` for your library
- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
