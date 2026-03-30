# API Reference

Complete API documentation for the Haywire settings system.

---

## Enums

### `FieldMode`

```python
from haywire.core.settings import FieldMode

class FieldMode(Enum):
    INHERIT  = auto()  # No opinion — defer to next tier up
    EXPLICIT = auto()  # Deliberate value — wins unless OVERRIDEd
    OVERRIDE = auto()  # Forced — wins over everything below
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

```python
from haywire.core.settings import NodeSettings, field, shadow, watch, Color, Icon
```

### `NodeSettings`

Base class for node-local settings. Declare as an inner class on a `@node` class:

```python
@node(label="My Node")
class MyNode(BaseNode):
    class filter(NodeSettings):
        threshold: float = field(0.5, min=0.0, max=1.0, label='Threshold')
```

`NodeSettings` are never registered with `SettingsRegistry`. The `@node` decorator assigns `_field_key` to each descriptor, and the node instance injects the registry for mirror/watch resolution.

### `field(default=None, *, ...)`

Declare a field on a `NodeSettings`, `FrameworkSettings`, or `LibrarySettings` class.

```python
threshold: float = field(0.5, min=0.0, max=1.0, label='Threshold')
algorithm: str   = field('fast', choices=['fast', 'accurate'])
color:     Color = field('#ffffff', label='Background')
verbose:   bool  = field(False, on_change='hb_on_verbose_change')
```

| Parameter | Type | Description |
| --------- | ---- | ----------- |
| `default` | `Any` | Default value |
| `label` | `str` | Panel display name |
| `description` | `str` | Tooltip text |
| `category` | `str` | Panel grouping |
| `order` | `int` | Sort order within category |
| `min` / `max` | `Any` | Slider bounds |
| `choices` | `list \| dict \| Callable \| None` | Dropdown options |
| `widget` | `str \| None` | Explicit widget hint |
| `on_change` | `str \| None` | Node method name called on change |
| `mirrors` | `FieldDescriptor \| str \| None` | Source descriptor or full key to mirror |
| `read_only` | `bool` | If `True`, instance writes raise `AttributeError` |
| `type_` | `type \| None` | Explicit type (inferred from default if omitted) |
| `stored` | `bool` | If `False`, excluded from serialization |
| `validator` | `Callable \| None` | Called with value; return `False` to reject |
| `metadata` | `dict \| None` | Arbitrary key/value attached to the descriptor (`._metadata`) |

Descriptor attributes (set after construction):

| Attribute | Set by | Description |
| --------- | ------ | ----------- |
| `_attr_name` | `__set_name__` | Python attribute name on the class |
| `_field_key` | `@node` / `namespace=` | Full dot-notation key for TOML resolution |
| `_mirror_key` | `mirrors=` | Full key of the mirrored global field |

#### `choices` — three accepted forms

| Form | Behaviour |
| ---- | --------- |
| `['a', 'b']` | Static list — value shown and stored as-is |
| `{'a': 'Label A', 'b': 'Label B'}` | Dict `{stored_value: display_label}` |
| `lambda: [...]` or `lambda: {...}` | Callable — evaluated at render time |

### `shadow(src, **kwargs) -> field`

Writable mirror of `src`. Inherits `_label`, `_default`, `_type`, `_choices`, `_widget`, `_min`, `_max` from the source. Per-instance writes are allowed and stored in the graph.

```python
bg_color: Color = shadow(NodeUISettings.bg_color)
bg_color: Color = shadow(NodeUISettings.bg_color, label='Node Background')  # override label
bg_color: Color = shadow("ui.node.bg_color")  # raw key form
```

### `watch(src, **kwargs) -> field`

Read-only mirror of `src`. Same inheritance as `shadow()`. Any write attempt raises `AttributeError`. The field is invisible in settings panels and never serialized.

```python
debug_mode: bool = watch(DebugSettings.verbose_logging)
```

---

## `Settings`

```python
from haywire.core.settings import Settings
```

Base class for all settings containers. `NodeSettings`, `FrameworkSettings`, and `LibrarySettings` all inherit from `Settings`.

### `__init__(registry=None)`

- `registry=None` — **simple mode**: reads/writes go directly to `_local_store`. Zero overhead.
- `registry=SettingsRegistry` — **extended mode**: reads go through the full TOML resolution chain.

`FrameworkSettings` and `LibrarySettings` subclasses read `cls._registry` automatically in their `__init__`, so no explicit injection is needed.

### Field access

```python
settings.threshold            # read (simple: local store; extended: resolution chain)
settings.threshold = 0.8      # write local override
```

### `subscribe(callback)` / `unsubscribe(callback)`

`callback(name: str, value: Any, old: Any)` — called on any field change.

### `reset(name: str) -> None`

Remove the local override for `name`. Fires callbacks if the value changes.

### `reset_all() -> None`

Reset all fields.

### `is_locally_set(name: str) -> bool`

Return `True` if `name` has a local instance override.

### `to_dict() -> dict`

Return only fields whose value differs from the descriptor default. `watch()` fields are never included.

### `from_dict(data: dict, *, silent: bool = True) -> None`

Restore values from `data`. Unknown keys silently ignored. `watch()` fields silently skipped.

- `silent=True` (default): writes directly to `_local_store` — no callbacks fired. Used during graph load.
- `silent=False`: uses normal `setattr` — callbacks fire.

### `cleanup() -> None`

Release global namespace subscriptions. Called automatically by `BaseNode` on node removal.

### `_subscribe_mirrors() -> None`

Subscribe cache-invalidation weakrefs for `shadow()`/`watch()` fields. Called automatically by `BaseNode` after settings construction.

### `list_setting_bags()` *(on BaseNode)*

```python
node.list_setting_bags()  # → {'filter': <NodeSettings>, 'output': <NodeSettings>, ...}
```

Returns all user-declared settings instances for this node.

---

## Schema Classes

### `FrameworkSettings`

Base class for framework/app-defined settings.

```python
from haywire.core.settings import FrameworkSettings, field

class ExecutionSettings(FrameworkSettings, namespace='execution'):
    max_threads: int   = field(4,     label='Max Threads')
    timeout_ms:  float = field(5000., label='Timeout (ms)')
```

- `namespace=` kwarg triggers `__init_subclass__` to wire `_field_key` on every descriptor and queue the class in `_pending_global`.
- `SettingsRegistry.__init__` drains `_pending_global` and writes `cls._registry = self`.
- After registration, `ExecutionSettings()` with no args is fully registry-wired.
- Deep inheritance (subclassing a `FrameworkSettings` subclass) is blocked.

### `LibrarySettings`

Base class for library plugin-defined settings. Must be decorated with `@settings`.

```python
from haywire.core.settings import LibrarySettings, field
from haywire.core.settings.decorator import settings

@settings(namespace='my_lib', label='My Library')
class MyLibSettings(LibrarySettings):
    api_url: str = field('https://api.example.com')
```

- `@settings` sets `class_identity` (required by `BaseRegistry._class_filter`), `class_library`, `_namespace`, and `_field_key` on all descriptors. Without it the class is invisible to the hot-reload registry.
- Registration is via `BaseRegistry` hot-reload machinery (inherited by `SettingsRegistry`).
- After registration, `cls._registry` is set and `MyLibSettings()` is fully wired.
- Deep inheritance is blocked.

### `NodeSettings` (schema class)

Base class for node-local settings. See the [Node-Author API](#node-author-api) section above.

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

## `SettingsRegistry`

```python
from haywire.core.settings import SettingsRegistry

# Via DI:
from haywire.core.di.config import get_settings_registry
registry = get_settings_registry()
```

### `register_schema(schema_cls, library_identity=None) -> str | None`

Explicitly register a `FrameworkSettings` or `LibrarySettings` class. Also writes `cls._registry = self`.

### `define(name, default, type_=None, label=None, description='', category='general', metadata=None, **kwargs) -> field`

Programmatically define a setting. `metadata` is stored on the returned `field` descriptor as `._metadata`.

### `has_definition(name) -> bool`

### `get_definition(name) -> field | None`

### `all_definitions() -> dict[str, field]`

### `get_global(name) -> FieldValue`

Returns `FieldValue(mode=INHERIT)` if the key is unknown.

### `set_global(name, value, mode=FieldMode.EXPLICIT) -> None`

### `reset_global(name) -> None`

Reset to `INHERIT`.

### `resolve(name, local=None) -> tuple[Any, str]`

Returns `(value, source)` where source is one of `'global_override'`, `'workspace_override'`, `'local'`, `'workspace'`, `'global'`, `'default'`.

- `local`: optional `FieldValue` representing the per-instance override.

### `load_from_toml(path, tier='workspace', watch=False) -> None`

Load values from a TOML file into the specified tier.

- `tier='global'` — loads into the global tier (`~/.haywire/settings.toml`).
- `tier='workspace'` — loads into the workspace tier (`<workspace>/.haywire/settings.toml`).

### `save_to_toml(path=None) -> None`

### `subscribe_namespace(namespace, weakref_callback) -> None`

Cache-invalidation hook. Called internally by `Settings._subscribe_mirrors()`.

---

## TOML Format

### Simple values (EXPLICIT mode)

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
4. Workspace tier EXPLICIT for full_key? → return it (set via UI, saved to workspace TOML)
    │ No
    ▼
5. Global tier EXPLICIT for full_key?    → return it (user global default)
    │ No
    ▼
6. Descriptor _default                   → return it
```

Settings instances in **simple mode** (no registry) skip steps 1–2 and 4–5.

---

## Next Steps

- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
