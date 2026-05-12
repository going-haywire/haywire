---
status: draft
doc_template: canonical-example
scope: Authoring settings — NodeSettings, LibrarySettings, the setting() / shadow() / watch() descriptors, on_change, panel integration
see-also:
  - ../../architecture/settings/settings-arch.md
  - ../nodes/node-canon.md
  - ../states/state-canon.md
  - ../../reference/glossary.md
---

# Setting — Canonical Example

## 1. What it solves

A **setting** is a configurable value that a user (or a TOML file, or a panel) can change at runtime. As an author, you declare settings in three places depending on scope:

- **NodeSettings** — per-node-instance settings; declared as an inner class on a `@node` class. Stored in the graph (only when locally overridden), shown in the property panel, accessible via `self.<accessor_name>.<field>` from worker code.
- **LibrarySettings** — library-wide defaults that nodes can mirror; declared as a `@settings`-decorated class in your library. Backed by `~/.haywire/settings.toml` and `<workspace>/.haywire/settings.toml`.
- **Mirror descriptors** (`shadow()` / `watch()`) — a node setting that *references* a global setting. `shadow()` is writable (per-node override allowed); `watch()` is read-only (invisible in panel, never stored).

Together these three replace ad-hoc instance attributes, manual TOML parsing, and per-node-config plumbing. One declarative API, automatic panel rendering, hot-reload aware.

The framework-level `FrameworkSettings` class (used for app-internal settings like `ExecutionSettings`, `DebugSettings`) is documented in [architecture/settings](../../architecture/settings/settings-arch.md). Library and node authors only need NodeSettings and LibrarySettings.

## 2. How it fits

```text
Author declares                Framework wires up               Worker reads
────────────────               ──────────────────                ────────────
class filter(NodeSettings):    @node decorator scans inner      self.filter.threshold
   threshold = setting[float]    classes, sets _setting_key,        ↓ resolution chain
   bg = shadow(NodeUI.bg_color)  binds settings instance to        (see architecture)
                                 self.<accessor_name>            → unwrapped value

@settings(namespace='my_lib')  BaseRegistry hot-reload picks    self.api.url, etc.
class MyLibSettings(            up the class; sets cls._registry   - via shadow/watch
   LibrarySettings):                                                from a NodeSettings
   url = setting[str](...)                                        - via direct instantiation
                                                                    from non-node code
```

Every node instance also exposes two more containers, alongside settings:

| Container | Serialized | GUI-visible | Purpose |
|---|---|---|---|
| `self.cache` | No | No | Transient runtime data (lookup tables, buffers, memoization) |
| `self.store` | Yes | No | Persistent internal state users don't see (counters, accumulators) |
| `self.<settings_name>` | Yes (local overrides only) | Yes | Anything users should see and configure |

Use `cache` for "lost on restart, fine"; `store` for "must survive saves, hidden from UI"; settings for "user-facing, configurable, declarative."

**Boundaries.** What a setting *resolves to* (the six-step resolution chain, the SettingsRegistry, three-tier TOML, FrameworkSettings) lives in [architecture/settings](../../architecture/settings/settings-arch.md). Live application/session-lifecycle state owned by editors and panels (the `@state` decorator) lives in [components/states](../states/state-canon.md). The properties-panel rendering pipeline that reads your settings classes lives in [architecture/studio/canvas](../../architecture/studio/canvas/canvas-arch.md) but the rendering rules below are author-facing.

## 3. Important concepts

**The three Settings classes.** All three inherit from `Settings`. Pick by scope:

| Class | Where you declare it | Persisted to | Instances |
|---|---|---|---|
| `NodeSettings` | Inner class on a `@node` class | Graph file (only overrides) | One per node, owned by the node |
| `LibrarySettings` | `@settings`-decorated class in your library | Workspace / global TOML | Construct as many as you need — they share state via the registry |
| `FrameworkSettings` | Framework-internal only | Workspace / global TOML | Construct as many as you need — they share state via the registry |

**Three descriptor types — `setting()`, `shadow()`, `watch()`.** All three are declared at class level on a Settings subclass:

| Descriptor | Behaviour |
|---|---|
| `setting[T](default, ...)` | Local field. Stored in graph (NodeSettings) or TOML (LibrarySettings/FrameworkSettings). |
| `shadow(GlobalSettings.field)` | Writable mirror of a global setting. Inherits the source's label/default/type/widget/min/max. Per-node writes are allowed and stored as overrides. Panel shows a `•` prefix and a reset button when locally overridden. |
| `watch(GlobalSettings.field)` | Read-only mirror. Invisible in panel, never stored. Tracks the global value reactively. Any write attempt raises `AttributeError`. |

`shadow()` and `watch()` accept either a descriptor reference (`shadow(CanvasSettings.snap_to_grid)`) or a raw key string (`shadow("ui.canvas.snap_to_grid")`).

**The accessor name.** A node's `class filter(NodeSettings):` becomes `self.filter` on every instance. The class name is the accessor name — pick descriptive ones (`filter`, `output`, `api`). Multiple accessors per node are allowed; each gets its own `_setting_key` namespace.

**`@node` derives the namespace automatically.** From a node's `registry_key`:

```text
registry_key: haybale_core:node:transform
  → namespace: haybale_core.node.transform
  → field key: haybale_core.node.transform.filter.threshold
```

You never hand-write these — they are what TOML and the registry use under the hood.

**`setting()` parameters.**

| Parameter | Effect |
|---|---|
| `default` | Default value (positional, required) |
| `label` | Display name in the panel |
| `description` | Tooltip text |
| `category` | Panel grouping (collapsible group) |
| `order` | Sort order within category |
| `min` / `max` | Slider bounds; also infer the slider widget |
| `choices` | Dropdown options (list, dict, or callable; see below) |
| `widget` | Explicit widget hint (override the inferred one) |
| `on_change` | Method name on the *node* called when the value changes |
| `mirrors` | Source descriptor or full key — same effect as `shadow()` directly |
| `read_only` | If `True`, instance writes raise `AttributeError`; field is invisible in panel |
| `validator` | `Callable(value) -> bool`; return `False` to reject. Checked before `setattr` |
| `stored` | If `False`, excluded from serialization |
| `metadata` | Arbitrary dict attached to the descriptor as `._metadata` |

**Widget inference.** Type and parameters together pick the panel widget:

| Condition | Widget |
|---|---|
| `widget='label'` | Read-only label |
| Type `Color` (`Color = str`) | Color picker |
| Type `Icon` (`Icon = str`) | Material icon picker |
| `choices` set | Dropdown |
| Type `bool` | Toggle |
| Type `int` / `float` | NumberDrag (Blender-style drag input) |
| Otherwise | Text input |

**`choices` accepts three forms.**

```python
# Static list — value shown and stored as-is
algorithm = setting[str]('fast', choices=['fast', 'accurate'])

# Dict — {stored_value: display_label}
algorithm = setting[str]('fast', choices={'fast': 'Fast Mode', 'accurate': 'High Accuracy'})

# Callable — evaluated at render time (use for dynamic lists from a registry)
theme = setting[str]('', choices=lambda: get_theme_registry().list_workbench_keys())
```

The callable form is evaluated fresh on every panel render, so plugin-added entries appear automatically.

**`on_change` callbacks.** Method name on the *node class* called whenever the resolved value changes (local set, reset, or upstream global change for shadow/watch fields):

```python
class filter(NodeSettings):
    scale = setting[float](1.0, on_change='hb_on_scale')

def hb_on_scale(self, value: float, field: str = ''):
    self.cache.scaled = value * 2
```

Use the `hb_*` prefix to keep your method names safe across framework updates.

**Panel rendering rules.** When the properties panel calls `render_reactive(node.filter)`:

- Fields with `read_only=True` are skipped entirely.
- Fields are sorted by `(category, order, attr_name)` and grouped under collapsible category headers.
- Mirror fields (`shadow()` / `watch()`) that are locally overridden show a `•` prefix and a reset button (`restart_alt` icon) that calls `obj.reset(attr_name)`.
- Each row produces this DOM structure (useful for tests):

```text
div[data-field="<attr_name>"]        ← row container
  label                              ← field label (with • prefix if locally overridden)
  <widget>[data-value="..."]         ← current value, always readable via DOM
  button[restart_alt]                ← reset button (mirror fields, when overridden)
div                                  ← error container (populated on validation failure)
  label[data-error="true"]           ← error message (only when last write was rejected)
```

**Settings instance methods.** Accessible via the accessor name (`self.filter.<method>()`):

| Method | Effect |
|---|---|
| `reset(name)` | Remove the local override for `name` (falls back through the chain) |
| `reset_all()` | Reset every field |
| `is_locally_set(name)` | `True` if the field has a local instance override |
| `subscribe(callback)` | `callback(name, value, old)` on any change |
| `to_dict()` | Returns only fields that differ from the descriptor default; `watch()` fields are never included |
| `from_dict(data, silent=True)` | Restore values; `silent=True` writes directly without firing callbacks (used during graph load) |

**Serialization.** Only locally-overridden values are serialized. Fields at their default and `watch()` fields are never stored:

```json
{
  "node_id": "abc123",
  "settings": {
    "filter": { "threshold": 0.8, "bg_color": "#ff0000" }
  },
  "store": { "execution_count": 42 }
}
```

The outer key is the accessor name; the inner dict maps field name → locally-set value.

**LibrarySettings registration.** A `@settings`-decorated class is picked up by `BaseRegistry`'s hot-reload machinery automatically when the library loads. No explicit `register_schema()` call is needed in normal usage. (For explicit registration in a `register_components()` override, see the LibrarySettings section in the example below.)

**Important ordering rule for `shadow()` / `watch()` between modules.** A node class using `shadow(MyLibSettings.api_url)` must be **defined after** `MyLibSettings`. The `@settings(namespace='my_lib')` decorator sets `_setting_key` on each descriptor at class evaluation time; if your node imports `MyLibSettings` later, that's fine — but if both live in the same module, declaration order matters.

## 3a. Using `LibrarySettings` from a State, Editor, or Panel

Hold a `LibrarySettings` instance the same way you'd hold any other dependency: construct it once, read fields off it. No injection, no setup call.

```python
from haybale_mylib.settings import MyLibSettings

class MyState(AppState):
    def on_enable(self):
        self.settings = MyLibSettings()
        # use it:
        port = self.settings.port
        # writes persist to workspace TOML automatically:
        self.settings.port = 8080
```

That's the whole API. Reads resolve through the chain (default → global → workspace → local override); writes go straight to the workspace TOML.

### Where you can construct it

| Location | OK? |
|---|---|
| `AppState.__init__` or `on_enable` | Yes |
| `Editor.__init__` or any editor method | Yes |
| `Panel.__init__` or any panel method | Yes |
| Inside a node worker, callback, or event handler | Yes |
| Module/class top level (at import time) | **No** — see below |

The rule: any code that runs *after* the owning library finishes loading can construct that library's settings. Everything listed above runs later than that, so you don't need to think about timing.

### What doesn't work, and why

**Module/class top level.** This runs at import time, before the library has loaded:

```python
from haybale_mylib.settings import MyLibSettings

class MyPanel(Panel):
    settings = MyLibSettings()   # ✗ runs at class-definition time

settings = MyLibSettings()       # ✗ runs at module import time
```

These do **not** crash — and that's the danger. You get a silently degraded instance: reads always return defaults, writes don't persist to TOML, and the instance is never upgraded once the library loads. Your settings appear to "work" in dev (defaults look fine) and quietly lose user data in production.

Move the call into a method (`__init__`, `on_enable`, a render method — anything that runs later) and it works correctly.

### Using one library's settings from another library

If your library reads settings from a sibling library, declare it as a dependency:

```python
@library(id="my_lib", dependencies=["other_lib"], ...)
class Library(BaseLibrary):
    ...
```

This is enough — the framework will load `other_lib` first, so by the time your code runs you can construct `OtherLibSettings()` like any other. Without the `dependencies=` entry, load order is undefined.

### Multiple holders are fine

Constructing `MyLibSettings()` in a State and again in an Editor (or anywhere else) gives you two separate instances — there's no singleton. That's intentional and safe: the persisted values live on the shared registry, not on the instances. A write through one holder is visible to the other on its next read.

```python
# In MyState.on_enable:
self.settings = MyLibSettings()
self.settings.port = 8080         # routed through the registry → workspace TOML

# In MyEditor.on_enable (any time, before or after):
self.settings = MyLibSettings()
print(self.settings.port)         # → 8080 (resolved fresh from the registry)
```

Each holder subscribes independently if it wants change notifications — there's no cross-instance piggybacking.

### Subscribing to changes

If you want to react to a setting being changed (by the user, by another panel, by a TOML edit), subscribe:

```python
def on_enable(self):
    self.settings = MyLibSettings()
    self.settings.subscribe(self._on_setting_changed)

def _on_setting_changed(self, name, value, old):
    if name == 'port':
        self.reconnect()
```

The callback fires on any change — local writes, global writes from other places, TOML reload. You only get notifications while you hold a reference to your settings instance, so keep it on `self`.

## 4. Live examples from the codebase

**LibrarySettings** — source: [`barn/haybale-testing/haybale_testing/settings/testing.py`](../../../barn/haybale-testing/haybale_testing/settings/testing.py)

`TestingSettings` demonstrates the full `@settings` / `LibrarySettings` surface: `float`, `int`, `str`, `bool`, `Color`, `Vec2i`, `Vec3f` field types, `min`/`max`, `choices`, `category`, `widget`:

```python
--8<-- "barn/haybale-testing/haybale_testing/settings/testing.py:testing_settings"
```

**NodeSettings with every descriptor** — source: [`barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py`](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py)

`SettingsNode.example` exercises every `setting()` type, `read_only`, `stored=False`, `shadow()`, `watch()`, and `validator` in one inner class:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py:settings_node_class"
```

What these examples exercise:

| Concept | Where it shows up |
|---|---|
| `@settings(namespace=..., label=...)` on `LibrarySettings` | `TestingSettings` |
| `setting[float]` with `min`/`max` | `default_intensity` |
| `setting[int]` with `min`/`max` | `default_count` |
| `setting[str]` plain and with `choices` | `default_label`, `default_mode` |
| `setting[bool]` | `default_enabled` |
| `setting[Color]` with `widget='color'` | `default_color` |
| `setting[Vec2i]` / `setting[Vec3f]` | `default_offset`, `default_position` |
| `read_only=True` — panel skips the field | `read_only_value` |
| `stored=False` — excluded from serialization | `transient_value` |
| `shadow()` — writable mirror, per-node override OK | `intensity`, `count_mirror`, … |
| `watch()` — read-only mirror, invisible in panel | `intensity_ro`, `count_ro`, … |
| `validator=` — rejects invalid values before write | `validated_string`, `clamped_positive`, `even_int` |
| Multiple field types in one `NodeSettings` inner class | `class example(NodeSettings)` |

For the resolution chain, registry mechanics, and TOML format, see [architecture/settings](../../architecture/settings/settings-arch.md). For non-node code that needs reactive access to `ImageLibSettings`, instantiate the class directly — `cls._registry` is auto-wired after the library loads, and `subscribe(callback)` gives you change notifications.

---

## Quick reference

### Three descriptors

```python
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color, Icon

class MyNode(BaseNode):
    class filter(NodeSettings):
        # Local
        threshold = setting[float](0.5, min=0.0, max=1.0, label='Threshold')

        # Writable mirror (per-node override OK)
        snap = shadow(CanvasSettings.snap_to_grid)

        # Read-only mirror (invisible, never stored)
        log_to_file = watch(DebugSettings.log_to_file)
```

### Reset / introspect

```python
self.filter.reset('threshold')          # remove local override
self.filter.reset_all()
self.filter.is_locally_set('threshold')
self.filter.subscribe(lambda n, v, o: print(n, o, '→', v))
```

### Three containers per node

```python
self.cache.tmp = ...    # transient (not serialized, not visible)
self.store.count = 0    # persistent (serialized, not visible)
self.<accessor>.field   # serialized (only when overridden), visible in panel
```

### Library settings shorthand

```python
from haywire.core.settings import LibrarySettings, setting
from haywire.core.settings.decorator import settings

@settings(namespace='my_lib')
class MyLibSettings(LibrarySettings):
    api_url = setting[str]('https://api.example.com', label='API URL')
```

Auto-registered when the library loads. Use as `shadow(MyLibSettings.api_url)` from a node.
