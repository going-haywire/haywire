# Node Development Guide

This guide covers how to use `self.cache`, `self.store`, and node settings when developing Haywire nodes.

---

## Quick Start

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, Color
from haywire.core.settings.builtins.debug import DebugSettings
from haywire.core.settings.builtins.ui_node import NodeUISettings

@node(label="Quick Start")
class QuickStartNode(BaseNode):

    class filter(NodeSettings):
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        bg_color:  Color = setting(mirrors=NodeUISettings.bg_color)
        verbose:   bool  = setting(mirrors=DebugSettings.verbose_logging, read_only=True)

    def init(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        self.cache.memo = {}
        self.store.call_count = 0

    def worker(self, context, value: float):
        self.store.call_count += 1
        result = value * self.filter.threshold   # direct settings access
        self.cache.memo[value] = result
        self.out('result', result)
```

---

## Declaring Settings: the Inner NodeSettings Class

Node settings are declared as an inner class that inherits from `NodeSettings`. The class name becomes the **accessor name** — the attribute you use to access settings directly on the node instance.

```python
from haywire.core.settings import NodeSettings, setting, Color, Icon

@node(label="My Node")
class MyNode(BaseNode):

    class filter(NodeSettings):
        # Local setting — stored in graph when set, shown in properties panel
        threshold:  float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        algorithm:  str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
        bg_color:   Color = setting('#ffffff', label='Background Color')
        verbose:    bool  = setting(False, label='Verbose Output')
        icon:       Icon  = setting('star', label='Icon')

        # mirrors= — inherits global default; per-node override shown with reset affordance
        node_bg:    Color = setting(mirrors=NodeUISettings.bg_color)

        # mirrors= + read_only= — read-only global cache; invisible in panel, never stored
        debug_mode: bool  = setting(mirrors=DebugSettings.verbose_logging, read_only=True)
```

Access in worker code directly via the accessor name:

```python
def worker(self, context, value: float):
    threshold = self.filter.threshold
    verbose   = self.filter.debug_mode
```

### Namespace and `_field_key`

The `@node` decorator automatically derives a namespace from the node's `registry_key` by replacing `:` with `.`:

```text
registry_key: haybale_core:node:transform
  → namespace: haybale_core.node.transform
  → full keys: haybale_core.node.transform.filter.threshold, etc.
```

This is the key used for TOML resolution and global registry lookups. You never need to write it yourself.

---

## Multiple Settings Groups

A node can declare any number of `NodeSettings` inner classes. Each gets its own accessor name:

```python
@node(registry_id='image_filter')
class ImageFilterNode(BaseNode):

    class filter(NodeSettings):
        threshold: float = setting(0.5)

    class output(NodeSettings):
        jpeg_quality: int = setting(85, min=1, max=100, label='JPEG Quality')

    def worker(self, context, img):
        t = self.filter.threshold
        q = self.output.jpeg_quality
```

**Conflict check:** the accessor name must not shadow an existing `BaseNode` method or attribute. If it does, `@node` raises `ValueError` at class-definition time.

---

## `setting()` Parameters

```python
class filter(NodeSettings):
    threshold:   float = setting(0.5, min=0.0, max=1.0, label='Threshold')
    algorithm:   str   = setting('fast', choices=['fast', 'accurate'], label='Algorithm')
    color:       Color = setting('#ffffff', label='Background')
    verbose:     bool  = setting(False, on_change='hb_on_verbose_change')
```

Widget is inferred from type unless overridden:

- `bool` → toggle
- `int`/`float` with `min`/`max` → slider
- `Color` → color picker
- `Icon` → icon picker
- `str` with `choices` → dropdown
- plain `str` → text input

### The `choices` parameter

`choices` accepts three forms:

```python
# Static list — value shown and stored as-is
algorithm: str = setting('fast', choices=['fast', 'accurate'])

# Dict {stored_value: display_label} — label shown, value stored
algorithm: str = setting('fast', choices={'fast': 'Fast Mode', 'accurate': 'High Accuracy'})

# Callable — evaluated at render time (use for dynamic lists from a registry)
theme: str = setting('', choices=lambda: get_theme_registry().list_workbench_keys())
```

The callable form is evaluated fresh on every panel render, so entries added by plugins after startup appear automatically.

### The `mirrors=` parameter

```python
from haywire.core.settings.builtins.ui_node import NodeUISettings

class filter(NodeSettings):
    # Inherits global value by default; user can override per-node
    bg_color: Color = setting(mirrors=NodeUISettings.bg_color)
```

`mirrors=SomeGlobalSettings.field` stores the target descriptor's `_field_key` and inherits its `_label`, `_default`, and widget metadata. The field resolves through the global registry.

### The `read_only=` parameter

```python
from haywire.core.settings.builtins.debug import DebugSettings

class filter(NodeSettings):
    # Invisible in panel; never stored; cache invalidated on global change
    verbose: bool = setting(mirrors=DebugSettings.verbose_logging, read_only=True)
```

`read_only=True` prevents per-instance writes. Attempting `self.filter.verbose = True` raises `AttributeError`.

---

## `on_change` Callbacks

Triggered when a setting value changes (local set, reset, or global cache invalidation via `mirrors=`):

```python
class filter(NodeSettings):
    scale: float = setting(1.0, label='Scale', on_change='hb_on_scale_change')

def hb_on_scale_change(self, value: float, field: str = '') -> None:
    # value: new resolved value
    # field: attr name (e.g. 'scale')
    self.cache.scale_cached = value
```

---

## Settings Instance Methods

```python
# Reset a field to default (removes local override)
self.filter.reset('threshold')

# Reset all fields
self.filter.reset_all()

# Check if a field has a local override
is_local = self.filter.is_locally_set('threshold')

# Subscribe a callback to any change on this settings instance
self.filter.subscribe(lambda name, value, old: ...)

# Serialize / restore
data = self.filter.to_dict()      # only locally-set non-default values
self.filter.from_dict(data)       # silent (no callbacks); use silent=False to fire them
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

Only locally-overridden values are serialized. `read_only` fields and fields at their default are never stored.

```json
{
  "settings": {
    "filter": {
      "threshold": 0.8,
      "bg_color": "#ff0000"
    }
  },
  "store": { "execution_count": 42 }
}
```

---

## Complete Example

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, Color
from haywire.core.settings.builtins.ui_node import NodeUISettings
from haywire.core.settings.builtins.debug import DebugSettings

@node(label="Signal Processor", is_stateful=True)
class SignalProcessorNode(BaseNode):

    class filter(NodeSettings):
        filter_strength: float = setting(0.5, min=0.0, max=1.0, label='Filter Strength',
                                         on_change='hb_on_filter_change')
        filter_type:     str   = setting('exponential',
                                         choices=['none', 'exponential', 'moving_average'],
                                         label='Filter Type')
        window_size:     int   = setting(10, min=2, max=100, label='Window Size')
        bg_color:        Color = setting(mirrors=NodeUISettings.bg_color)
        verbose:         bool  = setting(mirrors=DebugSettings.verbose_logging, read_only=True)

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
        f = self.filter
        if f.verbose:
            context.log(f"Signal: {signal}")

        filtered = self._apply_filter(signal)
        self.store.sample_count += 1
        self.store.running_sum += signal
        self.out('filtered', filtered)

    def _apply_filter(self, signal: float) -> float:
        f = self.filter
        if f.filter_type == 'none':
            return signal
        elif f.filter_type == 'exponential':
            alpha = f.filter_strength
            result = alpha * self.cache.last_filtered + (1 - alpha) * signal
            self.cache.last_filtered = result
            return result
        elif f.filter_type == 'moving_average':
            buf = self.cache.history_buffer
            buf.append(signal)
            w = f.window_size
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
