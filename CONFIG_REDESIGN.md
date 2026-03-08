# Haywire Configuration System Redesign
## Implementation Specification

**Branch:** `code_refactoring`
**Status:** Ready to implement — no backward compatibility required.

---

## Context for New Claude Session

Read these files first to understand the existing codebase before implementing:

```
packages/haywire-framework/src/haywire/core/settings/registry.py   — existing GlobalSettingsRegistry
packages/haywire-framework/src/haywire/core/settings/holder.py      — existing SettingsHolder
packages/haywire-framework/src/haywire/core/settings/definition.py  — SettingDefinition dataclass
packages/haywire-framework/src/haywire/core/settings/enums.py       — SettingMode, SettingScope
packages/haywire-framework/src/haywire/core/settings/value.py       — SettingValue dataclass
packages/haywire-framework/src/haywire/core/settings/builtins/ui_node.py — example builtin (to be replaced)
packages/haywire-framework/src/haywire/core/di/config.py            — DI wiring (HaywireModule)
packages/haywire-framework/src/haywire/ui/themes/palette.py         — ThemePalette (to be replaced)
packages/haywire-framework/src/haywire/ui/themes/base.py            — BaseTheme, TOMLTheme
packages/haywire-framework/src/haywire/ui/themes/builtin.py         — DefaultTheme, DarkTheme
packages/haywire-framework/src/haywire/ui/themes/keys.py            — ThemeKey enum
packages/haywire-framework/src/haywire/ui/app_shell.py              — CSS var block (hw-* tokens)
packages/haywire-framework/src/haywire/core/library/base.py         — BaseLibrary
tests/core/test_settings/test_settings.py                           — existing settings tests
docs/documentation/settings.md/01-overview.md                       — existing settings docs
```

---

## Goals

1. Replace procedural `registry.define()` / `self.settings.define()` with class-based, descriptor-driven schemas
2. Add `shadow()` and `watch()` descriptors for typed, cached global setting references
3. Add project-level settings tier (`<project>/.haywire/settings.toml`)
4. Replace `ThemePalette` with two typed registries: `SettingsRegistry` (extended) and `ThemeRegistry` (new)
5. Wire `GlobalSettingsRegistry` → `SettingsHolder` cache invalidation via namespace subscription (Option B: holders subscribe to specific namespaces via weakref)
6. Use decorator pattern (`@library_settings`, `@node_theme`, `@workbench_theme`) consistent with `@node`, `@editor`, `@panel`

---

## Shared Type Aliases

Add to `packages/haywire-framework/src/haywire/core/settings/types.py` (new file):

```python
# Type aliases for descriptor annotations — purely for IDE hinting.
# At runtime these are just str.
Color = str   # hex or rgba string, implies color-picker widget
Icon  = str   # material icon name, implies icon-picker widget
```

Import these in all schema classes and node Settings inner classes.

---

## New API at a Glance

```python
# ── Library-level global settings ──────────────────────────────────────────
@library_settings(namespace='my_lib')
class MyLibSettings(LibrarySettings):
    bg_color:     Color = setting('#1e1e2e', label='Node Background')
    accent_color: Color = setting('#4f8ef7', label='Accent Color')
    max_iter:     int   = setting(100, min=1, max=10000, label='Max Iterations')

# ── Library themes ──────────────────────────────────────────────────────────
@node_theme(id='my-lib-dark')
class MyLibDarkTheme(NodeTheme):
    canvas_bg: Color = '#1e1e2e'
    node_bg:   Color = 'rgba(30,30,30,0.9)'

@workbench_theme(id='haywire-dark')
class HaywireDarkTheme(WorkbenchTheme):
    bg_page:    Color = '#12121e'
    bg_surface: Color = '#1e1e2e'
    text_body:  Color = 'rgba(255,255,255,0.87)'
    text_muted: Color = 'rgba(255,255,255,0.55)'
    text_dim:   Color = 'rgba(255,255,255,0.6)'
    accent:     Color = '#4f8ef7'
    border:     Color = '#333333'

# ── Node settings ───────────────────────────────────────────────────────────
@node(label='My Node')
class MyNode(BaseNode):

    class Settings(NodeSettings):
        # LOCAL — stored with graph, shown in properties panel
        threshold: float = setting(0.5, min=0.0, max=1.0, label='Threshold')
        mode: Literal['fast', 'accurate'] = setting('fast', label='Mode',
                                                      on_change='hb_on_mode_changed')

        # SHADOW — mirrors a global; inherits global value; per-node override
        #          stored in graph only when overridden; shown in panel with reset affordance
        bg_color: Color = shadow(MyLibSettings.bg_color)

        # WATCH — read-only cached reference to a global; NOT shown in panel; NOT stored in graph
        verbose: bool = watch(DebugSettings.verbose_logging)

    def initialize(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        self.store.count = 0

    def worker(self, context, value: float):
        if self.settings.verbose:                     # watch — cached, fast
            context.log(f'value={value}')
        result = value * self.settings.threshold      # setting — cached
        bg = self.settings.bg_color                   # shadow — cached
        self.out('result', result)

    def hb_on_mode_changed(self, value, field: str = ''):
        self.cache.needs_rebuild = True
```

---

## Descriptor Design

### `packages/haywire-framework/src/haywire/core/settings/descriptors.py` (new)

All three descriptors share a `_SettingDescriptor` base:

```python
class _SettingDescriptor:
    # Set by __set_name__ (Python calls this automatically when class body is evaluated)
    _attr_name:    str   = ''     # attribute name on the Settings class
    _full_key:     str   = ''     # 'namespace.attr_name' — set by __init_subclass__

    # Set by constructor
    _default:      Any   = None
    _label:        str   = ''
    _description:  str   = ''
    _category:     str   = ''
    _order:        int   = 0
    _on_change:    str   = ''     # method name string on the node instance

    # Flags used by serializer and panel introspection
    _panel_visible: bool = True   # show in properties panel?
    _stored:        bool = True   # serialize in graph file?
    _read_only:     bool = False  # prevent local override?

    def __set_name__(self, owner, name):
        self._attr_name = name
        # _full_key set later by __init_subclass__ once namespace is known

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self   # class-level access → returns descriptor (typed key handle)
        raise AttributeError(
            f"Access '{name}' via self.settings.{name}, not self.{name}"
        )
```

#### `setting(default, *, min=None, max=None, choices=None, widget=None, label='', description='', category='', order=0, on_change='')`

```python
class setting(_SettingDescriptor):
    _panel_visible = True
    _stored        = True
    _read_only     = False
    # Additional: _min, _max, _choices, _widget (for UI widget inference)
```

Widget inference (used by properties panel, no explicit widget needed in most cases):

| Type annotation | Inferred widget |
|---|---|
| `bool` | toggle |
| `int` with min+max | slider |
| `int` without | number input |
| `float` with min+max | slider |
| `Color` | color picker |
| `Icon` | icon picker |
| `Literal[...]` | dropdown |
| `str` | text input |

#### `shadow(global_descriptor)`

```python
class shadow(_SettingDescriptor):
    _panel_visible = True    # shown with "reset to global" affordance
    _stored        = True    # stored in graph ONLY when locally overridden
    _read_only     = False

    def __init__(self, global_descriptor: _SettingDescriptor):
        # Store string key immediately — robust to partial hot-reload.
        # global_descriptor._full_key is available because LibrarySettings/GlobalSettings
        # set _full_key at their own __init_subclass__ time (before node class is evaluated).
        self._global_key = global_descriptor._full_key
        # Inherit label, description, category, widget from global descriptor
        self._label       = global_descriptor._label
        self._description = global_descriptor._description
        self._default     = global_descriptor._default
```

#### `watch(global_descriptor)`

```python
class watch(_SettingDescriptor):
    _panel_visible = False   # invisible in properties panel
    _stored        = False   # never serialized
    _read_only     = True    # cannot be overridden locally

    def __init__(self, global_descriptor: _SettingDescriptor):
        self._global_key = global_descriptor._full_key
        self._default    = global_descriptor._default
```

---

## Schema Base Classes

### `packages/haywire-framework/src/haywire/core/settings/schema.py` (new)

```python
class _SettingsSchema:
    """Shared base: collects _SettingDescriptor fields via __init_subclass__."""
    _fields: ClassVar[dict[str, _SettingDescriptor]]   # populated by __init_subclass__
    _namespace: ClassVar[str] = ''

    def __init_subclass__(cls, namespace: str = '', **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect all setting descriptors from this class's own __dict__
        cls._fields = {}
        for name, val in cls.__dict__.items():
            if isinstance(val, _SettingDescriptor):
                # __set_name__ already called by Python — _attr_name is set
                cls._fields[name] = val
        # Set _namespace and _full_key when namespace kwarg is given.
        # class_identity is NOT set here — that is always the decorator's job.
        if namespace:
            cls._namespace = namespace
            for name, descriptor in cls._fields.items():
                descriptor._full_key = f'{namespace}.{name}'


class NodeSettings(_SettingsSchema):
    """Marker for node-local settings schemas (inner class on BaseNode subclasses)."""
    # _namespace and _full_key set by BaseNode.__init_subclass__ after outer class is known
    # No class_identity — NodeSettings are never registered with GlobalSettingsRegistry


class LibrarySettings(_SettingsSchema):
    """
    Library-global settings. Must be decorated with @library_settings to be
    registered with GlobalSettingsRegistry (decorator sets class_identity).
    The namespace= kwarg on the class line is optional — @library_settings
    sets it authoritatively.
    """


class GlobalSettings(_SettingsSchema):
    """
    Framework built-in settings (replaces builtins/ui_node.py etc.).
    namespace= kwarg required. No decorator needed — register_schema()
    creates class_identity from _namespace at registration time.
    Registered explicitly via register_schema() in builtins/__init__.py,
    not via folder scan.
    """
```

---

## `_full_key` Timing — Critical Ordering

This ordering ensures `shadow(MyLibSettings.bg_color)` always works:

```
1. MyLibSettings class body evaluated
   → LibrarySettings.__init_subclass__ runs
   → namespace known from kwarg → _full_key set on all descriptors immediately
   → MyLibSettings.bg_color._full_key = 'my_lib.bg_color'  ✓ available now

2. MyNode class body evaluated
   → class Settings(NodeSettings): ... evaluated
     → NodeSettings.__init_subclass__ runs
     → _fields collected, __set_name__ called
     → shadow(MyLibSettings.bg_color) called:
         → MyLibSettings.bg_color returns the descriptor (class-level __get__)
         → descriptor._full_key is already 'my_lib.bg_color' ✓
         → shadow stores 'my_lib.bg_color' as string — object reference discarded
   → BaseNode.__init_subclass__ runs (outer class)
     → cls.__dict__.get('Settings') found
     → namespace derived from MyNode
     → _full_key set on NodeSettings descriptors: 'my_lib.my_node.threshold' etc.

3. SettingsHolder created per node instance
   → Resolves watch()/shadow() targets by string key via registry — no object reference
```

---

## Namespace Derivation Algorithm

For `NodeSettings` inner classes, derived by `BaseNode.__init_subclass__`:

```python
import re

def _derive_namespace(cls) -> str:
    # Top-level library package = first segment of module path
    pkg = cls.__module__.split('.')[0]           # e.g. 'haybale_vision'
    # Class name → snake_case, strip common suffixes
    name = cls.__name__
    for suffix in ('Node', 'Processor', 'Generator', 'Filter'):
        if name.endswith(suffix) and len(name) > len(suffix):
            name = name[:-len(suffix)]
            break
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()  # CamelCase → snake_case
    return f'{pkg}.{snake}'   # e.g. 'haybale_vision.signal_processor'
```

Can be overridden explicitly:
```python
class Settings(NodeSettings, namespace='my_custom.ns'):
    ...
```

---

## SettingsHolder

### `packages/haywire-framework/src/haywire/core/settings/holder.py` (rewrite)

```python
import weakref
from typing import Any

class SettingsHolder:
    def __init__(self, schema_cls, chain, node_instance):
        self._schema        = schema_cls
        self._chain         = chain          # ResolutionChain instance
        self._node          = node_instance
        self._cache: dict[str, Any] = {}
        # Reverse map: full_key → attr_name (for targeted invalidation)
        self._key_to_name: dict[str, str] = {
            d._full_key: name
            for name, d in schema_cls._fields.items()
            if d._full_key
        }
        # Resolve on_change method names → actual methods
        self._callbacks: dict[str, Callable] = {}
        for name, d in schema_cls._fields.items():
            if d._on_change:
                method = getattr(node_instance, d._on_change, None)
                if method is None:
                    logger.warning(f"on_change '{d._on_change}' not found on {type(node_instance).__name__}")
                else:
                    self._callbacks[name] = method
        # Subscribe to namespaces of watch() and shadow() targets (Option B)
        self._subscribe_to_global_namespaces()

    def __getattr__(self, name: str) -> Any:
        if name.startswith('_'):
            raise AttributeError(name)
        try:
            return self._cache[name]
        except KeyError:
            pass
        descriptor = self._schema._fields.get(name)
        if descriptor is None:
            raise AttributeError(f"No setting '{name}' in {self._schema.__name__}")
        value = self._chain.resolve(descriptor._full_key, descriptor._default)
        self._cache[name] = value
        return value

    def get(self, descriptor_or_str, default=None) -> Any:
        """Uncached access for escape-hatch reads (settings.get(Global.key))."""
        key = descriptor_or_str._full_key if isinstance(descriptor_or_str, _SettingDescriptor) else descriptor_or_str
        return self._chain.resolve(key, default)

    def is_locally_set(self, name: str) -> bool:
        """True if this node has a local override for the named field (for panel reset affordance)."""
        descriptor = self._schema._fields.get(name)
        if descriptor is None:
            return False
        return self._chain.has_local(descriptor._full_key)

    def _invalidate(self, full_key: str) -> None:
        """Called by GlobalSettingsRegistry namespace subscriber on schema update."""
        name = self._key_to_name.get(full_key)
        if name:
            self._cache.pop(name, None)
            # Fire on_change callback if registered
            if name in self._callbacks:
                new_value = self.__getattr__(name)  # re-resolve and re-cache
                try:
                    self._callbacks[name](new_value, name)
                except TypeError:
                    self._callbacks[name](new_value)  # fallback: no field arg

    def _subscribe_to_global_namespaces(self) -> None:
        """Subscribe to namespaces of all shadow() and watch() fields (Option B)."""
        global_registry = ...  # injected or accessed via DI
        watched_keys = {
            d._full_key
            for d in self._schema._fields.values()
            if isinstance(d, (shadow, watch)) and d._full_key
        }
        for key in watched_keys:
            namespace = key.rsplit('.', 1)[0]
            global_registry.subscribe_namespace(
                namespace,
                weakref.WeakMethod(self._invalidate)
            )

    # ── Serialization support ──────────────────────────────────────────────

    def get_serializable(self) -> dict:
        """Return only locally-set values for fields where _stored=True."""
        result = {}
        for name, d in self._schema._fields.items():
            if not d._stored:
                continue
            if self._chain.has_local(d._full_key):
                result[name] = self._chain.get_local(d._full_key)
        return result

    def load_serialized(self, data: dict) -> None:
        """Restore locally-set values from graph file."""
        for name, value in data.items():
            descriptor = self._schema._fields.get(name)
            if descriptor and descriptor._stored:
                self._chain.set_local(descriptor._full_key, value)
                self._cache.pop(name, None)   # invalidate cache entry
```

---

## Resolution Chain

### `packages/haywire-framework/src/haywire/core/settings/chain.py` (new)

```python
class ResolutionChain:
    """
    Resolves a setting key through four tiers:
      1. Global OVERRIDE  — forced, wins over everything
      2. Local SET        — per-node override stored in graph
      3. Project SET      — from <project>/.haywire/settings.toml
      4. Global SET       — from ~/.haywire/settings.toml
      5. Schema default   — fallback
    """
    def __init__(self, local_store: dict, global_registry: GlobalSettingsRegistry):
        self._local:  dict[str, Any] = local_store    # per-node mutable dict
        self._global: GlobalSettingsRegistry = global_registry

    def resolve(self, full_key: str, default: Any) -> Any:
        # Tier 1: Global OVERRIDE
        global_val = self._global.get_global(full_key)
        if global_val.mode == SettingMode.OVERRIDE:
            return global_val.value
        # Tier 2: Local SET
        if full_key in self._local:
            return self._local[full_key]
        # Tier 3 & 4: Global resolution (project tier is inside GlobalSettingsRegistry)
        if global_val.mode == SettingMode.SET:
            return global_val.value
        # Tier 5: Default
        return default

    def has_local(self, full_key: str) -> bool:
        return full_key in self._local

    def get_local(self, full_key: str) -> Any:
        return self._local.get(full_key)

    def set_local(self, full_key: str, value: Any) -> None:
        self._local[full_key] = value

    def clear_local(self, full_key: str) -> None:
        self._local.pop(full_key, None)
```

**Project tier integration in `GlobalSettingsRegistry`:**
`provide_settings_registry()` in `di/config.py` loads TOML in order:
1. `~/.haywire/settings.toml` — global
2. `<project_root>/.haywire/settings.toml` — project (loaded second, wins over global for SET)

Both use the existing `load_from_toml()` with an `append=True` mode so project values shadow global ones.

---

## GlobalSettingsRegistry: BaseRegistry + Namespace Subscription (Option B)

`GlobalSettingsRegistry` now extends `BaseRegistry`, giving it hot-reload support,
folder scanning, and compatibility with `LibraryRegistry.add_class_registry()`.

The three abstract methods manage `LibrarySettings` / `GlobalSettings` schema classes.
All existing value-management logic (`define()`, `get_global()`, `resolve()`, TOML I/O,
listeners, file watcher) is kept as-is — it lives alongside the BaseRegistry machinery.

### New class signature

```python
# packages/haywire-framework/src/haywire/core/settings/registry.py

import inspect
from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity
from .schema import LibrarySettings, GlobalSettings

class GlobalSettingsRegistry(BaseRegistry):
    """
    Central registry for setting definitions and global values.

    Extends BaseRegistry: supports hot-reload, folder scanning, lifecycle events,
    dependency tracking, and snapshot rollback.

    Registered with LibraryRegistry via:
        library_registry.add_class_registry(GlobalSettingsRegistry, settings_registry)

    Libraries add their settings folder in register_components():
        settings_registry.add_folder(path, library_identity)

    When a LibrarySettings module is hot-reloaded, event_dispatcher() (inherited
    from BaseRegistry) calls _on_change() → _reload_managed_module() →
    _unregister_class() then _register_class(), which removes old defines and
    re-registers the new schema — SettingsHolder namespace subscribers fire
    automatically via _notify_namespace_subscribers().
    """

    def __init__(self):
        super().__init__()   # initialises BaseRegistry state
        # --- existing GlobalSettingsRegistry state ---
        self._lock = threading.RLock()
        self._definitions: dict[str, SettingDefinition] = {}
        self._global_values: dict[str, SettingValue] = {}
        self._listeners: list[Callable[[str, SettingValue], None]] = []
        self._categories: dict[str, list[str]] = {}
        self._toml_defined: set[str] = set()
        self._config_path: Path | None = None
        self._observer = None
        self._file_watch_enabled = False
        # --- namespace subscription (Option B) ---
        self._namespace_subscribers: dict[str, list[weakref.ref]] = {}

    # ── BaseRegistry abstract methods ────────────────────────────────────────

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, (LibrarySettings, GlobalSettings))
                and cls not in (LibrarySettings, GlobalSettings)
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> 'str | None':
        """Register a settings schema class and define all its fields."""
        registry_key = cls.class_identity.registry_key
        self._register_schema_fields(cls)
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> 'type | None':
        """Unregister a settings schema and remove all its field definitions."""
        removed_cls = super()._unregister(registry_key)
        if removed_cls is not None:
            self._unregister_schema_fields(removed_cls)
        return removed_cls

    # ── Schema field management ──────────────────────────────────────────────

    def _register_schema_fields(self, schema_cls: type) -> None:
        """Called by _register_class. Replaces manual define() calls."""
        for name, descriptor in schema_cls._fields.items():
            self.define(
                name        = descriptor._full_key,
                default     = descriptor._default,
                label       = descriptor._label,
                description = descriptor._description,
                category    = getattr(descriptor, '_category', None) or schema_cls._namespace,
                min_value   = getattr(descriptor, '_min', None),
                max_value   = getattr(descriptor, '_max', None),
                choices     = getattr(descriptor, '_choices', None),
                ui_widget   = getattr(descriptor, '_widget', None),
                ui_order    = descriptor._order,
            )

    def _unregister_schema_fields(self, schema_cls: type) -> None:
        """Remove all field definitions belonging to this schema."""
        changed_keys = set()
        for name, descriptor in schema_cls._fields.items():
            key = descriptor._full_key
            self._definitions.pop(key, None)
            self._global_values.pop(key, None)
            self._toml_defined.discard(key)
            for cat_names in self._categories.values():
                if key in cat_names:
                    cat_names.remove(key)
            changed_keys.add(key)
        if changed_keys:
            self._notify_namespace_subscribers(changed_keys)
```

### `register_schema()` — explicit registration for built-in GlobalSettings

Built-in `GlobalSettings` classes live inside the framework package, not in a library
folder, so they cannot be discovered via `add_folder()`. They are registered explicitly
from `builtins/__init__.py`.

`GlobalSettings` subclasses need no decorator. `register_schema()` creates
`class_identity` from `_namespace` at registration time, then delegates to
`_register_class()`.

```python
# builtins/ui_node.py  — no decorator, just namespace= kwarg
class NodeUISettings(GlobalSettings, namespace='ui.node'):
    bg_color: Color = setting('#ffffff', label='Background Color')
```

```python
# builtins/__init__.py
from haywire.core.library.identity import LibraryIdentity
from haywire.core.settings.decorators import SettingsClassIdentity

FRAMEWORK_IDENTITY = LibraryIdentity(
    id          = 'haywire.framework',
    label       = 'Haywire Framework',
    module_name = 'haywire',
    folder_path = '',   # no folder scan — explicit registration only
)

def register_builtin_settings(registry: GlobalSettingsRegistry) -> None:
    from .ui_node   import NodeUISettings
    from .ui_edge   import EdgeUISettings
    from .ui_canvas import CanvasUISettings
    # ... etc.
    for schema_cls in [NodeUISettings, EdgeUISettings, CanvasUISettings, ...]:
        registry.register_schema(schema_cls, FRAMEWORK_IDENTITY)
```

`register_schema()` fills in `class_identity` if absent, then calls `_register_class()`:

```python
def register_schema(
    self,
    schema_cls: type,
    library_identity: Optional[LibraryIdentity] = None
) -> str | None:
    """
    Explicitly register a settings schema (not via folder scan).
    Used for built-in GlobalSettings at DI bootstrap time.
    Creates class_identity from _namespace if the class has no decorator.
    """
    if not hasattr(schema_cls, 'class_identity'):
        ns = schema_cls._namespace
        if not ns:
            raise ValueError(f"{schema_cls.__name__} has no namespace — add namespace= kwarg")
        schema_cls.class_identity = SettingsClassIdentity(
            namespace    = ns,
            registry_key = f'__haywire__:settings:{ns}',
            label        = ns,
        )
    return self._register_class(schema_cls, library_identity)
```

Two paths, one destination:

| Class | Decorator | Registration | `class_identity` source |
| --- | --- | --- | --- |
| `LibrarySettings` subclass | `@library_settings` required | `add_folder()` scan | decorator |
| `GlobalSettings` subclass | none needed | `register_schema()` explicit | `register_schema()` at call time |

### Namespace subscription (Option B)

```python
def subscribe_namespace(self, namespace: str, callback: weakref.ref) -> None:
    """
    Register a weakref callback invoked when any key under namespace changes.
    Used by SettingsHolder to invalidate cached values on schema update.
    """
    self._namespace_subscribers.setdefault(namespace, []).append(callback)

def _notify_namespace_subscribers(self, changed_keys: set[str]) -> None:
    for key in changed_keys:
        parts = key.split('.')
        namespaces_to_notify = {'.'.join(parts[:i]) for i in range(1, len(parts) + 1)}
        for ns in namespaces_to_notify:
            dead = []
            for cb_ref in self._namespace_subscribers.get(ns, []):
                cb = cb_ref()
                if cb is None:
                    dead.append(cb_ref)
                else:
                    try:
                        cb(key)
                    except Exception as e:
                        logger.error(f"Namespace subscriber error for {key}: {e}")
            for ref in dead:
                self._namespace_subscribers[ns].remove(ref)
```

Call `_notify_namespace_subscribers(changed_keys)` at the end of `_notify_changes()`
(the existing TOML-reload notification method) in addition to the existing listener loop.

---

## BaseNode Integration

In `BaseNode.__init_subclass__` (or the `@node` decorator):

```python
def __init_subclass__(cls, **kwargs):
    super().__init_subclass__(**kwargs)

    # Detect inner Settings class (use __dict__ not getattr — don't inherit parent's)
    settings_cls = cls.__dict__.get('Settings')
    if settings_cls is not None and issubclass(settings_cls, NodeSettings):
        # Derive namespace if not explicitly set
        if not settings_cls._namespace:
            ns = _derive_namespace(cls)
            settings_cls._namespace = ns
            for name, descriptor in settings_cls._fields.items():
                descriptor._full_key = f'{ns}.{name}'
        # Deferred registration: actual register_schema() called when DI is ready
        cls._settings_schema = settings_cls
```

**SettingsHolder creation** (in `NodeWrapper.__init__` or wherever node instances are built):

```python
self.settings = SettingsHolder(
    schema_cls    = type(node).Settings if hasattr(type(node), 'Settings') else _EmptySettings,
    chain         = ResolutionChain(local_store={}, global_registry=global_registry),
    node_instance = node,
)
```

**dont forget to cleanup reference to global registry if the node is removed, to avoid memory leaks via SettingsHolder's namespace subscription**
---

## `@library_settings` Decorator

### `packages/haywire-framework/src/haywire/core/settings/decorators.py` (new)

`@library_settings` must set `class_identity` — required by `BaseRegistry._register()`.
Use a `SettingsClassIdentity` dataclass, analogous to `ThemeClassIdentity`.

```python
from dataclasses import dataclass

@dataclass
class SettingsClassIdentity:
    namespace:    str          # e.g. 'my_lib'
    registry_key: str          # '__haywire__:settings:my_lib'
    label:        str = ''


def library_settings(namespace: str, label: str = ''):
    """
    Decorator for library-global settings classes.
    Consistent with @node, @editor, @panel, @workbench_theme pattern.
    Sets class_identity (required by BaseRegistry) and _namespace.
    BaseLibrary.register_components() discovers these via GlobalSettingsRegistry
    folder scan — no manual _auto_register_schemas() call needed.
    """
    def decorator(cls):
        cls.class_identity = SettingsClassIdentity(
            namespace    = namespace,
            registry_key = f'__haywire__:settings:{namespace}',
            label        = label or namespace,
        )
        cls._namespace     = namespace
        cls._auto_register = True   # kept as a readable flag
        # Set _full_key on all descriptors (namespace known at decoration time)
        for name, descriptor in cls._fields.items():
            descriptor._full_key = f'{namespace}.{name}'
        return cls
    return decorator
```

**Note:** Manual `_auto_register_schemas()` scanning in `BaseLibrary` is no longer needed.
`GlobalSettingsRegistry` is registered with `LibraryRegistry.add_class_registry()`, so
`BaseLibrary.register_components()` adds folders to it directly — the same pattern used
by `NodeRegistry`, `SkinRegistry`, `EditorTypeRegistry`, etc.

---

## Theme System

### `WorkbenchTheme`
### `packages/haywire-framework/src/haywire/ui/themes/workbench.py` (new)

```python
class WorkbenchTheme(_SettingsSchema):
    """
    Defines CSS custom property values for the app shell.
    Fields map directly to --hw-{field_name} CSS tokens.
    No setting() wrapper needed — the annotation value IS the default.
    """
    # Token → CSS var mapping
    _CSS_TOKEN_MAP = {
        'bg_page':    '--hw-bg-page',
        'bg_surface': '--hw-bg-surface',
        'bg_sidebar': '--hw-bg-sidebar',
        'text_body':  '--hw-text-body',
        'text_muted': '--hw-text-muted',
        'text_dim':   '--hw-text-dim',
        'accent':     '--hw-accent',
        'border':     '--hw-border',
        # extend as needed
    }

    def to_css_vars(self) -> dict[str, str]:
        """Returns {--hw-token: value} dict for CSS injection."""
        result = {}
        for field_name, css_var in self._CSS_TOKEN_MAP.items():
            value = self._fields[field_name]._default   # class-level default
            result[css_var] = value
        return result
```

### `@workbench_theme` / `@node_theme` decorators
### `packages/haywire-framework/src/haywire/ui/themes/theme_decorators.py` (new)

Both decorators must set `class_identity` — required by `BaseRegistry._register()`. Use a
`ThemeClassIdentity` dataclass (analogous to how `@editor`, `@skin`, `@panel` work).

```python
from dataclasses import dataclass
from haywire.core.registry.base import BaseRegistry   # for type checking only

@dataclass
class ThemeClassIdentity:
    theme_id:     str          # short id, e.g. 'haywire-dark'
    theme_type:   str          # 'workbench' or 'node'
    registry_key: str          # '__haywire__:theme:workbench:haywire-dark'
    label:        str = ''


def workbench_theme(id: str, label: str = ''):
    def decorator(cls):
        cls.class_identity = ThemeClassIdentity(
            theme_id     = id,
            theme_type   = 'workbench',
            registry_key = f'__haywire__:theme:workbench:{id}',
            label        = label or id,
        )
        cls._theme_id       = id   # keep for backwards compat
        cls._auto_register  = True
        return cls
    return decorator


def node_theme(id: str, label: str = ''):
    def decorator(cls):
        cls.class_identity = ThemeClassIdentity(
            theme_id     = id,
            theme_type   = 'node',
            registry_key = f'__haywire__:theme:node:{id}',
            label        = label or id,
        )
        cls._theme_id       = id
        cls._auto_register  = True
        return cls
    return decorator
```

### `ThemeRegistry`
### `packages/haywire-framework/src/haywire/ui/themes/theme_registry.py` (new)

`ThemeRegistry` extends `BaseRegistry` — giving it hot-reload support, lifecycle events,
folder scanning, and compatibility with `LibraryRegistry.add_class_registry()`.

```python
import inspect
from typing import Optional
from haywire.core.registry.base import BaseRegistry
from haywire.core.library.identity import LibraryIdentity
from .workbench import WorkbenchTheme
from .node_theme import NodeTheme


class ThemeRegistry(BaseRegistry):
    """
    Registry for WorkbenchTheme and NodeTheme classes.

    Extends BaseRegistry: supports hot-reload, folder scanning, lifecycle events,
    dependency tracking, and snapshot rollback.

    Active theme is session-scoped (stored in SessionContext), not here.
    ThemeRegistry is registered in LibraryRegistry via:
        library_registry.add_class_registry(ThemeRegistry, theme_registry)
    """

    def _class_filter(self, cls) -> bool:
        try:
            return (
                inspect.isclass(cls)
                and issubclass(cls, (WorkbenchTheme, NodeTheme))
                and cls not in (WorkbenchTheme, NodeTheme)
                and hasattr(cls, 'class_identity')
            )
        except TypeError:
            return False

    def _register_class(
        self, cls: type, library_identity: Optional[LibraryIdentity] = None
    ) -> 'str | None':
        registry_key = cls.class_identity.registry_key
        return super()._register(registry_key, cls, library_identity)

    def _unregister_class(self, registry_key: str) -> 'type | None':
        return super()._unregister(registry_key)

    # ── Typed accessors ──────────────────────────────────────────────────────

    def get_workbench(self, theme_id: str) -> WorkbenchTheme:
        key = f'__haywire__:theme:workbench:{theme_id}'
        cls = self._classes.get(key)
        if cls is None:
            raise KeyError(f"Unknown workbench theme: '{theme_id}'")
        return cls()   # stateless — instantiate fresh each time

    def get_node_theme(self, theme_id: str) -> NodeTheme:
        key = f'__haywire__:theme:node:{theme_id}'
        cls = self._classes.get(key)
        if cls is None:
            raise KeyError(f"Unknown node theme: '{theme_id}'")
        return cls()

    def list_workbench_ids(self) -> list[str]:
        return sorted(
            cls.class_identity.theme_id
            for cls in self._classes.values()
            if cls.class_identity.theme_type == 'workbench'
        )

    def list_node_theme_ids(self) -> list[str]:
        return sorted(
            cls.class_identity.theme_id
            for cls in self._classes.values()
            if cls.class_identity.theme_type == 'node'
        )
```

### Session-scoped active theme

`SessionContext` gains two fields:
```python
active_workbench_theme_id: str = 'haywire-dark'   # default from global settings
active_node_theme_id:      str = 'default'
```

These are **not** persisted across sessions (reset to global/project settings default on reconnect).
The user can change them during a session; on reload, they revert to the default set in `settings.toml`:
```toml
[workbench]
theme = "haywire-dark"

[node]
theme = "default"
```

### `app_shell.py` CSS var injection

Replace the hardcoded `:root` / `body.body--dark` CSS block:

```python
def _build_initial_theme_css(self, theme: WorkbenchTheme) -> str:
    """Called once at page render to inject initial CSS vars."""
    vars_str = '; '.join(f'{k}: {v}' for k, v in theme.to_css_vars().items())
    return f':root {{ {vars_str} }}'

async def apply_workbench_theme(self, theme_id: str, context: SessionContext):
    """Called when user switches workbench theme during session."""
    theme = self._theme_registry.get_workbench(theme_id)
    context.active_workbench_theme_id = theme_id
    for token, value in theme.to_css_vars().items():
        await ui.run_javascript(
            f"document.documentElement.style.setProperty('{token}', '{value}')"
        )
```

The `body.body--dark` CSS block is **removed** — mode switching is now purely via theme selection (haywire-light vs haywire-dark). Quasar dark mode (`ui.dark_mode`) is still toggled so Quasar components adapt, but the `--hw-*` vars are driven by the active workbench theme.

---

## Built-in Settings Conversion

Each `builtins/ui_*.py` becomes a `GlobalSettings` subclass. Example:

```python
# BEFORE (builtins/ui_node.py) — 190 lines
def register(registry):
    registry.define('ui.node.bg_color', '#ffffff', label='Background Color', ...)
    registry.define('ui.node.border_width', 1, min_value=0, max_value=5, ...)
    ...

# AFTER — ~25 lines
class NodeUISettings(GlobalSettings, namespace='ui.node'):
    bg_color:          Color = setting('#ffffff',   label='Background Color',    order=10)
    bg_color_selected: Color = setting('#e3f2fd',   label='Selected Background', order=11)
    bg_color_error:    Color = setting('#ffebee',   label='Error Background',    order=12)
    border_color:      Color = setting('#cccccc',   label='Border Color',        order=20)
    border_width:      int   = setting(1,  min=0, max=5,    label='Border Width',  order=22)
    border_radius:     int   = setting(4,  min=0, max=20,   label='Border Radius', order=23)
    font_size:         int   = setting(12, min=8, max=24,   label='Font Size',     order=30)
    show_labels:       bool  = setting(True,  label='Show Port Labels',           order=40)
    show_type_hints:   bool  = setting(True,  label='Show Type Hints',            order=41)
    min_width:         int   = setting(150, min=50, max=500, label='Minimum Width', order=50)
    max_width:         int   = setting(400, min=0, max=1000, label='Maximum Width', order=51)
    shadow_enabled:    bool  = setting(True,  label='Enable Shadow',              order=60)
```

`builtins/__init__.py`'s `register_all(registry)` imports each `GlobalSettings` class and calls `registry.register_schema(cls)`.

---

## DI Wiring Changes

### `packages/haywire-framework/src/haywire/core/di/config.py`

**Add:**
```python
from ...ui.themes.theme_registry import ThemeRegistry

@provider
@singleton
def provide_theme_registry(self) -> ThemeRegistry:
    registry = ThemeRegistry()
    # Register built-in workbench themes
    from ...ui.themes.builtin import HaywireDarkTheme, HaywireLightTheme
    registry.register_workbench(HaywireDarkTheme)
    registry.register_workbench(HaywireLightTheme)
    # Register built-in node themes
    from ...ui.themes.builtin import DefaultNodeTheme
    registry.register_node_theme(DefaultNodeTheme)
    return registry
```

**Modify `provide_settings_registry()`:**
```python
def provide_settings_registry(self) -> GlobalSettingsRegistry:
    registry = GlobalSettingsRegistry()
    register_builtin_settings(registry)   # now calls register_schema() on each GlobalSettings class
    # Global tier
    registry.load_from_toml(self.settings_path, watch=self.watch_settings)
    # Project tier (loaded second — overrides global SET values)
    project_settings = Path(self.project_root) / '.haywire' / 'settings.toml'
    if project_settings.exists():
        registry.load_from_toml(project_settings, watch=self.watch_settings, append=True)
    return registry
```

**Remove:** `provide_theme_palette()` — `ThemePalette` is replaced by `ThemeRegistry`.

**In `LibrarySystemService.initialize()`:**
```python
theme_registry    = self.injector.get(ThemeRegistry)
settings_registry = self.injector.get(GlobalSettingsRegistry)

# Both registries extend BaseRegistry — register with LibraryRegistry so that
# BaseLibrary.register_components() can call add_folder() on them directly.
library_registry.add_class_registry(ThemeRegistry, theme_registry)
library_registry.add_class_registry(GlobalSettingsRegistry, settings_registry)

# Module dependency propagation: nodes/skins/panels/editors that import a
# LibrarySettings class (for shadow()/watch() syntax) live in modules that
# depend on the settings file. When the settings file changes on disk,
# settings_registry propagates the FileChangeEvent downstream so each
# registry can reload any managed module that imports from the changed file.
# This is the same pattern as type_registry → node_registry.
#
# NOTE: runtime value changes (TOML reload, set_global(), UI edits) are NOT
# handled here — those propagate via SettingsHolder namespace subscriptions,
# which fire _invalidate() on live node instances directly.
settings_registry.add_registry_subscriber(node_registry)
settings_registry.add_registry_subscriber(skin_registry)
settings_registry.add_registry_subscriber(panel_registry)
settings_registry.add_registry_subscriber(editor_registry)
```

---

## on_change Callback Convention

**Signature:** `method(self, value, field: str = '')` — `field` is optional.

The holder tries the two-arg form first, falls back to one-arg:
```python
try:
    callback(new_value, field_name)
except TypeError:
    callback(new_value)
```

This lets a single callback handle multiple settings fields:
```python
def hb_on_filter_changed(self, value, field: str = ''):
    if field == 'filter_strength':
        self.cache.alpha = value
    self.cache.needs_recalc = True
```

---

## File Inventory Summary

### New files

```
packages/haywire-framework/src/haywire/core/settings/
    types.py                — Color, Icon type aliases
    descriptors.py          — setting(), shadow(), watch()
    schema.py               — NodeSettings, LibrarySettings, GlobalSettings
    chain.py                — ResolutionChain
    decorators.py           — @library_settings, SettingsClassIdentity

packages/haywire-framework/src/haywire/ui/themes/
    workbench.py            — WorkbenchTheme
    node_theme.py           — NodeTheme
    theme_registry.py       — ThemeRegistry(BaseRegistry)
    theme_decorators.py     — @workbench_theme, @node_theme, ThemeClassIdentity
    data/haywire-dark.toml  — dark workbench theme values
    data/haywire-light.toml — light workbench theme values

tests/core/test_settings/
    test_descriptors.py
    test_schema.py
    test_chain.py
    test_holder_cache.py
    test_hot_reload.py
    test_namespace_sub.py

tests/ui/
    test_theme_registry.py
    test_workbench_theme.py
    test_node_theme.py

docs/documentation/themes.md/
    01-overview.md
    02-workbench-themes.md
    03-node-themes.md
    04-library-themes.md
```

### Modified files

```
packages/haywire-framework/src/haywire/core/settings/
    registry.py             — add subscribe_namespace(), register_schema(), project tier support
    holder.py               — full rewrite (class-based, cached, weakref subscriptions)
    __init__.py             — export new public API
    builtins/ui_node.py     — convert to GlobalSettings class
    builtins/ui_edge.py     — convert to GlobalSettings class
    builtins/ui_canvas.py   — convert to GlobalSettings class
    builtins/ui_minimap.py  — convert to GlobalSettings class
    builtins/execution.py   — convert to GlobalSettings class
    builtins/debug.py       — convert to GlobalSettings class
    builtins/editor.py      — convert to GlobalSettings class
    builtins/__init__.py    — register_all() calls register_schema() on each class

packages/haywire-framework/src/haywire/core/
    di/config.py            — add ThemeRegistry provider, project tier, remove ThemePalette
    library/base.py         — NO CHANGE needed: add_folder() pattern handles discovery

packages/haywire-framework/src/haywire/ui/themes/
    palette.py              — thin shim → ThemeRegistry (kept for transition, then remove)
    builtin.py              — DefaultTheme/DarkTheme → WorkbenchTheme/NodeTheme subclasses
    base.py                 — BaseTheme kept for TOML loading; ThemeMetadata kept
    __init__.py             — updated exports

packages/haywire-framework/src/haywire/ui/
    app_shell.py            — CSS vars read from active WorkbenchTheme; JS setProperty on change

docs/documentation/settings.md/
    01-overview.md          — full rewrite
    02-node-development.md  — full rewrite
    03-library-development.md — update for @library_settings
    04-ui-integration.md    — update
    05-reference.md         — full API reference update
    06-testing.md           — update
```

---

## Testing Plan

### `test_descriptors.py`
- `setting()` class-level `__get__` returns descriptor (key handle), instance-level returns resolved value
- `shadow(MyLibSettings.bg_color)` stores string `'my_lib.bg_color'`, not object reference
- `watch()` has `_panel_visible=False`, `_stored=False`
- `on_change='missing_method'` logs warning at holder init, does not raise

### `test_schema.py`
- `NodeSettings._fields` populated from annotated descriptors in class body
- `LibrarySettings` without `namespace=` kwarg raises at class definition
- `_full_key` set correctly for `LibrarySettings` (immediate) vs `NodeSettings` (deferred)
- `__set_name__` called with correct `owner` and `name`

### `test_chain.py`
- OVERRIDE > local SET > project SET > global SET > default
- `has_local()`, `set_local()`, `clear_local()` work correctly
- Project tier values correctly shadow global tier for SET (but not OVERRIDE)

### `test_holder_cache.py`
- First access → resolves via chain, caches result
- Second access → dict hit, chain.resolve NOT called
- `_invalidate('my_lib.bg_color')` evicts `bg_color` only; `threshold` cache survives
- `is_locally_set('bg_color')` returns False before set, True after `set_local()`
- `get_serializable()` excludes `watch()` fields, includes only locally-SET `setting()`/`shadow()` fields

### `test_hot_reload.py`
- Schema class recreated (simulated reload) → `_full_key` stable (same string)
- Namespace subscriber fires on schema update → affected cache entries evicted
- Values in `_local` store survive across schema recreations

### `test_namespace_sub.py`
- `subscribe_namespace('my_lib', weakref_cb)` → cb called when `my_lib.*` key changes
- GC'd subscriber → removed from list without error on next notification
- `my_other_lib.*` change does NOT trigger `my_lib` subscribers

### `test_theme_registry.py`
- `@workbench_theme(id='x')` + `register_workbench(cls)` → `get_workbench('x')` works
- `get_workbench('unknown')` raises `KeyError`
- `to_css_vars()` returns `{'--hw-bg-page': '#12121e', ...}`

### `test_workbench_theme.py` / `test_node_theme.py`
- Field introspection: all annotated fields collected in `_fields`
- TOML partial override: only listed fields replaced, others use class defaults
- `extends` chain: child overrides parent values, parent provides rest

---

## What Does NOT Change

- `self.store` — unchanged
- `self.cache` — unchanged
- TOML file format for values — same nested structure, values-only (schema stays in Python)
- `SettingMode.AUTO/SET/OVERRIDE` — kept; mapped to resolution chain semantics
- Library `@library`, `BaseLibrary`, `register_components()` — extended, not replaced
- Cross-registry `add_registry_subscriber()` pattern — used as-is
- Existing `GlobalSettingsRegistry.resolve()` logic — kept; `register_schema()` calls `define()` internally
- `self.cache.clear()` / `self.store.clear()` / `self.settings.reset()` behaviour

---

## Implementation Order

1. `types.py` — Color, Icon aliases
2. `descriptors.py` — setting(), shadow(), watch()
3. `schema.py` — NodeSettings, LibrarySettings, GlobalSettings
4. `registry.py` — add subscribe_namespace(), register_schema()
5. `chain.py` — ResolutionChain
6. `holder.py` — full rewrite
7. `builtins/` — convert all to GlobalSettings classes
8. `BaseNode.__init_subclass__` — Settings inner class wiring
9. `decorators.py` — @library_settings
10. `workbench.py`, `node_theme.py`, `theme_registry.py`, `theme_decorators.py`
11. `builtin.py` — convert DefaultTheme/DarkTheme
12. `app_shell.py` — CSS var injection from active WorkbenchTheme
13. `di/config.py` — wire ThemeRegistry, project tier, subscriber wiring
14. Tests
15. Documentation
