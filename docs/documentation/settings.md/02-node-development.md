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

    class Settings(NodeSettings):
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        bg_color:  Color = shadow(NodeUISettings.bg_color)
        verbose:   bool  = watch(DebugSettings.verbose_logging)

    def initialize(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        self.cache.memo = {}
        self.store.call_count = 0

    def worker(self, context, value: float):
        self.store.call_count += 1
        result = value * self.settings.threshold
        self.cache.memo[value] = result
        self.out('result', result)
```

---

## Declaring Settings: the Inner `Settings` Class

Node settings are declared as an inner `class Settings(NodeSettings):`. The `@node` decorator detects it and wires up full keys automatically.

```python
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color, Icon

class MyNode(BaseNode):

    class Settings(NodeSettings):
        # Local setting — stored in graph, shown in properties panel
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

### Namespace Derivation

The namespace is derived automatically from the node's `registry_key` by replacing `:` with `.`:

```
registry_key: haybale_core:node:transform
  → namespace: haybale_core.node.transform
  → full keys: haybale_core.node.transform.threshold, etc.
```

You can override it explicitly:

```python
class Settings(NodeSettings, namespace='my_lib.filter'):
    threshold: float = setting(0.5)
```

---

## Extra Schemas

A node can pull in additional settings from a pre-defined schema class using `extra_schemas`. This is useful when a library provides a shared set of settings that multiple nodes should expose.

```python
from haybale_customlib.settings import LibVisualSettings

@node(registry_id='transform')
class TransformNode(BaseNode):

    class Settings(NodeSettings, extra_schemas=(LibVisualSettings,)):
        threshold: float = setting(0.5, label='Threshold')
```

All fields from `LibVisualSettings` are merged into the flat `self.settings` namespace alongside `threshold`:

```python
def worker(self, context, value: float):
    color  = self.settings.bg_color    # from LibVisualSettings
    factor = self.settings.threshold   # own field
```

**Rules:**

- Extra schemas are merged in before the primary `Settings` (extras first, primary last)
- Access is flat — no sub-namespace; all fields from all schemas are at the same level
- A `ValueError` is raised at node instantiation if any field name collides between schemas (including the framework-injected `NodeInstanceSettings`)
- The framework's `NodeInstanceSettings` (`muted`, `skin`, `collapsed`, …) is always injected automatically and does not need to be listed in `extra_schemas`

---

## Descriptor Types

### `setting()` — Local node setting

Stored in the graph when locally set. Shown in properties panel.

```python
class Settings(NodeSettings):
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

### `shadow()` — Mirror a global setting

Inherits the global value by default. User can override per-node; shown with a reset affordance in the panel. Target must be a `LibrarySettings` or `GlobalSettings` field.

```python
from haywire.core.settings.builtins.ui_node import NodeUISettings

class Settings(NodeSettings):
    bg_color: Color = shadow(NodeUISettings.bg_color)
```

### `watch()` — Read-only cached global reference

Invisible in panel. Never stored. Cache is invalidated automatically when the global value changes.

```python
from haywire.core.settings.builtins.debug import DebugSettings

class Settings(NodeSettings):
    verbose: bool = watch(DebugSettings.verbose_logging)
```

---

## Accessing Settings in Node Code

Access is always by the **short attr name** — never the full key.

```python
def worker(self, context, value: float):
    # Dot notation (preferred)
    if self.settings.verbose:
        context.log(f"Processing: {value}")

    result = value * self.settings.threshold
    self.out('result', result)
```

Dict-style access also works (by attr name or full key):

```python
color = self.settings['bg_color']
color = self.settings['haybale_core.my_node.bg_color']  # by full key
```

---

## `on_change` Callbacks

Triggered when a setting value changes (local set or global cache invalidation):

```python
class Settings(NodeSettings):
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
def initialize(self):
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
def initialize(self):
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
    "schema_values": {
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
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color
from haywire.core.settings.builtins.ui_node import NodeUISettings
from haywire.core.settings.builtins.debug import DebugSettings

@node(label="Signal Processor", is_stateful=True, is_pure=False)
class SignalProcessorNode(BaseNode):

    class Settings(NodeSettings):
        filter_strength: float = setting(0.5, min=0.0, max=1.0, label='Filter Strength',
                                         on_change='hb_on_filter_change')
        filter_type:     str   = setting('exponential',
                                         choices=['none', 'exponential', 'moving_average'],
                                         label='Filter Type')
        window_size:     int   = setting(10, min=2, max=100, label='Window Size')
        bg_color:        Color = shadow(NodeUISettings.bg_color)
        verbose:         bool  = watch(DebugSettings.verbose_logging)

    def initialize(self):
        self.add(FLOAT.as_inlet('signal'))
        self.add(FLOAT.as_outlet('filtered'))

        self.cache.last_filtered = 0.0
        self.cache.history_buffer = []

        self.store.sample_count = 0
        self.store.running_sum = 0.0

    def hb_on_filter_change(self, value: float, field: str = '') -> None:
        self.cache.last_filtered = 0.0  # reset filter state on change

    def worker(self, context, signal: float):
        if self.settings.verbose:
            context.log(f"Signal: {signal}")

        filtered = self._apply_filter(signal)
        self.store.sample_count += 1
        self.store.running_sum += signal
        self.out('filtered', filtered)

    def _apply_filter(self, signal: float) -> float:
        ft = self.settings.filter_type
        if ft == 'none':
            return signal
        elif ft == 'exponential':
            alpha = self.settings.filter_strength
            result = alpha * self.cache.last_filtered + (1 - alpha) * signal
            self.cache.last_filtered = result
            return result
        elif ft == 'moving_average':
            buf = self.cache.history_buffer
            buf.append(signal)
            w = self.settings.window_size
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
