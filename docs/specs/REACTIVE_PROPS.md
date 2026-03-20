# Reactive Props — Lightweight Observable Properties for Haywire

**Status:** Specification
**Module:** `haywire.core.reactive`
**Descriptor:** `prop()`
**Base class:** `Reactive`

---

## 1. Motivation

Haywire's Settings system (`setting()` + `GlobalSettings` + `GlobalSettingsRegistry` +
`ResolutionChain` + `SettingsHolder`) is designed for hierarchical, multi-tier resolution —
global OVERRIDE → workspace OVERRIDE → per-node local → workspace SET → global SET → default.
That machinery is warranted for node settings where library developers need per-instance
overrides with global defaults, `shadow()`, and `watch()`.

However, many framework-internal classes are just **flat bags of typed, observable properties**:
app-level preference singletons (debug, editor, execution settings), per-node instance state
(muted, collapsed, pinned, skin), and future service configuration objects. Forcing these through
the full Settings pipeline adds complexity and indirection for zero benefit.

NiceGUI's `BindableProperty` solves this pattern, but `haywire.core` must remain free of UI
dependencies.

**Reactive Props** is a ~80-line pure-Python module in `haywire.core` that provides:

- Direct attribute access (`obj.field = value`)
- Change notification (callbacks fired on set)
- UI metadata (label, type, min/max, choices) — same fields as `setting()` for panel rendering
- Built-in `to_dict()` / `from_dict()` serialization
- Zero external dependencies

---

## 2. Scope

### In scope — migrates to `Reactive` + `prop()`

All Reactive implementations are framework concerns and live in `haywire-core`, not in
library code. App singletons that currently live in `haybale-studio/settings/` move to
`haywire/ui/prefs/` as part of this migration.

| Class | Current location | New location | Category |
|---|---|---|---|
| `NodeInstanceSettings` | `haywire/core/settings/builtins/node_instance.py` | same (rewritten in place) | Per-node instance state |
| `DebugSettings` | `haybale-studio/settings/debug.py` | `haywire/ui/prefs/debug.py` | App singleton |
| `EditorSettings` | `haybale-studio/settings/editor.py` | `haywire/ui/prefs/editor.py` | App singleton |
| `ExecutionSettings` | `haybale-studio/settings/execution.py` | `haywire/ui/prefs/execution.py` | App singleton |
| `WorkbenchSettings` | `haybale-studio/settings/workbench.py` | `haywire/ui/prefs/workbench.py` | App singleton |
| `NodeThemeSettings` | `haybale-studio/settings/workbench.py` | `haywire/ui/prefs/workbench.py` | App singleton |
| `CanvasSettings` | `haybale-studio/settings/ui_canvas.py` | `haywire/ui/prefs/canvas.py` | App singleton |
| `NodeUISettings` | `haybale-studio/settings/ui_node.py` | `haywire/ui/prefs/node_ui.py` | App singleton |
| `EdgeUISettings` | `haybale-studio/settings/ui_edge.py` | `haywire/ui/prefs/edge_ui.py` | App singleton |
| `MinimapSettings` | `haybale-studio/settings/ui_minimap.py` | `haywire/ui/prefs/minimap.py` | App singleton |

**Target layout:**

```
packages/haywire-core/src/haywire/
├── core/
│   ├── reactive.py                         # Reactive + prop()
│   └── settings/
│       └── builtins/
│           └── node_instance.py            # NodeInstanceSettings (Reactive)
└── ui/
    └── prefs/                              # Framework preference singletons
        ├── __init__.py                     # re-exports all prefs classes
        ├── debug.py                        # DebugSettings
        ├── editor.py                       # EditorSettings
        ├── execution.py                    # ExecutionSettings
        ├── workbench.py                    # WorkbenchSettings, NodeThemeSettings
        ├── canvas.py                       # CanvasSettings
        ├── node_ui.py                      # NodeUISettings
        ├── edge_ui.py                      # EdgeUISettings
        └── minimap.py                      # MinimapSettings
```

**Why `haywire/ui/prefs/`?** These classes configure UI behaviour (canvas zoom, edge
curves, node dimensions, minimap layout, editor interaction). They belong in the framework
because they are consumed by framework renderers and editors — not library-specific.
`haybale-studio/settings/` is deleted after migration.

**Validation:** None of these classes are referenced by `shadow()` or `watch()` in any
library node code. All are mockups consumed only by their own panels.

### Out of scope — stays on full Settings system

- `NodeSettings` (per-node, hierarchical, `shadow()`/`watch()` targets)
- `LibrarySettings` (library-global defaults, `shadow()` targets)
- `GlobalSettings` base class itself (remains available for future hierarchical use)
- `SettingsHolder`, `SubHolder`, `ResolutionChain` (unchanged)
- `GlobalSettingsRegistry` (unchanged, but no longer used by the migrated classes)

---

## 3. API Specification

### 3.1 `prop()` — Descriptor

```python
from haywire.core.reactive import prop

class MySettings(Reactive):
    threshold: float = prop(0.5, label='Threshold', min=0.0, max=1.0)
    algorithm: str   = prop('fast', label='Algorithm', choices=['fast', 'accurate'])
    verbose:   bool  = prop(False, label='Verbose')
    theme:     str   = prop('', label='Theme', choices=lambda: get_available_themes())
```

**Constructor signature:**

```python
prop(
    default,
    *,
    label: str = '',
    description: str = '',
    category: str = '',
    order: int = 0,
    min: Any = None,
    max: Any = None,
    choices: list | dict | Callable | None = None,
    widget: str | None = None,
)
```

**Behaviour:**

- **Class-level access** returns the descriptor itself (for introspection by panels and
  `shadow()`-style references if ever needed)
- **Instance-level `__get__`** returns the current value (stored in `obj.__dict__` under a
  private key `_prop_{name}`, falling back to `_default`)
- **Instance-level `__set__`** stores the value and calls `obj._on_prop_change(name, value, old)`
  if the value differs from the previous one
- **`_type`** is inferred from `type(default)` (same as `setting()`)

**Metadata attributes** (same names as `SettingDescriptor` for panel compatibility):

`_default`, `_type`, `_label`, `_description`, `_category`, `_order`,
`_min`, `_max`, `_choices`, `_widget`, `_attr_name`

**`.choices` property** — resolves callable, identical to `SettingDescriptor.choices`.

### 3.2 `Reactive` — Base class

```python
from haywire.core.reactive import Reactive

class ExecutionSettings(Reactive):
    auto_execute: bool = prop(True, label='Auto Execute')
    debounce_ms:  int  = prop(100,  label='Debounce (ms)', min=0, max=2000)
```

**Instance methods:**

| Method | Signature | Description |
|---|---|---|
| `subscribe` | `(callback) -> None` | Register `callback(name, value, old)` |
| `unsubscribe` | `(callback) -> None` | Remove a previously registered callback |
| `to_dict` | `() -> dict` | Serialize non-default values: `{'field': value, ...}` |
| `from_dict` | `(data, *, silent=True) -> None` | Restore values. `silent=True` skips callbacks |
| `reset` | `(name) -> None` | Reset a single field to its default |
| `reset_all` | `() -> None` | Reset all fields to defaults |

**Class methods:**

| Method | Signature | Description |
|---|---|---|
| `_prop_fields` | `() -> dict[str, prop]` | All `prop` descriptors on this class (walks MRO) |

**`_on_prop_change(name, value, old)`** — called by `prop.__set__`. Default implementation
iterates `_callbacks`. Subclasses can override for custom logic.

**`__init__`** — initializes `_callbacks: list = []`. Subclasses that override `__init__`
must call `super().__init__()`.

### 3.3 Serialization format

`to_dict()` returns only fields whose current value differs from the descriptor default:

```python
settings = ExecutionSettings()
settings.auto_execute = False
settings.to_dict()
# → {'auto_execute': False}
```

`from_dict(data, silent=True)` restores values:

- `silent=True` (default): writes directly to the private attr — no callbacks fired.
  Used during deserialization (graph load, TOML hydration).
- `silent=False`: uses normal `setattr` — callbacks fire. Used for live updates.

Unknown keys in `data` are silently ignored (forward compatibility).

### 3.4 Backward-compatible graph serialization

For `NodeInstanceSettings`, the graph JSON format stays compatible:

```json
{
  "settings": {
    "node": { "schema_values": { "threshold": 0.8 } }
  },
  "props": { "muted": true, "collapsed": true },
  "store": { "execution_count": 42 },
  "ui": { "state": { "x": 100, "y": 200 } }
}
```

`_initialize_from_dict()` handles migration from the old format:

```python
# New format: 'props' at top level
if 'props' in data:
    self._props.from_dict(data['props'])
# Old format: '_node' nested inside 'settings'
elif 'settings' in data and '_node' in data['settings']:
    old = data['settings'].pop('_node', {})
    self._props.from_dict(old.get('schema_values', {}))
```

### 3.5 Panel rendering

A new `render_reactive()` function in `_settings_panel_base.py` renders any `Reactive`
instance. It reuses the existing `_render_widget_impl()` since `prop()` carries identical
metadata attributes.

```python
def render_reactive(obj: Reactive) -> None:
    fields = type(obj)._prop_fields()
    sorted_fields = sorted(fields.items(), key=lambda item: (item[1]._order, item[0]))
    for attr_name, defn in sorted_fields:
        value = getattr(obj, attr_name)
        label_text = defn._label or attr_name
        with ui.row().classes('w-full items-center justify-between gap-0 px-2 py-0'):
            lbl = ui.label(label_text).classes('text-sm flex-1 min-w-0 truncate')
            if defn._description:
                lbl.tooltip(defn._description)
            _render_widget_impl(defn, value, lambda coerce: _make_reactive_setter(obj, attr_name, coerce))

def _make_reactive_setter(obj, attr_name, coerce):
    def handler(e):
        try:
            setattr(obj, attr_name, coerce(e.value))
        except Exception:
            pass
    return handler
```

Panel draw methods simplify from:

```python
# Before
registry = context.app.library_service.get_settings_registry()
render_schema(ExecutionSettings, registry)

# After
exec_settings = context.app.injector.get(ExecutionSettings)
render_reactive(exec_settings)
```

---

## 4. Integration Points

### 4.1 `NodeInstanceSettings` on `BaseNode`

`NodeData.__init__()` creates a `Reactive` instance as a sibling to `cache`, `store`, `ui`:

```python
self._props = NodeInstanceSettings()   # replaces schemas['_node'] injection
```

Exposed as `self.props` (property). `NodeUI` delegates change from
`self._node.settings._node.collapsed` to `self._node.props.collapsed`.

The `'_node'` reserved accessor name validation in `@node` decorator is removed.

### 4.2 App singletons via DI

App-level `Reactive` instances live in `haywire/ui/prefs/` and are registered as
singletons in the DI container (in `HaywireModule`):

```python
# In HaywireModule (haywire-core DI config)
from haywire.ui.prefs import ExecutionSettings, DebugSettings

binder.bind(ExecutionSettings, to=ExecutionSettings(), scope=singleton)
binder.bind(DebugSettings, to=DebugSettings(), scope=singleton)
```

Panels access them via `context.app.injector.get(ExecutionSettings)`.

### 4.3 TOML persistence for app singletons

Not built into `Reactive` itself. Handled externally at app startup:

```
1. Create singleton:     exec = ExecutionSettings()
2. Load workspace TOML:  exec.from_dict(toml_data.get('execution', {}))
3. Subscribe auto-save:  exec.subscribe(lambda *_: save_workspace_toml())
```

This keeps `haywire.core.reactive` free of file I/O concerns.

---

## 5. What `prop()` shares with `SettingDescriptor`

Both carry the same metadata attribute names so that `_render_widget_impl()` works
unchanged for either:

| Attribute | `prop()` | `SettingDescriptor` |
|---|---|---|
| `_default` | yes | yes |
| `_type` | yes | yes |
| `_label` | yes | yes |
| `_description` | yes | yes |
| `_category` | yes | yes |
| `_order` | yes | yes |
| `_min` | yes | yes |
| `_max` | yes | yes |
| `_choices` / `.choices` | yes | yes |
| `_widget` | yes | yes |
| `_attr_name` | yes | yes |

Attributes that exist only on `SettingDescriptor` (not needed by `prop()`):
`_field_key`, `_mirror_key`, `_panel_visible`, `_stored`, `_read_only`, `_on_change`,
`_validator`, `validate()`, `coerce()`.

---

## 6. Migration Inventory

### 6.1 haywire-core

| File | Class | Change |
|---|---|---|
| `core/settings/builtins/node_instance.py` | `NodeInstanceSettings` | `NodeSettings` → `Reactive`, `setting()` → `prop()` |
| `core/node/base.py` | `NodeData.__init__()` | Remove `schemas['_node']` injection; add `self._props = NodeInstanceSettings()` |
| `core/node/base.py` | `NodeData._to_dict()` | Add `'props': self._props.to_dict()` |
| `core/node/base.py` | `NodeData._initialize_from_dict()` | Handle `'props'` key + old `'_node'` migration |
| `core/node/ui_state.py` | `NodeUI` | `settings._node.X` → `props.X` |
| `core/node/decorator.py` | `_wire_settings_namespace()` | Remove `'_node'` reserved name check |
| `ui/ui_node.py` | `_render()` | `settings._node.skin` → `props.skin` |

### 6.2 App singleton prefs — move from haybale-studio to haywire-core

All 9 classes move from `haybale-studio/settings/` to `haywire/ui/prefs/`,
rewritten from `GlobalSettings` + `setting()` to `Reactive` + `prop()`.
The `@settings` decorator and `GlobalSettingsRegistry` imports are removed.

| Old file (haybale-studio) | New file (haywire-core) | Class(es) | Fields |
|---|---|---|---|
| `settings/debug.py` | `ui/prefs/debug.py` | `DebugSettings` | 13 |
| `settings/editor.py` | `ui/prefs/editor.py` | `EditorSettings` | 16 |
| `settings/execution.py` | `ui/prefs/execution.py` | `ExecutionSettings` | 13 |
| `settings/workbench.py` | `ui/prefs/workbench.py` | `WorkbenchSettings`, `NodeThemeSettings` | 1 + 1 |
| `settings/ui_canvas.py` | `ui/prefs/canvas.py` | `CanvasSettings` | 11 |
| `settings/ui_node.py` | `ui/prefs/node_ui.py` | `NodeUISettings` | 9 |
| `settings/ui_edge.py` | `ui/prefs/edge_ui.py` | `EdgeUISettings` | 9 |
| `settings/ui_minimap.py` | `ui/prefs/minimap.py` | `MinimapSettings` | 6 |

After migration, `haybale-studio/settings/` is deleted (the `__init__.py` is already empty).

### 6.3 haybale-studio panels

Panels stay in haybale-studio but update their imports from `haybale_studio.settings.*`
to `haywire.ui.prefs.*` and switch from `render_schema(cls, registry)` to
`render_reactive(instance)`.

| File | Panel class | Change |
|---|---|---|
| `panels/_settings_panel_base.py` | (shared renderer) | Add `render_reactive()` + `_make_reactive_setter()` |
| `panels/node_properties_panel.py` | `NodeInstanceSettingsPanel` | `render_sub_holder(settings._node)` → `render_reactive(node.node.props)` |
| `panels/settings_debug_panel.py` | `DebugSettingsPanel` | import from `haywire.ui.prefs`, use `render_reactive(injector.get(cls))` |
| `panels/settings_execution_panel.py` | `ExecutionSettingsPanel` | same pattern |
| `panels/settings_app_panels.py` | `WorkbenchSettingsPanel` | same pattern |
| `panels/settings_app_panels.py` | `EditorSettingsPanel` | same pattern |
| `panels/settings_canvas_panels.py` | `CanvasSettingsPanel` | same pattern |
| `panels/settings_canvas_panels.py` | `NodeUISettingsPanel` | same pattern |
| `panels/settings_canvas_panels.py` | `EdgeUISettingsPanel` | same pattern |
| `panels/settings_canvas_panels.py` | `MinimapSettingsPanel` | same pattern |

### 6.4 Tests

| Area | Change |
|---|---|
| New: `tests/core/test_reactive.py` | Unit tests for `prop()`, `Reactive`, serialization |
| Update: `tests/core/test_settings/test_sub_holders.py` | Remove `'_node': NodeInstanceSettings` from test fixtures |
| Update: `tests/core/test_settings/test_descriptors.py` | Remove docstring examples referencing `shadow(NodeUISettings.bg_color)` etc. |
| Update: any test touching `settings._node` | Change to `props.X` |

### 6.5 Documentation

| File | Change |
|---|---|
| `docs/documentation/settings.md/01-overview.md` | Remove `NodeInstanceSettings` from settings architecture; add note about Reactive Props |
| `docs/documentation/settings.md/02-node-development.md` | Update `_node` accessor section to point to `props` |
| `docs/documentation/settings.md/05-reference.md` | Remove `NodeInstanceSettings` reference section |
| `CLAUDE.md` | Add Reactive Props summary |
| New: `docs/documentation/reactive.md` | Full reference for `Reactive` + `prop()` |

---

## 7. Implementation Plan

### Phase 1: Core module (haywire-core)

1. **Create `haywire/core/reactive.py`** — `prop()` descriptor + `Reactive` base class
   (~80 lines). Includes `to_dict()`, `from_dict()`, `subscribe()`, `reset()`,
   `_prop_fields()`.

2. **Write `tests/core/test_reactive.py`** — full unit test coverage:
   - `prop()` default values, class-level returns descriptor, instance-level returns value
   - `__set__` fires callbacks, skips when value unchanged
   - `to_dict()` only includes non-default values
   - `from_dict(silent=True)` restores without callbacks
   - `from_dict(silent=False)` fires callbacks
   - `reset()` / `reset_all()` return to defaults
   - `.choices` property resolves callables
   - `_prop_fields()` walks MRO correctly
   - Inheritance (subclass adds fields, parent fields preserved)

3. **Run tests**, verify green.

### Phase 2: Migrate `NodeInstanceSettings` (haywire-core)

1. **Rewrite `node_instance.py`** — `Reactive` + `prop()` instead of `NodeSettings` + `setting()`.

2. **Update `NodeData.__init__()`** — replace `schemas['_node']` injection with
   `self._props = NodeInstanceSettings()`. Add `props` property.

3. **Update `NodeData._to_dict()` / `_initialize_from_dict()`** — serialize `props`,
   handle old `_node` format migration.

4. **Update `NodeUI`** — all `settings._node.X` → `props.X`.

5. **Update `@node` decorator** — remove `'_node'` reserved accessor check.

6. **Update `ui_node.py`** — `settings._node.skin` → `props.skin`.

7. **Fix affected tests** — update any test referencing `settings._node`.

8. **Run full test suite**, verify green.

### Phase 3: Panel renderer (haybale-studio)

1. **Add `render_reactive()`** to `_settings_panel_base.py` — reuses
   `_render_widget_impl()`.

2. **Update `NodeInstanceSettingsPanel`** — use `render_reactive(node.node.props)`.

3. **Run tests**, verify green.

### Phase 4: Move and migrate app singleton prefs

1. **Create `haywire/ui/prefs/`** package with `__init__.py`.

2. **Move all 9 settings classes** from `haybale_studio/settings/` to
   `haywire/ui/prefs/`, rewriting each from `GlobalSettings` + `setting()` to
   `Reactive` + `prop()`. Remove `@settings` decorator and all
   `GlobalSettingsRegistry` imports. Rename files to match new module names
   (e.g. `ui_canvas.py` → `canvas.py`, `ui_node.py` → `node_ui.py`).

3. **Delete `haybale_studio/settings/`** (entire directory — `__init__.py` is empty,
   all concrete classes have moved).

4. **Register as DI singletons** in `HaywireModule` or app setup.

5. **Update all 7 settings panels** in haybale-studio — change imports from
   `haybale_studio.settings.*` to `haywire.ui.prefs.*`, replace
   `render_schema(Cls, registry)` with `render_reactive(injector.get(Cls))`.

6. **Run full test suite**, verify green.

### Phase 5: Cleanup & docs

1. **Update documentation** — settings overview, node development guide, API reference,
   CLAUDE.md.

2. **Write `docs/documentation/reactive.md`** — standalone reference for the new module.

3. **Clean up imports** — remove unused `GlobalSettings` / `@settings` imports from
   any remaining files. If `GlobalSettings` has no remaining concrete subclasses, add a
   deprecation note (but keep the class — library developers may use it).

---

## 8. Design Decisions

### Why not extend `SettingDescriptor`?

`SettingDescriptor.__get__` raises `AttributeError` on instance access by design — values
are resolved through `SettingsHolder`. `prop()` needs the opposite: direct instance
`__get__`/`__set__`. Sharing a base would create confusing dual semantics. Separate
descriptors with identical metadata attribute names gives panel compatibility without
behavioral coupling.

### Why not add tiers to `Reactive`?

Two-tier resolution (global defaults + workspace overrides) could be added later as an
optional `defaults` dict on `Reactive`. The current design deliberately starts flat —
`from_dict()` with TOML data at startup covers the common case. YAGNI until proven
otherwise.

### Why `props` (not `_node` or `instance_settings`)?

`props` is short, parallels `cache`, `store`, `ui` as a node container namespace, and
avoids the underscore-prefix convention that suggested "private/framework-only." Node
developers will read `self.props.muted` — it should feel like a first-class API.

### Why `Reactive` (not `Observable`)?

"Observable" is overloaded (RxPY, observer pattern). "Reactive" communicates that changes
propagate automatically, aligns with the `prop()` descriptor pattern, and reads naturally
in class definitions: `class DebugSettings(Reactive)`.
