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

## Node-Author API

Imported from `haywire.core.settings`.

```python
from haywire.core.settings import Settings, setting, Color, Icon
```

### `setting(default, *, min=None, max=None, choices=None, widget=None, label='', description='', category='general', order=0, on_change=None, mirrors=None, read_only=False)`

Declare a field on a `Settings` inner class.

```python
threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
algorithm: str   = setting('fast', choices=['fast', 'accurate'])
color:     Color = setting('#ffffff', label='Background')
verbose:   bool  = setting(False, on_change='hb_on_verbose_change')

# mirrors= — inherit from a GlobalSettings or LibrarySettings field
bg_color:  Color = setting(mirrors=NodeUISettings.bg_color)

# mirrors= + read_only= — read-only global cache (invisible in panel)
debug:     bool  = setting(mirrors=DebugSettings.verbose_logging, read_only=True)
```

| Attribute | Type | Description |
| --------- | ---- | ----------- |
| `_default` | `Any` | Default value |
| `_min` / `_max` | `Any` | Slider bounds |
| `_choices` | `list \| dict \| Callable \| None` | Dropdown options |
| `_widget` | `str \| None` | Explicit widget hint |
| `_label` | `str` | Panel display name |
| `_description` | `str` | Tooltip text |
| `_category` | `str` | Panel grouping |
| `_order` | `int` | Sort order within category |
| `_on_change` | `str \| None` | Node method name called on change |
| `_mirror_key` | `str` | Full key of the mirrored global field (set from `mirrors=`) |
| `_read_only` | `bool` | If `True`, instance writes raise `AttributeError` |
| `_field_key` | `str` | Set by `@node` decorator; used for TOML resolution |
| `_attr_name` | `str` | Set by `__set_name__` |

#### `choices` — three accepted forms

| Form | Behaviour |
| ---- | --------- |
| `['a', 'b']` | Static list — value shown and stored as-is |
| `{'a': 'Label A', 'b': 'Label B'}` | Dict `{stored_value: display_label}` |
| `lambda: [...]` or `lambda: {...}` | Callable — evaluated at render time |

---

## `Settings`

```python
from haywire.core.settings import Settings
```

### `__init__(registry=None)`

- `registry=None` — **simple mode**: reads/writes go directly to `_local_store`. Zero overhead. Used for standalone settings instances and `NodeProperties`.
- `registry=GlobalSettingsRegistry` — **extended mode**: reads go through the full TOML resolution chain. Injected automatically by `@node`/`BaseNode`.

### Field access

```python
settings.threshold            # read (simple: local store; extended: resolution chain)
settings.threshold = 0.8      # write local override
```

### `subscribe(callback)` / `unsubscribe(callback)`

`callback(name: str, value: Any, old: Any)` — called on any field change.

### `reset(name: str) -> None`

Remove the local override for `name`, restoring it to the default (or global value in extended mode). Fires callbacks if the value changes.

### `reset_all() -> None`

Reset all fields.

### `is_locally_set(name: str) -> bool`

Return `True` if `name` has a local instance override.

### `to_dict() -> dict`

Return only fields whose value differs from the descriptor default. `read_only` fields are never included.

### `from_dict(data: dict, *, silent: bool = True) -> None`

Restore values from `data`. Unknown keys are silently ignored. `read_only` fields are silently skipped.

- `silent=True` (default): writes directly to `_local_store` — no callbacks fired. Used during graph load.
- `silent=False`: uses normal `setattr` — callbacks fire.

### `cleanup() -> None`

Release global namespace subscriptions. Called automatically by `BaseNode` on node removal.

### `_subscribe_mirrors() -> None`

Subscribe cache-invalidation weakrefs for `mirrors=` fields. Called automatically by `BaseNode` after settings construction.

### `list_setting_bags()` *(on BaseNode)*

```python
node.list_setting_bags()  # → {'filter': <Settings>, 'output': <Settings>, ...}
```

Returns all user-declared settings instances for this node. Used by panels to discover what to render.

---

## Schema Classes

### `LibrarySettings`

Base class for library-wide settings.

```python
from haywire.core.settings import LibrarySettings
from haywire.core.settings.decorator import settings

@settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    api_url: str = setting('https://api.example.com')
```

Must be decorated with `@settings`. `_field_key` is set at class definition time.

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

### `@settings(namespace, label='')`

```python
from haywire.core.settings.decorator import settings

@settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    ...
```

Sets on the class:

- `class_identity: SettingsClassIdentity` — `namespace`, `registry_key`, `label`
- `_namespace: str`
- `_auto_register: bool = True`
- `_field_key` on each descriptor field

---

## `GlobalSettingsRegistry`

```python
from haywire.core.settings import GlobalSettingsRegistry

# Via DI:
from haywire.core.di.config import get_settings_registry
registry = get_settings_registry()
```

### `register_schema(schema_cls, library_identity=None) -> str | None`

Register a `GlobalSettings` or `LibrarySettings` class.

### `define(name, default, type_=None, label=None, description='', category='general', **kwargs) -> setting`

Programmatically define a setting.

### `has_definition(name) -> bool`

### `get_definition(name) -> setting | None`

### `all_definitions() -> dict[str, setting]`

### `get_global(name) -> SettingValue`

Returns `SettingValue(mode=AUTO)` if the key is unknown.

### `set_global(name, value, mode=SettingMode.SET) -> None`

### `reset_global(name) -> None`

Reset to `AUTO`.

### `resolve(name, local=None) -> tuple[Any, str]`

Returns `(value, source)` where source is `'global'`, `'local'`, or `'default'`.

- `local`: optional `SettingValue` representing the per-instance override (passed by `Settings._resolve()`).

### `load_from_toml(path, tier='workspace', watch=False) -> None`

Load values from a TOML file into the specified tier.

- `tier='global'` — loads into the global tier (`~/.haywire/settings.toml`).
- `tier='workspace'` — loads into the workspace tier (`<workspace>/.haywire/settings.toml`).

### `save_to_toml(path=None) -> None`

### `subscribe_namespace(namespace, weakref_callback) -> None`

Cache-invalidation hook. Callback is called with `(full_key: str)` when any key under `namespace` changes. Used internally by `Settings._subscribe_mirrors()`.

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

```text
self.filter.threshold
    │
    ▼
1. Global tier OVERRIDE for full_key?    → return it (admin policy, hand-edited TOML)
    │ No
    ▼
2. Workspace tier OVERRIDE for full_key? → return it (workspace-wide force)
    │ No
    ▼
3. Local value in settings._local_store? → return it (per-node override)
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

Settings instances in **simple mode** (no registry) skip steps 1–2 and 4–5.

---

## Next Steps

- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
