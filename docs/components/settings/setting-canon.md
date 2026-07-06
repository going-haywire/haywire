---
status: draft
doc_template: canonical-example
scope: Authoring settings — NodeSettings, LibrarySettings, the setting() / shadow() / watch() descriptors, change subscriptions, panel integration
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
| `min` / `max` | Numeric bounds, folded into `widget_config["properties"]` |
| `widget` | Explicit widget contract — a `{"key", "config"}` dict from `WidgetCls.config(...)`. Wins outright over the field IType's declared default widget |
| `widget_config` | Bare property overrides layered on top of whichever widget was selected (IType default or explicit `widget=`) — e.g. `{"options": [...]}` for a `CHOICES` field |
| `mirrors` | Source descriptor or full key — same effect as `shadow()` directly |
| `read_only` | If `True`, instance writes raise `AttributeError`; field is invisible in panel |
| `validator` | `Callable(value) -> bool`; return `False` to reject. Checked before `setattr` |
| `metadata` | Arbitrary dict attached to the descriptor as `._metadata` |

**Widget selection is a stamped port contract (ADR 0017).** Every `setting()`
descriptor computes plain `widget_key: str` / `widget_config: dict`
attributes exactly **once** — at class-definition time (`__set_name__`) for a
class-body field, or at construction time for a registry-built one (`registry.define(...)`,
file auto-define). Nothing re-resolves at render time. Precedence:

1. An explicit `widget=WidgetCls.config(...)` dict, if given — wins outright.
2. Otherwise, the field's IType's own declared identity
   (`@type(widget_key=..., widget_config=...)`) — e.g. `CHOICES` declares
   `widget_key=SELECT_WIDGET`, `COLOR` declares a color-picker key, plain
   `FLOAT`/`INT` declare a NumberDrag key, `BOOL` a toggle key.
3. `min`/`max` and any `widget_config=` you pass are folded into
   `widget_config["properties"]` on top of the IType's own declared
   properties.

There is no `choices=` parameter and no string `widget="color"` /
`widget="label"` shorthand — both were deleted. For a read-only label use
`widget=SimpleLabelWidget.config()`; for a color field use `setting[COLOR]`
(its IType identity already selects the color picker, no `widget=` needed).

**Dropdowns use `setting[CHOICES]`, options supplied per-use.** `CHOICES` is
a builtin `IType(STRING)` whose identity says "renders as a select" but
carries **zero options** — every declaration site supplies its own via
`widget_config={"options": ...}`. Three option shapes:

```python
from haywire.barn.builtin.types import CHOICES

# Static list — value shown and stored as-is
algorithm = setting[CHOICES]('fast', widget_config={'options': ['fast', 'accurate']})

# Dict — {stored_value: display_label}
algorithm = setting[CHOICES](
    'fast',
    widget_config={'options': {'fast': 'Fast Mode', 'accurate': 'High Accuracy'}},
)

# Callable — resolved fresh by SelectWidget.build() on every widget build
# (use for dynamic lists from a registry; plugin-added entries appear automatically)
theme = setting[CHOICES]('', widget_config={'options': lambda: get_theme_registry().list_workbench_keys()})
```

A real example from the codebase (`haywire/core/debug/debug_settings.py`):

```python
from haywire.barn.builtin.types import BOOL, CHOICES

_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "ERROR"]

class DebugSettings(FrameworkSettings, namespace=NAMESPACE_DEBUG):
    log_level = setting[CHOICES](
        "INFO",
        label="Global Log Level",
        description="Minimum log level for the haywire root logger",
        widget_config={"options": _LEVEL_CHOICES},
    )
```

Because `CHOICES` carries identity STRING↔CHOICES adapters (both directions,
pure passthrough), a plain string port can connect to — or be promoted from —
a `CHOICES`-typed setting with no special-case handling.

**Reacting to a single field.** The `on_change='method'` string dispatch was retired (ADR 0013); use `subscribe_field` — one adapter on the field's cell, so it hears every writer (local set, reset, registry write-through, and edge drives into a promoted port's shared cell):

```python
def post_init(self):
    self.filter.subscribe_field('scale', self._on_scale)

def _on_scale(self, value: float, old: float):
    self.cache.scaled = value * 2
```

`unsubscribe(callback)` and `cleanup()` detach it; registration is idempotent per (field, callback), and one callback may watch several fields.

**Panel rendering rules.** When the properties panel calls `render_settings(node.filter)`:

- Fields with `read_only=True` are skipped entirely.
- Fields are sorted by `(category, order, attr_name)` and grouped under collapsible category headers.
- Mirror fields (`shadow()` / `watch()`) that are locally overridden show a `•` prefix and a reset button (`restart_alt` icon) that calls `obj.reset(attr_name)`.
- Each row produces this DOM structure (useful for tests):

```text
div[data-field="<attr_name>"]        ← row container (data-ui-disabled="true" when disabled)
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
| `subscribe(callback)` | `callback(name, value, old)` on any change to any field |
| `subscribe_field(field, callback)` | `callback(value, old)` on changes to one field (ADR 0013) |
| `unsubscribe(callback)` | Detach a callback registered by either subscribe method |
| `to_dict()` | Returns only fields that differ from the descriptor default; `watch()` fields are never included |
| `from_dict(data, silent=True)` | Restore values; `silent=True` writes cells directly, bypassing validation (graph load — subscribers attached later never see it) |

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

**Promoting a setting to a port (field + direction).** A setting can be *promoted* to a DATA port so the graph can drive it or read it. Promotion is a **field + a direction**; the port and the setting become one cell, two views (the port borrows the setting's cell by reference — see [architecture §6.5](../../architecture/settings/settings-arch.md#65-promotion--field--direction) and [ADR 0014](../../adr/0014-promotion-as-direction.md)).

```python
from haywire.core.node.promotion import promote_setting, demote_setting
from haywire.core.types.enums import PortType

promote_setting(node, "filter", "threshold", direction=PortType.INLET)   # edge drives the setting
promote_setting(node, "filter", "threshold", direction=PortType.OUTLET)  # setting drives downstream
demote_setting(node, "filter", "threshold")                              # remove the port
```

Eligibility is `eligible_promotion_directions(descriptor)` — declared `promotable=` (see below) intersected with the structural rule that a `watch()` field is **outlet only** (read-only ⇒ no write path in); plain and `shadow()` fields default to promotable either way. Direction picks the port factory, so a promoted **inlet** shows its widget while unlinked and hides it while driven, and a promoted **outlet** never shows one. `demote` never resets the value (freeze-on-disconnect) — recovery is an explicit `reset`. In the graph editor these are the node right-click "Promote Setting → inlet / outlet" verbs and the pin's "Detach from setting".

**Serialization (ADR 0019).** Promotion state lives in the owning settings bag, not the port: `Settings._promoted_keys: dict[str, PortType]` (`storage_key → direction`) is the single source of truth. A bag's `to_dict()` returns `{"values": {...}, "promoted": {storage_key: "inlet"|"outlet"}}` — **a promoted port is never serialized in the node's `ports` block**; it is regenerated on load by `regenerate_promoted_ports`, which walks `_promoted_keys` and calls `promote_setting` for each entry (the same path an interactive promotion takes, so there is one creation path either way). This runs after settings restore and before edges wire, so a regenerated promoted inlet exists before any edge resolves against it. `demote_setting` clears `_promoted_keys[storage_key]` in addition to removing the port — promote writes the record, demote clears it. A pre-ADR-0019 settings dict (the old flat `{field: value}` shape) is treated as incompatible: `from_dict` raises `PromotedFormatError`, the node loader resets that bag to defaults and attaches a WARNING to the node rather than crashing.

**Restricting promotion (`promotable=`).** By default every writable setting can be promoted to an inlet or an outlet, and a `watch()` field to an outlet only. A field can narrow or remove that with the `promotable=` kwarg:

```python
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.barn.builtin.types import CHOICES

class depth(NodeSettings):
    # Restart-required pipeline parameter: a port would imply live control
    # the hardware can't deliver — remove it from the promote menu entirely.
    preset_mode = setting[CHOICES](
        "HIGH_DENSITY",
        label="Preset Mode",
        promotable=Promotable.NONE,
    )
```

`Promotable` is a Flag: `NONE` / `INLET` / `OUTLET` / `ALL` (default). Effective eligibility is the intersection of the declaration and the structural rules (`read_only=True` stays outlet-only regardless; `read_only` + `promotable=INLET` intersects to nothing). The single source of truth is `eligible_promotion_directions()` in `haywire.core.node.promotion` — the promote menu hides ineligible entries and `promote_setting()` raises `ValueError` for them, whether the call is interactive or from the load-time regeneration pass.

**Disabling a setting in the panel (`ui_disabled` / `enabled_when`).** A setting can render as disabled — Quasar `:disable` where the widget root supports it, the §2.11 opacity treatment otherwise — while staying a completely normal, fully-writable field from the code's perspective. This is purely a panel-display concern: node code and any direct `setattr` keep working regardless of disabled state; there is no write guard in the settings layer.

Two composable mechanisms, combined via OR (either one disabling the field is enough):

```python
from haywire.core.settings import NodeSettings, setting
from haywire.barn.builtin.types import BOOL, FLOAT

class color(NodeSettings):
    enable_color = setting[BOOL](True, label="Enable Color")

    # Declarative: disabled whenever enable_color != True. Same-bag only,
    # exact-match only (no predicates). Live — toggling enable_color in the
    # panel immediately disables exposure, no redraw needed.
    exposure = setting[FLOAT](
        20000.0,
        label="Exposure",
        metadata={"enabled_when": ("enable_color", True)},
    )

    # Imperative: starts disabled until something says otherwise.
    manual_gain = setting[FLOAT](1.0, label="Manual Gain", ui_disabled=True)
```

```python
# Runtime API on any Settings instance — for gating driven by something
# OTHER than a sibling setting (e.g. a different node's wiring state):
bag.set_ui_disabled("manual_gain", False)   # re-enable
bag.is_ui_disabled("manual_gain")           # -> False
bag.set_ui_disabled_all(True)               # bulk: every field on the bag
```

**One channel per concern.** `set_ui_disabled` announces transitions on a dedicated UI-state channel (`bag.subscribe_ui_state(cb)` with `cb(name, disabled)`, removed via `unsubscribe_ui_state` / `cleanup()`), which the panel subscribes to. It never fires the field's cell event — the cell event keeps meaning exactly "the value changed", so value subscribers (widgets, node live-control handlers, promoted ports) are structurally incapable of hearing chrome changes. This mirrors NiceGUI's own design, where `enabled` and `value` are independent bindable properties. `set_ui_disabled` is transition-only: redundant calls fire nothing, so recomputing disabled state in a hot path is free in steady state.

`enabled_when` is a `(field_name, expected_value)` tuple stored in `metadata` — a string field reference, not validated at class-definition time. If the referenced field doesn't exist on the same bag, the panel logs a warning and the field renders normally (never auto-disabled) rather than raising. `enabled_when` only ever expresses a same-bag relationship; cross-bag or cross-node gating (e.g. one node's callback-edge wiring determining another's field state) uses `set_ui_disabled` from whatever code owns that external state.

Neither mechanism is persisted — disabled state is always transient, recomputed at construction (`ui_disabled=`) or by whatever runtime code calls `set_ui_disabled`.

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

`TestingSettings` demonstrates the full `@settings` / `LibrarySettings` surface: `FLOAT`, `INT`, `STRING`, `BOOL`, `CHOICES`, `COLOR`, `VEC2I`, `VEC3F` field types, `min`/`max`, `widget_config`, `category`:

```python
--8<-- "barn/haybale-testing/haybale_testing/settings/testing.py:testing_settings"
```

**NodeSettings with every descriptor** — source: [`barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py`](../../../barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py)

`SettingsNode.example` exercises every `setting()` type, `read_only`, `shadow()`, `watch()`, and `validator` in one inner class:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py:settings_node_class"
```

What these examples exercise:

| Concept | Where it shows up |
|---|---|
| `@settings(namespace=..., label=...)` on `LibrarySettings` | `TestingSettings` |
| `setting[FLOAT]` with `min`/`max` | `default_intensity` |
| `setting[INT]` with `min`/`max` | `default_count` |
| `setting[STRING]` plain | `default_label` |
| `setting[CHOICES]` with `widget_config={"options": [...]}` | `default_mode` |
| `setting[BOOL]` | `default_enabled` |
| `setting[COLOR]` (widget comes from the IType identity, no `widget=` needed) | `default_color` |
| `setting[VEC2I]` / `setting[VEC3F]` | `default_offset`, `default_position` |
| `read_only=True` — panel skips the field | `read_only_value` |
| `shadow()` — writable mirror, per-node override OK | `intensity`, `count_mirror`, … |
| `watch()` — read-only mirror, invisible in panel | `intensity_ro`, `count_ro`, … |
| `validator=` — rejects invalid values before write | `validated_string`, `clamped_positive`, `even_int` |
| Multiple field types in one `NodeSettings` inner class | `class example(NodeSettings)` |

For the resolution chain, registry mechanics, and TOML format, see [architecture/settings](../../architecture/settings/settings-arch.md). For non-node code that needs reactive access to `ImageLibSettings`, instantiate the class directly — `cls._registry` is auto-wired after the library loads, and `subscribe(callback)` gives you change notifications.

---

## Quick reference

### Three descriptors

```python
from haywire.core.settings import NodeSettings, setting, shadow, watch
from haywire.barn.builtin.types import FLOAT

class MyNode(BaseNode):
    class filter(NodeSettings):
        # Local
        threshold = setting[FLOAT](0.5, min=0.0, max=1.0, label='Threshold')

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
