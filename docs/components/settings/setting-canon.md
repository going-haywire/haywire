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
- **Mirror descriptors** (`shadow()` / `watch()`) — a node setting that *references* a global setting. `shadow()` is writable (per-node override allowed); `watch()` seeds `ui_state=DISABLED` and `promotable=OUTLET` (renders as a greyed widget, outlet-only-promotable by declaration — writes are not structurally blocked, just conventionally discouraged).

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

**The four Settings classes.** All four inherit from `Settings`. Pick by scope:

| Class | Where you declare it | Persisted to | Instances |
|---|---|---|---|
| `NodeSettings` | Inner class on a `@node` class | Graph file (only overrides) | One per node, owned by the node |
| `GraphSettings` | Framework-internal only (one bag today: `GraphProperties`) | Graph file, under `"props"` (only overrides) | One per graph, owned by the graph (`graph.props`) |
| `LibrarySettings` | `@settings`-decorated class in your library | Workspace / global TOML | Construct as many as you need — they share state via the registry |
| `FrameworkSettings` | Framework-internal only | Workspace / global TOML | Construct as many as you need — they share state via the registry |

**Four descriptor types — `setting()`, `shadow()`, `watch()`, `graph()`.** All four are declared at class level on a Settings subclass:

| Descriptor | Behaviour |
|---|---|
| `setting[T](default, ...)` | Local field. Stored in graph (NodeSettings/GraphSettings) or TOML (LibrarySettings/FrameworkSettings). |
| `shadow(GlobalSettings.field)` | Writable mirror of a global (registry-backed) setting. Inherits the source's label/default/type/widget/min/max. Per-node writes are allowed and stored as overrides. Panel shows a `•` prefix and a reset button when locally overridden. |
| `watch(GlobalSettings.field)` | Sugar over `shadow()`: seeds `ui_state=UiState.DISABLED` (renders as a greyed, non-interactive widget in the panel) and `promotable=Promotable.OUTLET`. Tracks the global value reactively. Writes are still technically legal (no enforced guard) but are a naming/usage convention — a `watch()` field is meant to be read, not written. |
| `graph(GraphSettingsField)` | Writable mirror of a field declared on a `GraphSettings` bag (ADR 0022) — the graph-tier analogue of `shadow()`. See [§3b](#3b-mirroring-a-graph-setting-from-a-node-bag) below. |

`shadow()` and `watch()` accept either a descriptor reference (`shadow(CanvasSettings.snap_to_grid)`) or a raw key string (`shadow("ui.canvas.snap_to_grid")`), and the source must be declared on a DIFFERENT class — a same-bag sibling raises `ValueError`. `graph()` accepts **only** a descriptor reference, and only one whose owner is a `GraphSettings` subclass — `TypeError` at class-definition time otherwise. Use `shadow()`/`watch()` for a registry-backed (Framework/Library) source; use `graph()` for a `GraphSettings` source. Pointing `shadow()` at a `GraphSettings` field instead of using `graph()` fails loudly at wiring time (bag construction), naming the fix.

**The accessor name.** A node's `class filter(NodeSettings):` becomes `self.filter` on every instance. The class name is the accessor name — pick descriptive ones (`filter`, `output`, `api`). Multiple accessors per node are allowed; each gets its own `_setting_key` namespace.

**`@node` derives the namespace automatically.** From a node's `registry_key`:

```text
example key: haybale-core:node:transform
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
| `mirrors` | Source descriptor or full key, on a DIFFERENT class — same effect as `shadow()` directly |
| `ui_state` | Initial `UiState` (`NORMAL`/`DISABLED`/`HIDDEN`) seed — controls widget presentation and rendering |
| `promotable` | Which port directions this field may be promoted to (default `ALL`) |
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
--8<-- "packages/haywire-core/src/haywire/core/debug/debug_settings.py:debug-settings-choices-example"
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

- Every field renders a row, sorted by `(category, order, attr_name)` and grouped under collapsible category headers.
- A field's `effective_ui_state()` controls chrome: `DISABLED` renders the widget non-interactive (greyed), `HIDDEN` removes the row entirely. `watch()` seeds `DISABLED`.
- Mirror fields (`shadow()` / `watch()`) that are locally overridden show a `•` prefix and a reset button (`restart_alt` icon) that calls `obj.reset(attr_name)`.
- Each row produces this DOM structure (useful for tests):

```text
div[data-field="<attr_name>"]        ← row container (data-ui-state="normal"|"disabled"|"hidden")
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
| `to_dict()` | Returns only fields that differ from the descriptor default and are locally set |
| `from_dict(data, silent=True)` | Restore values; `silent=True` writes cells directly, bypassing validation (graph load — subscribers attached later never see it) |

**Serialization.** Only locally-overridden values are serialized. Fields at their default are never stored:

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

Eligibility is `eligible_promotion_directions(descriptor)` — purely the field's declared `promotable=` (see below); `watch()` seeds `Promotable.OUTLET` itself, so plain and `shadow()` fields default to promotable either way and a `watch()` field is outlet only by declaration, not by a separate structural rule. Direction picks the port factory. In the settings panel a promoted **inlet** row replaces its widget with a "promoted" label (the graph owns the value); a promoted **outlet** row keeps its editable widget. `demote` never resets the value (freeze-on-disconnect) — recovery is an explicit `reset`. In the studio these live in the **Setting-row menu** (right-click a row's label in the properties panel: Promote to inlet / Promote to outlet / Demote / Reset); the pin's right-click keeps "Detach from setting".

**Serialization (ADR 0019).** Promotion state lives in the owning settings bag, not the port: `Settings._promoted_keys: dict[str, PortType]` (`storage_key → direction`) is the single source of truth. A bag's `to_dict()` returns `{"values": {...}, "promoted": {storage_key: "inlet"|"outlet"}}` — **a promoted port is never serialized in the node's `ports` block**; it is regenerated on load by `regenerate_promoted_ports`, which walks `_promoted_keys` and calls `promote_setting` for each entry (the same path an interactive promotion takes, so there is one creation path either way). This runs after settings restore and before edges wire, so a regenerated promoted inlet exists before any edge resolves against it. `demote_setting` clears `_promoted_keys[storage_key]` in addition to removing the port — promote writes the record, demote clears it. A pre-ADR-0019 settings dict (the old flat `{field: value}` shape) is treated as incompatible: `from_dict` raises `PromotedFormatError`, the node loader resets that bag to defaults and attaches a WARNING to the node rather than crashing.

**Restricting promotion (`promotable=`).** By default every writable setting can be promoted to an inlet or an outlet, and a `watch()` field to an outlet only. A field can narrow or remove that with the `promotable=` kwarg:

```python
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.barn.builtin.types import CHOICES

class depth(NodeSettings):
    # Restart-required pipeline parameter: a port would imply live control
    # the hardware can't deliver — remove it from the Setting-row menu entirely.
    preset_mode = setting[CHOICES](
        "HIGH_DENSITY",
        label="Preset Mode",
        promotable=Promotable.NONE,
    )
```

`Promotable` is a Flag: `NONE` / `INLET` / `OUTLET` / `ALL` (default). Effective eligibility is purely the declared flag — `watch()` seeds `Promotable.OUTLET` itself, so there's no separate structural rule to intersect with. The single source of truth is `eligible_promotion_directions()` in `haywire.core.node.promotion` — the Setting-row menu hides ineligible entries and `promote_setting()` raises `ValueError` for them, whether the call is interactive or from the load-time regeneration pass.

**Presentation state (`UiState`: `ui_state=` / `enabled_when` / `visible_when`).** A setting has a three-valued presentation state in the panel — `UiState.NORMAL` (rendered, interactive), `UiState.DISABLED` (rendered but non-interactive: Quasar `:disable` where the widget root supports it, the §2.11 opacity treatment otherwise), and `UiState.HIDDEN` (the row is not rendered at all; a category whose rows are ALL hidden hides its header too). DISABLED means *exists but locked*; HIDDEN means *does not apply right now* (e.g. a manual-focus value while focus mode is AUTO). This is purely a panel-display concern: node code and any direct `setattr` keep working regardless of state; there is no write guard in the settings layer, values keep serializing normally, and the state itself is never persisted.

Three composable sources, combined by **severity max** (`NORMAL < DISABLED < HIDDEN` — `UiState` is an `IntEnum` in that order):

```python
from haywire.core.settings import NodeSettings, UiState, setting
from haywire.barn.builtin.types import BOOL, CHOICES, FLOAT

class color(NodeSettings):
    enable_color = setting[BOOL](True, label="Enable Color")
    focus_mode = setting[CHOICES]("AUTO", label="Focus Mode",
                                  widget_config={"options": ["AUTO", "MANUAL"]})

    # Declarative DISABLE: locked whenever enable_color != True. Same-bag
    # only, exact-match only (no predicates). Live — toggling enable_color
    # in the panel immediately disables exposure, no redraw needed.
    exposure = setting[FLOAT](
        20000.0,
        label="Exposure",
        metadata={"enabled_when": ("enable_color", True)},
    )

    # Declarative HIDE: the row disappears whenever focus_mode != "MANUAL".
    # Same tuple shape and same-bag/exact-match contract as enabled_when.
    manual_focus = setting[FLOAT](
        0.0,
        label="Manual Focus",
        metadata={"visible_when": ("focus_mode", "MANUAL")},
    )

    # Imperative seed: starts disabled until something says otherwise.
    manual_gain = setting[FLOAT](1.0, label="Manual Gain", ui_state=UiState.DISABLED)
```

```python
# Runtime API on any Settings instance — for gating driven by something
# OTHER than a sibling setting (e.g. a different node's wiring state):
bag.set_ui_state("manual_gain", UiState.NORMAL)          # re-enable
bag.ui_state("manual_gain")                              # imperative state only
bag.effective_ui_state("manual_gain")                    # composed (use this)
bag.set_ui_state_all(UiState.DISABLED)                   # bulk: every field on the bag
bag.set_ui_state_all(UiState.HIDDEN, category="Manual")  # bulk: one category only
```

`effective_ui_state(name)` is the **single composition oracle** — severity max of the imperative state, `enabled_when` (contributes at most DISABLED), and `visible_when` (contributes HIDDEN). Both the panel's row rendering and the Setting-row menu consume it, so they can never disagree. `category=` on the bulk setter is purely a *selector* over the fields' declared `category=` — a category carries no state of its own; header visibility is derived from its rows.

**One channel per concern.** `set_ui_state` announces transitions on a dedicated UI-state channel (`bag.subscribe_ui_state(cb)` with `cb(name, state)`, removed via `unsubscribe_ui_state` / `cleanup()`), which the panel subscribes to. It never fires the field's cell event — the cell event keeps meaning exactly "the value changed", so value subscribers (widgets, node live-control handlers, promoted ports) are structurally incapable of hearing chrome changes. This mirrors NiceGUI's own design, where `enabled` and `value` are independent bindable properties. `set_ui_state` is transition-only: redundant calls fire nothing, so recomputing state in a hot path is free in steady state. Declarative (`enabled_when`/`visible_when`) re-evaluation does NOT ride this channel — a controller-value change is a genuine cell event, and the panel's per-row controller subscription handles it.

`enabled_when` and `visible_when` are `(field_name, expected_value)` tuples stored in `metadata` — string field references, not validated at class-definition time. If the referenced field doesn't exist on the same bag, the panel logs a warning at row build and the field renders normally (never auto-gated) rather than raising; `effective_ui_state` skips the broken gate silently. Both only ever express a same-bag relationship; cross-bag or cross-node gating (e.g. one node's callback-edge wiring determining another's field state) uses `set_ui_state` from whatever code owns that external state.

**Promotion interplay with `UiState`.** The Setting-row menu never renders for HIDDEN rows (the row itself isn't rendered); DISABLED fields stay promotable. Structural eligibility (`promotable=`, `eligible_promotion_directions()`) and load-time port regeneration ignore UiState entirely — hiding never unpromotes, and a linked inlet on a hidden field keeps driving the value (the port stays visible on the canvas).

No part of this mechanism is persisted — presentation state is always transient, recomputed at construction (`ui_state=` seed) or by whatever runtime code calls `set_ui_state`.

## 3b. Mirroring a graph setting from a node bag

A graph owns one framework-provided settings bag, `graph.props` (a `GraphProperties` instance), accessed the same way `node.props` is. Its `default_skin` field shadows the framework's studio-skin default via an ordinary `shadow()` — nothing new there. What's new is the **other** direction: a node field mirroring a field on the graph bag, so the resolution order becomes **framework default < graph opinion < node opinion**.

```python
from haywire.core.settings import NodeSettings
from haywire.core.settings.descriptor import graph
from haywire.core.graph.properties import GraphProperties

class NodeProperties(NodeSettings):
    skin = graph(
        src=GraphProperties.default_skin,
        label="Skin",
        category="appearance",
        # Mirrors inherit IType from src, but NOT its per-setting widget_config —
        # options must be re-supplied here.
        widget_config={"options": _node_skin_choices},
    )
```

This is the actual declaration `NodeProperties.skin` uses (ADR 0022).

**Tier semantics, per hop.** Each hop in the chain (framework → graph, graph → node) independently follows "unset tracks, set ignores": while a field has no local override, it live-tracks the tier below it; a local write wins and the field stops tracking; `reset()` returns to *whatever the tier below currently holds* (not the framework default, unless the tier below is itself unset all the way down). A framework change only reaches an unset node field by passing through an unset graph bag first — a graph-level opinion is a genuine dam in the chain.

**When to use `graph()` vs `shadow()`/`watch()`.** Use `shadow()`/`watch()` when the source field lives on a `FrameworkSettings` or `LibrarySettings` schema (registry-backed, has a `_setting_key`). Use `graph()` when the source lives on a `GraphSettings` bag. The two are not interchangeable: `graph()` validates its `src` eagerly (`TypeError` at class-definition time unless `src`'s owner is a `GraphSettings` subclass), and a `shadow()` mistakenly pointed at a `GraphSettings` field fails loudly at bag-construction time instead of silently never tracking.

**Headless / detached bags.** A `graph()` field's mirror is only live when its bag can reach a graph (`node.wrapper.graph`, for a `NodeSettings` bag). A bag built without a node, or a node not yet attached to a graph, sees the field hold its plain descriptor default — not a fallback resolution of the framework value. This is deliberate (ADR 0022): no production code path constructs such a bag, since a `NodeWrapper`'s graph is a required constructor argument.

**Declaring your own `GraphSettings` bag.** Only one bag exists today (`GraphProperties`); a library adding its own graph-scoped bag is out of scope for now (see ADR 0022's rejected alternatives — the hot-reload lifecycle for library-registered graph bags was judged not worth the risk yet).

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
@library(id="my_lib", ...)   # linked_libraries live in haybale.toml
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

**LibrarySettings** — source: `barn/haybale-testing/haybale_testing/settings/testing.py`

`TestingSettings` demonstrates the full `@settings` / `LibrarySettings` surface: `FLOAT`, `INT`, `STRING`, `BOOL`, `CHOICES`, `COLOR`, `VEC2I`, `VEC3F` field types, `min`/`max`, `widget_config`, `category`:

```python
--8<-- "barn/haybale-testing/haybale_testing/settings/testing.py:10:69"
```

from: `TestingSettings` — registry_key: `haybale-testing:setting:TestingSettings`

**NodeSettings with every descriptor** — source: `barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py`

`SettingsNode.example` exercises every `setting()` type, `shadow()`, `watch()`, and `validator` in one inner class:

```python
--8<-- "barn/haybale-testing/haybale_testing/nodes/testbed/settings_node.py:9:148"
```

from: `SettingsNode` — registry_key: `haybale-testing:node:SettingsNode`

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
| `shadow()` — writable mirror, per-node override OK | `intensity`, `count_mirror`, … |
| `watch()` — mirror seeded DISABLED + outlet-only-promotable | `intensity_ro`, `count_ro`, … |
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

        # Mirror seeded DISABLED + outlet-only-promotable (still writable — convention, not enforced)
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
