# API Reference

Complete API documentation for the Haywire settings system.

---

## Enums

### SettingMode

Defines how a setting value is applied.

```python
from haywire.core.settings import SettingMode

class SettingMode(Enum):
    AUTO = "auto"       # Inherit from parent level
    SET = "set"         # Explicitly set at this level
    OVERRIDE = "override"  # Force value on all children (global only)
```

| Mode | Description |
|------|-------------|
| `AUTO` | No value set; inherit from global or use default |
| `SET` | Value explicitly set at this level |
| `OVERRIDE` | (Global only) Force this value on all nodes |

### SettingScope

Defines whether a setting participates in the global hierarchy.

```python
from haywire.core.settings import SettingScope

class SettingScope(Enum):
    GLOBAL_AWARE = "global_aware"  # Participates in global/local hierarchy
    LOCAL_ONLY = "local_only"      # Exists only at node level
```

| Scope | Description |
|-------|-------------|
| `GLOBAL_AWARE` | Can inherit from global settings, can be overridden |
| `LOCAL_ONLY` | No global equivalent; purely local to node |

---

## SettingValue

Represents a setting's value and mode.

```python
from haywire.core.settings import SettingValue

@dataclass
class SettingValue:
    mode: SettingMode = SettingMode.AUTO
    value: Any = None
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_dict()` | `dict` | Serialize to `{'mode': str, 'value': Any}` |
| `from_dict(data)` | `SettingValue` | Deserialize from dict |

---

## SettingDefinition

Defines a setting's schema, constraints, and metadata.

```python
from haywire.core.settings import SettingDefinition

@dataclass
class SettingDefinition:
    name: str                    # Full setting name (e.g., 'ui.node.bg_color')
    default: Any                 # Default value
    type_: type = str            # Expected Python type
    scope: SettingScope = GLOBAL_AWARE
    
    # Validation
    min_value: float | None = None
    max_value: float | None = None
    choices: list | None = None
    validator: Callable[[Any], bool] | None = None
    
    # UI Metadata
    label: str | None = None
    description: str = ""
    category: str = "general"
    ui_widget: str | None = None  # 'color', 'slider', 'textarea', etc.
    ui_order: int = 0
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Full dotted name (e.g., `'ui.node.bg_color'`) |
| `default` | `Any` | Default value when no override exists |
| `type_` | `type` | Python type for validation/coercion |
| `scope` | `SettingScope` | `GLOBAL_AWARE` or `LOCAL_ONLY` |
| `min_value` | `float \| None` | Minimum allowed value (numeric) |
| `max_value` | `float \| None` | Maximum allowed value (numeric) |
| `choices` | `list \| None` | Allowed values (enum-like) |
| `validator` | `Callable` | Custom validation function `(value) -> bool` |
| `label` | `str` | Human-readable label for UI |
| `description` | `str` | Tooltip/help text |
| `category` | `str` | Category for grouping in UI |
| `ui_widget` | `str` | Widget hint for UI rendering |
| `ui_order` | `int` | Sort order within category |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `validate(value)` | `bool` | Check if value is valid |
| `coerce(value)` | `Any` | Convert value to correct type |
| `to_dict()` | `dict` | Serialize definition |

---

## GlobalSettingsRegistry

Singleton registry for global settings definitions and values.

### Initialization

```python
from haywire.core.settings import GlobalSettingsRegistry

# Usually accessed via DI:
from haywire.core.di.config import get_settings_registry
registry = get_settings_registry()

# Or create directly (testing):
registry = GlobalSettingsRegistry()
```

### Define Settings

```python
registry.define(
    name: str,                    # Required: setting name
    default: Any,                 # Required: default value
    type_: type = None,           # Inferred from default if None
    label: str = None,            # Defaults to name
    description: str = "",
    category: str = "general",
    min_value: float = None,
    max_value: float = None,
    choices: list = None,
    validator: Callable = None,
    ui_widget: str = None,
    ui_order: int = 0
) -> GlobalSettingsRegistry      # Returns self for chaining
```

### Get/Set Values

```python
# Get global value (returns SettingValue)
sv = registry.get_global(name: str) -> SettingValue

# Set global value
registry.set_global(
    name: str,
    value: Any,
    mode: SettingMode = SettingMode.SET
) -> None

# Reset to AUTO
registry.reset_global(name: str) -> None
```

### Resolution

```python
# Resolve with optional local value
value, source = registry.resolve(
    name: str,
    local_value: SettingValue = None
) -> tuple[Any, str]

# Source is one of: 'global_override', 'local', 'global', 'default'
```

### Introspection

```python
# Check if defined
registry.has_definition(name: str) -> bool

# Get definition
defn = registry.get_definition(name: str) -> SettingDefinition | None

# Get all definitions
all_defs = registry.all_definitions() -> dict[str, SettingDefinition]

# Group by category
by_cat = registry.definitions_by_category() -> dict[str, list[SettingDefinition]]
```

### Persistence

```python
# Load from TOML file
registry.load_from_toml(
    path: Path | str,
    watch: bool = False  # Enable hot-reload
) -> None

# Save to TOML file
registry.save_to_toml(path: Path | str = None) -> None

# Reload from file
registry.reload_from_toml() -> None
```

### Change Notifications

```python
# Subscribe to changes
registry.add_listener(
    callback: Callable[[str, SettingValue], None]
) -> None

# Unsubscribe
registry.remove_listener(callback: Callable) -> None
```

---

## SettingsHolder

Per-instance container for settings with local values.

### Initialization

```python
from haywire.core.settings import SettingsHolder

holder = SettingsHolder(
    registry: GlobalSettingsRegistry,
    owner: Any = None,           # Optional owner for notifications
    owner_name: str = ''         # For debugging
)
```

### Define Local Settings

```python
holder.define(
    name: str,
    default: Any,
    type_: type = None,
    scope: SettingScope = GLOBAL_AWARE,
    label: str = None,
    description: str = "",
    category: str = "local",
    **kwargs  # Same as SettingDefinition
) -> SettingsHolder  # Returns self for chaining
```

### Access Values

```python
# Dict-style
value = holder['ui.node.bg_color']
holder['ui.node.bg_color'] = '#ff0000'

# Dot notation
value = holder.ui.node.bg_color

# Get with default
value = holder.get('missing', default=42)

# Check existence
if 'ui.node.bg_color' in holder:
    ...

# Iterate
for name in holder:
    print(name, holder[name])

for name, value in holder.items():
    print(name, value)
```

### Set Values

```python
# Set with explicit mode
holder.set(
    name: str,
    value: Any,
    mode: SettingMode = SettingMode.SET
) -> None

# Reset to AUTO (inherit)
holder.reset(name: str) -> None

# Reset all
holder.reset_all() -> None
```

### Introspection

```python
# Get full info for UI
info = holder.get_info(name: str) -> SettingInfo

# Get all settings info
all_info = holder.get_all_info() -> dict[str, SettingInfo]

# Get only locally-set settings
local = holder.get_local_settings() -> dict[str, SettingInfo]
```

### Change Callbacks

```python
# Subscribe
holder.on_change(
    callback: Callable[[str, Any, str], None]  # (name, value, source)
) -> None

# Unsubscribe
holder.remove_callback(callback: Callable) -> None
```

### Serialization

```python
# Serialize local state
data = holder.to_dict() -> dict

# Restore local state
holder.from_dict(data: dict) -> None
```

### Cleanup

```python
# Clean up subscriptions
holder.cleanup() -> None
```

---

## SettingInfo

Full information about a resolved setting (for UI).

```python
from haywire.core.settings import SettingInfo

@dataclass
class SettingInfo:
    name: str              # Setting name
    value: Any             # Resolved value
    source: str            # 'global_override', 'local', 'global', 'default'
    
    is_overridden: bool    # True if global override is active
    is_inherited: bool     # True if using global/default (not local)
    
    local_mode: SettingMode
    local_value: Any | None
    global_mode: SettingMode
    global_value: Any | None
    
    definition: SettingDefinition
```

---

## NodeCache

Transient runtime cache (not serialized).

```python
from haywire.core.node import NodeCache

# It's a SimpleNamespace, use freely:
cache = NodeCache()
cache.my_data = {}
cache.counter = 0

# Clear all
cache.clear()
```

### Properties

- Attribute access: `cache.key = value`
- Not serialized
- Fast access (~50ns)

---

## NodeStore

Persistent user state (serialized, not GUI-visible).

```python
from haywire.core.node import NodeStore

store = NodeStore()
```

### Attribute Access

```python
store.counter = 0
store.data = {"key": "value"}
value = store.counter
```

### Dict-Style Access

```python
store['counter'] = 0
value = store['counter']
del store['counter']
```

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `has(key)` | `bool` | Check if key exists |
| `get(key, default)` | `Any` | Get with default |
| `setdefault(key, default)` | `Any` | Get or set default |
| `keys()` | `Iterator` | All keys |
| `values()` | `Iterator` | All values |
| `items()` | `Iterator` | All (key, value) pairs |
| `update(**kwargs)` | `None` | Set multiple values |
| `clear()` | `None` | Clear all data |
| `to_dict()` | `dict` | Serialize |
| `from_dict(data)` | `None` | Deserialize |

### Serialization

Supports: `str`, `int`, `float`, `bool`, `None`, `list`, `dict`, `set`, `tuple`, and objects with `to_dict()` method.

---

## TOML Format

### Simple Values (SET mode)

```toml
[ui.node]
bg_color = "#ffffff"
font_size = 12
show_labels = true

[execution]
timeout_seconds = 60
max_parallel = 4
```

### Override Values

```toml
[ui.node]
# Force this value on all nodes
font_size = { override = true, value = 14 }
```

### Full Example

```toml
# ~/.haywire/settings.toml

[ui.node]
bg_color = "#f5f5f5"
border_color = "#cccccc"
font_size = { override = true, value = 13 }
show_labels = true

[ui.edge]
color = "#666666"
width = 2
curve_style = "bezier"

[ui.canvas]
bg_color = "#1a1a1a"
grid_enabled = true
grid_size = 20

[execution]
auto_execute = true
timeout_seconds = 120
max_parallel = 8

[debug]
verbose_logging = false
show_execution_time = false

[my_library]
feature_x_enabled = true
api_url = "https://api.example.com"
```

---

## Resolution Algorithm

```
resolve(name, local_value):
    1. If global mode is OVERRIDE:
       → Return global value, source='global_override'
    
    2. If local mode is SET:
       → Return local value, source='local'
    
    3. If global mode is SET:
       → Return global value, source='global'
    
    4. Return definition default, source='default'
```

For LOCAL_ONLY settings:

```
resolve_local_only(name):
    1. If local mode is SET:
       → Return local value, source='local'
    
    2. Return definition default, source='default'
```

---

## Next Steps

- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
