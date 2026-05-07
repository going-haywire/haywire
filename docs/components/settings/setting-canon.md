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

| Class | Where you declare it | Registered? | Per-instance? |
|---|---|---|---|
| `NodeSettings` | Inner class on a `@node` class | No (per-instance binding) | Yes — one per node instance |
| `LibrarySettings` | `@settings`-decorated class in your library | Yes (via `BaseRegistry` hot-reload) | Singleton-ish; instances auto-wire to the registry |
| `FrameworkSettings` | Framework-internal only | Yes (auto-registers via `_pending_global`) | Singleton-ish |

**Three descriptor types — `setting()`, `shadow()`, `watch()`.** All three are declared at class level on a Settings subclass:

| Descriptor | Behaviour |
|---|---|
| `setting[T](default, ...)` | Local field. Stored in graph (NodeSettings) or TOML (LibrarySettings/FrameworkSettings). |
| `shadow(GlobalSettings.field)` | Writable mirror of a global setting. Inherits the source's label/default/type/widget/min/max. Per-node writes are allowed and stored as overrides. Panel shows a `•` prefix and a reset button when locally overridden. |
| `watch(GlobalSettings.field)` | Read-only mirror. Invisible in panel, never stored. Tracks the global value reactively. Any write attempt raises `AttributeError`. |

`shadow()` and `watch()` accept either a descriptor reference (`shadow(NodeUISettings.bg_color)`) or a raw key string (`shadow("ui.node.bg_color")`).

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

## 4. One comprehensive example

A worked example exercising every concept above: a library `image_lib` with its own `LibrarySettings`, plus a `ResizeNode` that uses local settings, a `shadow()` mirror with override capability, a `watch()` mirror for a read-only global flag, an `on_change` callback, and a `validator`. Demonstrates worker access for all three plus `cache` and `store` containers.

```python
# image_lib/settings.py
from haywire.core.settings import LibrarySettings, setting, shadow, watch, Color
from haywire.core.settings.decorator import settings

@settings(namespace='image_lib', label='Image Processing')
class ImageLibSettings(LibrarySettings):
    """Library-wide defaults — backed by ~/.haywire/settings.toml.
    Auto-registered by BaseRegistry hot-reload when the library loads."""
    jpeg_quality = setting[int](
        85, min=1, max=100,
        label='JPEG Quality', category='quality', order=10,
    )
    resize_algorithm = setting[str](
        'lanczos',
        choices=['nearest', 'bilinear', 'bicubic', 'lanczos'],
        label='Resize Algorithm', category='resize', order=10,
    )
    accent_color = setting[Color]('#3498db', label='Accent', category='appearance')
    gpu_acceleration = setting[bool](
        True, label='GPU Acceleration', category='processing',
    )

# image_lib/nodes/resize.py
from haywire.core.node import BaseNode, node
from haywire.core.settings import NodeSettings, setting, shadow, watch
from haywire.core.settings.builtins.debug import DebugSettings
from haywire.core.settings.builtins.ui_node import NodeUISettings
from ..settings import ImageLibSettings

@node(label='Resize Image', menu='image/transform')
class ResizeNode(BaseNode):
    """Exercises every authoring concept."""

    # ── Primary settings group ────────────────────────────────────────
    class resize(NodeSettings):
        # Local — stored in graph when set, shown in panel
        width = setting[int](
            512, min=1, max=8192,
            label='Width', category='dimensions', order=10,
            on_change='hb_on_size_change',
            validator=lambda v: v > 0 and v % 2 == 0,  # reject odd values
        )
        height = setting[int](
            512, min=1, max=8192,
            label='Height', category='dimensions', order=20,
            on_change='hb_on_size_change',
        )

        # shadow() — writable mirror of a library default; per-node override OK.
        # Panel shows '•' and a reset button when overridden.
        algorithm = shadow(ImageLibSettings.resize_algorithm)

        # shadow() with label override — same source, custom display
        node_bg = shadow(NodeUISettings.bg_color, label='Node Background')

        # watch() — read-only mirror; invisible in panel, never stored,
        # tracks the global value reactively
        gpu = watch(ImageLibSettings.gpu_acceleration)
        verbose = watch(DebugSettings.verbose_logging)

        # Read-only label-style display field
        info = setting[str]('Configure dimensions above', widget='label', read_only=True)

    # ── Secondary settings group (separate accessor) ──────────────────
    class output(NodeSettings):
        quality = shadow(ImageLibSettings.jpeg_quality)
        preserve_metadata = setting[bool](
            True, label='Preserve EXIF', category='quality',
        )

    def init(self):
        from haybale_core.types.specs import FLOAT
        self.add(FLOAT.as_inlet('image'))
        self.add(FLOAT.as_outlet('result'))

        # cache: transient — lost on save/load
        self.cache.last_dimensions = None
        self.cache.scaler = None

        # store: persistent — survives save/load, hidden from UI
        self.store.frames_processed = 0
        self.store.cumulative_pixels = 0

    # hb_* prefix → safe across framework updates
    def hb_on_size_change(self, value: int, field: str = ''):
        # Invalidate cached scaler when dimensions change. This fires on:
        # - direct local set: self.resize.width = 1024
        # - reset: self.resize.reset('width')
        # - upstream global change for shadow fields: not applicable here
        #   (width is local, not a mirror)
        self.cache.scaler = None
        self.cache.last_dimensions = (self.resize.width, self.resize.height)

    def worker(self, context, image):
        # Direct access via the accessor name. Resolution chain runs
        # transparently — see architecture/settings for the full chain.
        r = self.resize
        o = self.output

        if r.verbose:
            context.log(f'Resize {r.width}x{r.height} algo={r.algorithm}')

        # Counters live in store (persistent, hidden)
        self.store.frames_processed += 1
        self.store.cumulative_pixels += r.width * r.height

        # Memoise the scaler in cache (transient, lost on restart)
        if self.cache.scaler is None:
            self.cache.scaler = self._build_scaler(r.algorithm, r.width, r.height)

        # GPU flag is a watch() mirror — read-only; reflects the live global
        result = self.cache.scaler.run(image, gpu=r.gpu)

        # Write outlet, never wrap
        self.out('result', result)

    def _build_scaler(self, algo, w, h):
        # Implementation detail — could touch the global accent colour
        # for diagnostic overlays via direct registry access:
        # from image_lib.settings import ImageLibSettings
        # accent = ImageLibSettings().accent_color
        return _make_scaler(algo, w, h)
```

What this example exercises:

| Concept | Where it shows up |
|---|---|
| `LibrarySettings` with `@settings(namespace=...)` | `ImageLibSettings` |
| `setting()` with `choices`, `min`/`max`, `category`, `order` | `jpeg_quality`, `resize_algorithm` |
| Multiple `NodeSettings` accessors on one node | `class resize`, `class output` |
| Local `setting()` with `on_change` and `validator` | `width`, `height` |
| `shadow()` of a `LibrarySettings` field | `algorithm`, `quality` |
| `shadow()` with a label override | `node_bg = shadow(NodeUISettings.bg_color, label='...')` |
| `watch()` for a read-only mirror | `gpu`, `verbose` |
| `read_only=True` + `widget='label'` for display-only | `info` |
| `validator=` rejecting invalid input | `width` (must be even and > 0) |
| `on_change` callback with `hb_*` prefix | `hb_on_size_change` |
| Worker access via accessor name | `self.resize.width`, `self.output.quality` |
| `self.cache` for transient state | `self.cache.scaler`, `self.cache.last_dimensions` |
| `self.store` for persistent hidden state | `self.store.frames_processed` |

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
        bg = shadow(NodeUISettings.bg_color)

        # Read-only mirror (invisible, never stored)
        debug = watch(DebugSettings.verbose_logging)
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
