# API Reference

Complete API documentation for the Haywire settings system.

---

## Enums

### `SettingMode`

```python
from haywire.core.settings import SettingMode

class SettingMode(Enum):
    AUTO     = "auto"      # No value set; inherit from global or use descriptor default
    SET      = "set"       # Explicitly set at this level
    OVERRIDE = "override"  # (Global only) Force this value on all instances
```

---

## Type Aliases

```python
from haywire.core.settings import Color, Icon

Color = str  # hex/rgba string — implies color-picker widget
Icon  = str  # material icon name — implies icon-picker widget
```

---

## Descriptors

Imported from `haywire.core.settings`.

### `setting(default, *, min=None, max=None, choices=None, widget=None, label='', description='', category='', order=0, on_change='')`

Local node setting. Stored in graph when set. Shown in properties panel.

```python
threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
algorithm: str   = setting('fast', choices=['fast', 'accurate'])
color:     Color = setting('#ffffff', label='Background')
verbose:   bool  = setting(False, on_change='hb_on_verbose_change')
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `_default` | `Any` | Default value |
| `_min` / `_max` | `Any` | Slider bounds |
| `_choices` | `list \| None` | Dropdown options |
| `_widget` | `str \| None` | Explicit widget hint |
| `_label` | `str` | Panel display name |
| `_description` | `str` | Tooltip text |
| `_category` | `str` | Panel grouping |
| `_order` | `int` | Sort order within category |
| `_on_change` | `str` | Node method name to call on change |
| `_panel_visible` | `bool` | `True` |
| `_stored` | `bool` | `True` |
| `_read_only` | `bool` | `False` |
| `_full_key` | `str` | Set by `_SettingsSchema.__init_subclass__` |
| `_attr_name` | `str` | Set by `__set_name__` |

### `shadow(global_descriptor)`

Mirrors a global setting. Inherits global value; per-node override shown with reset affordance. Target must be a `GlobalSettings` or `LibrarySettings` field accessed at class level (returns the descriptor object).

```python
from haywire.core.settings.builtins.ui_node import NodeUISettings

bg_color: Color = shadow(NodeUISettings.bg_color)
```

Stores `global_descriptor._full_key` as a string immediately (object reference discarded for hot-reload safety). Inherits `_label`, `_description`, `_default`, `_category`, `_widget`, `_min`, `_max`, `_choices` from the target descriptor.

| Attribute | Value |
|-----------|-------|
| `_global_key` | Copied from target descriptor `_full_key` |
| `_panel_visible` | `True` |
| `_stored` | `True` (when locally overridden) |
| `_read_only` | `False` |

### `watch(global_descriptor)`

Read-only cached reference to a global setting. Invisible in panel. Never stored. Cache invalidated automatically via namespace subscription when the global value changes.

```python
from haywire.core.settings.builtins.debug import DebugSettings

verbose: bool = watch(DebugSettings.verbose_logging)
```

| Attribute | Value |
|-----------|-------|
| `_global_key` | Copied from target descriptor `_full_key` |
| `_panel_visible` | `False` |
| `_stored` | `False` |
| `_read_only` | `True` |

---

## Schema Classes

### `NodeSettings`

Base class for node `Settings` inner classes.

```python
from haywire.core.settings import NodeSettings

class Settings(NodeSettings):
    threshold: float = setting(0.5)

# Explicit namespace override:
class Settings(NodeSettings, namespace='my_lib.my_node'):
    threshold: float = setting(0.5)

# Pull in extra schemas (flat merge, collision raises ValueError):
class Settings(NodeSettings, extra_schemas=(LibVisualSettings,)):
    threshold: float = setting(0.5)
```

`_namespace` and `_full_key` on each descriptor are set by the `@node` decorator. The namespace is derived from the node's `registry_key` by replacing `:` with `.` — e.g. `haybale_core:node:transform` → `haybale_core.node.transform`.

### `LibrarySettings`

Base class for library-wide settings.

```python
from haywire.core.settings import LibrarySettings
from haywire.core.settings.decorators import library_settings

@library_settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    api_url: str = setting('https://api.example.com')
```

Must be decorated with `@library_settings`. `_full_key` is set at class definition time.

### `GlobalSettings`

Base class for built-in framework-wide settings.

```python
from haywire.core.settings import GlobalSettings

class MyGlobalSettings(GlobalSettings, namespace='my_ns'):
    some_option: bool = setting(False)
```

Registered explicitly via `registry.register_schema(cls)`.

---

## Decorators

### `@library_settings(namespace, label='')`

```python
from haywire.core.settings.decorators import library_settings, SettingsClassIdentity

@library_settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    ...
```

Sets on the class:
- `class_identity: SettingsClassIdentity` — `namespace`, `registry_key`, `label`
- `_namespace: str`
- `_auto_register: bool = True`
- `_full_key` on each descriptor field

---

## `GlobalSettingsRegistry`

```python
from haywire.core.settings import GlobalSettingsRegistry

# Via DI:
from haywire.core.di.config import get_settings_registry
registry = get_settings_registry()
```

### `register_schema(schema_cls, library_identity=None) -> str | None`

Register a `GlobalSettings` or `LibrarySettings` class. Creates a synthetic `class_identity` from `_namespace` if not present.

### `define(name, default, type_=None, label=None, description='', category='general', **kwargs) -> GlobalSettingsRegistry`

Programmatically define a setting. Returns `self` for chaining.

### `has_definition(name) -> bool`

### `get_definition(name) -> SettingDefinition | None`

### `all_definitions() -> dict[str, SettingDefinition]`

### `definitions_by_category() -> dict[str, list[SettingDefinition]]`

### `get_global(name) -> SettingValue`

Returns `SettingValue(mode=AUTO)` if the key is unknown.

### `set_global(name, value, mode=SettingMode.SET) -> None`

### `reset_global(name) -> None`

Reset to `AUTO`.

### `resolve(name) -> tuple[Any, str]`

Returns `(value, source)` where source is `'global'` or `'default'`.

### `load_from_toml(path, tier='workspace', watch=False) -> None`

Load values from a TOML file into the specified tier.
- `tier='global'` — loads into the global tier (`~/.haywire/settings.toml`, hand-edited by user).
- `tier='workspace'` — loads into the workspace tier (`<workspace>/.haywire/settings.toml`, written by UI).

### `save_to_toml(path=None) -> None`

### `subscribe_namespace(namespace, weakref_callback) -> None`

Option B invalidation. Callback is called with `(full_key: str)` when any key under `namespace` changes.

---

## `ResolutionChain`

```python
from haywire.core.settings.chain import ResolutionChain
```

Internal four-tier value resolver used by `SettingsHolder`.  Most code never needs to import this directly.

### `resolve(full_key, default) -> Any`

Resolution priority:

1. Global `OVERRIDE` → return global value
2. Local dict has key → return local value
3. Global `SET` → return global value
4. Return `default`

### `has_local / get_local / set_local / clear_local`

Direct access to the per-instance local store.

---

## `NodeInstanceSettings`

```python
from haywire.core.settings.builtins.node_instance import NodeInstanceSettings
```

A `NodeSettings` subclass with `namespace='node'` that is automatically injected into every node's `SettingsHolder` as an extra schema.  Node developers never instantiate this directly — it is just always present.

Fields: `skin`, `muted`, `collapsed`, `condensed`, `pinned`, `color_override`, `comment`, `show_comment`.
Full keys: `node.skin`, `node.muted`, … (see Overview for full table).

---

## `SettingsHolder`

```python
from haywire.core.settings import SettingsHolder

holder = SettingsHolder(schema_cls, registry, node_instance, extra_schemas=())
```

`extra_schemas` is a tuple of additional `_SettingsSchema` subclasses whose fields are merged in before the primary `schema_cls`. `NodeData.__init__` always prepends `NodeInstanceSettings` and then appends any schemas declared via `extra_schemas=(...)` on the inner `Settings` class.

Field merge order: extra schemas first (in declaration order), then primary `schema_cls`. A `ValueError` is raised on any attr-name collision — there is no silent overwrite.

### Field access

```python
# By schema attr name (preferred) — works for fields from any merged schema
value = holder.threshold        # node-class field
value = holder.muted            # NodeInstanceSettings field
value = holder['threshold']

# By full key — also works
value = holder['my_lib.my_node.threshold']
value = holder['node.muted']

# Get with default
value = holder.get('threshold', 0.5)

# Check containment
'threshold' in holder
'node.muted' in holder   # by full key
```

### `set(name, value, mode=SettingMode.SET) -> None`

`name` is the attr name or full key. Raises `AttributeError` if the field is `watch()` (read-only).

### `reset(name) -> None`

Reset to `AUTO` (inherit from global/default).

### `reset_all() -> None`

### `get_info(name) -> SettingInfo`

`name` is the attr name or full key. Returns full resolution info for UI display.

### `is_locally_set(name) -> bool`

### `on_change(callback) -> None`

`callback(name: str, value: Any, source: str)` — called when a local value is set.

### `remove_callback(callback) -> None`

### `to_dict() -> dict`

```python
{
    'schema_values': {attr_name: value, ...},   # all locally-overridden fields (both
}                                               #   node-class and NodeInstanceSettings)
```

### `from_dict(data) -> None`

Restore serialized state.  Also handles migration from the previous legacy-bridge format
(old `legacy_values` dict with `node.X` full-key entries is automatically mapped to the
corresponding `NodeInstanceSettings` attr names).

### `cleanup() -> None`

Release namespace subscriptions. Call from `NodeWrapper` on node removal.

---

## `SettingInfo`

Returned by `holder.get_info(attr_name)`.

```python
@dataclass
class SettingInfo:
    name:        str           # attr name
    value:       Any           # resolved value
    source:      str           # 'global_override' | 'local' | 'global' | 'default'
    is_overridden: bool        # True when global OVERRIDE is active
    is_inherited:  bool        # True when source is 'global' or 'default'
    local_mode:  SettingMode
    local_value: Any | None
    global_mode: SettingMode
    global_value: Any | None
    definition:  SettingDefinition
```

---

## TOML Format

### Simple values (SET mode)

```toml
[ui.node]
bg_color  = "#ffffff"
font_size = 12

[debug]
verbose_logging = false
```

### Override values

```toml
[ui.node]
font_size = { override = true, value = 14 }
```

---

## Resolution Algorithm

```
self.settings.threshold
    │
    ▼
1. Global tier OVERRIDE for full_key?    → return it (admin policy, hand-edited TOML)
    │ No
    ▼
2. Workspace tier OVERRIDE for full_key? → return it (workspace-wide force)
    │ No
    ▼
3. Local value in chain._local?          → return it (per-node override)
    │ No
    ▼
4. Workspace tier SET for full_key?      → return it (set via UI, saved to workspace TOML)
    │ No
    ▼
5. Global tier SET for full_key?         → return it (user global default)
    │ No
    ▼
6. Descriptor _default                   → return it
```

---

## Next Steps

- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
