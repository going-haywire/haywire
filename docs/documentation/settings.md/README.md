
## Data Architecture Summary

### 1. App Startup (Global Registry)

```
┌─────────────────────────────────────────────────────────────────┐
│                     GlobalSettingsRegistry                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Created as singleton via DI                                 │
│  2. Builtin modules register definitions (schema):              │
│     - ui_node.py → 'ui.node.bg_color', 'ui.node.font_size'...  │
│     - ui_edge.py → 'ui.edge.color', 'ui.edge.width'...         │
│     - execution.py → 'execution.timeout_seconds'...             │
│     - etc.                                                      │
│  3. Load settings.toml → applies VALUES (SET/OVERRIDE modes)    │
│  4. File watcher (optional) → hot-reload on file change         │
└─────────────────────────────────────────────────────────────────┘

settings.toml only contains VALUES, not schema:
┌─────────────────────────────────┐
│ [ui.node]                       │
│ bg_color = "#f0f0f0"            │  ← SET mode (implicit)
│ font_size = { override = true,  │  ← OVERRIDE mode (explicit)
│               value = 14 }      │
└─────────────────────────────────┘
```

### 2. Node Creation (Local Holder)

```
┌─────────────────────────────────────────────────────────────────┐
│                    Node Instance Created                         │
├─────────────────────────────────────────────────────────────────┤
│  1. SettingsHolder created, linked to GlobalSettingsRegistry    │
│                                                                  │
│  2. node_instance.py registers LOCAL-ONLY settings:             │
│     - 'node.muted' (default: False)                             │
│     - 'node.collapsed' (default: False)                         │
│     - 'node.pinned' (default: False)                            │
│     - 'node.color_override' (default: None)                     │
│     - etc.                                                       │
│     These have NO global equivalent.                            │
│                                                                  │
│  3. Node designer can add more in init():                 │
│                                                                  │
│     # Local-only (no global equivalent)                         │
│     self.settings.define('my_node.cache_size', 100,             │
│                          scope=SettingScope.LOCAL_ONLY)         │
│                                                                  │
│     # Participate in global resolution (optional)               │
│     self.settings.define('ui.node.special_mode', False)         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Runtime Resolution

```
┌─────────────────────────────────────────────────────────────────┐
│              self.settings['ui.node.bg_color']                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Resolution Order:                                               │
│                                                                  │
│  1. Global OVERRIDE? ──→ Return global value (forced)           │
│         │                                                        │
│         ↓ No                                                     │
│  2. Local SET? ──→ Return local value (node-specific)           │
│         │                                                        │
│         ↓ No                                                     │
│  3. Global SET? ──→ Return global value (app default)           │
│         │                                                        │
│         ↓ No                                                     │
│  4. Return definition default                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

For LOCAL-ONLY settings (e.g., 'node.muted'):
┌─────────────────────────────────────────────────────────────────┐
│  1. Local SET? ──→ Return local value                           │
│         │                                                        │
│         ↓ No                                                     │
│  2. Return definition default                                    │
│                                                                  │
│  (No global lookup - these don't exist in GlobalRegistry)       │
└─────────────────────────────────────────────────────────────────┘
```

### 4. Node Serialization

```
┌─────────────────────────────────────────────────────────────────┐
│                      node._to_dict()                            │
├─────────────────────────────────────────────────────────────────┤
│  {                                                               │
│    'node_id': 'abc123',                                         │
│    'ports': { ... },                                            │
│    'settings': {                                                │
│      'local_values': {                                          │
│        # Only non-AUTO values are saved                         │
│        'node.muted': {'mode': 'SET', 'value': True},           │
│        'node.collapsed': {'mode': 'SET', 'value': False},      │
│        'ui.node.bg_color': {'mode': 'SET', 'value': '#ff0000'},│ ← Local override of global
│        'my_node.cache_size': {'mode': 'SET', 'value': 200},    │ ← Local-only
│      },                                                         │
│      'local_definitions': {                                     │
│        # Only LOCAL_ONLY definitions are saved                  │
│        'my_node.cache_size': {                                  │
│          'default': 100,                                        │
│          'type': 'int',                                         │
│          'scope': 'LOCAL_ONLY',                                 │
│          ...                                                    │
│        }                                                        │
│      }                                                          │
│    },                                                           │
│    'store': { ... },                                            │
│    'ui': { ... },                                               │
│    'metadata': { ... }                                          │
│  }                                                               │
└─────────────────────────────────────────────────────────────────┘

Note: 
- Global-aware settings that are AUTO (inherited) are NOT saved
- Global definitions are NOT saved (they exist in code)
- Only local overrides and local-only definitions are persisted
```

### 5. Node Deserialization

```
┌─────────────────────────────────────────────────────────────────┐
│                 node._initialize_from_dict(data)                │
├─────────────────────────────────────────────────────────────────┤
│  1. Create fresh SettingsHolder (linked to GlobalRegistry)      │
│  2. Register node_instance.py LOCAL-ONLY settings               │
│  3. Restore local_definitions from saved data                   │
│     (rebuilds any custom LOCAL_ONLY settings)                   │
│  4. Restore local_values from saved data                        │
│     (applies saved overrides)                                   │
│                                                                  │
│  Result: Node has same local overrides as when saved,           │
│          but global values may have changed (that's fine!)      │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Reference Table

| Setting Type | Defined In | Stored In | Serialized With | GUI Visible |
|--------------|------------|-----------|-----------------|-------------|
| Global (builtin) | `builtins/*.py` | GlobalRegistry | `settings.toml` | Global Settings Panel |
| Global (from TOML) | `settings.toml` | GlobalRegistry | `settings.toml` | Global Settings Panel |
| Local override of global | Node code | SettingsHolder | Node dict | Node Properties Panel |
| Local-only | Node code | SettingsHolder | Node dict | Node Properties Panel |
| Node instance defaults | `node_instance.py` | SettingsHolder | Node dict (if changed) | Node Properties Panel |

we don't save the **global values**, we save the **local override values**. The distinction matters because:

```python
# Global registry has:
'ui.node.bg_color' = '#ffffff' (SET mode)

# Node has local override:
self.settings['ui.node.bg_color'] = '#ff0000'

# When saved, node stores:
'ui.node.bg_color': {'mode': 'SET', 'value': '#ff0000'}  # The LOCAL value

# NOT the global value '#ffffff'
```

When the node is loaded, it will:
1. See `'ui.node.bg_color'` exists in GlobalRegistry ✓
2. Apply the local override `'#ff0000'`
3. Resolve to `'#ff0000'` (local wins over global)

If the global value changes to `'#000000'` between save and load, the node still uses `'#ff0000'` because it has a local override.


# Speed Considerations for Settings Access in Nodes

## Rough Benchmarks

```python
# Approximate timing (will vary by hardware)

# Direct dict access
d = {'key': 42}
d['key']  # ~50-100 ns

# Settings resolution (estimated)
self.settings['ui.node.bg_color']  # ~500-1000 ns (0.5-1 µs)

# For comparison:
# - Function call overhead: ~100-200 ns
# - Port value access: ~200-500 ns
# - Simple math operation: ~10-50 ns
```

## Recommendation

**Don't use settings in hot paths within worker().**

Instead, **cache resolved values** in `self.cache` during `post_init()` or at the beginning of `worker()`:

### Pattern 1: Cache in `post_init()`

```python
@node(label="Fast Node")
class FastNode(BaseNode):
    
    def init(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
    
    def post_init(self, context):
        """Called once before first execution."""
        # Cache settings that won't change during execution
        self.cache.verbose = self.settings['debug.verbose_logging']
        self.cache.timeout = self.settings['execution.timeout_seconds']
    
    def worker(self, context, value: float):
        # Use cached values - direct attribute access is fast
        if self.cache.verbose:
            context.log(f"Processing: {value}")
        
        self.out('result', value * 2)
```

### Pattern 2: Cache at Start of Worker (if settings might change)

```python
@node(label="Responsive Node")
class ResponsiveNode(BaseNode):
    
    def init(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        
        # Track if cache needs refresh
        self.cache.settings_valid = False
        
        # Subscribe to setting changes
        self.settings.on_change(self._on_setting_change)
    
    def _on_setting_change(self, name: str, value: Any, source: str):
        self.cache.settings_valid = False
    
    def _refresh_settings_cache(self):
        self.cache.verbose = self.settings['debug.verbose_logging']
        self.cache.multiplier = self.settings.get('my_node.multiplier', 1.0)
        self.cache.settings_valid = True
    
    def worker(self, context, value: float):
        # Refresh cache only when needed
        if not self.cache.settings_valid:
            self._refresh_settings_cache()
        
        # Fast access
        if self.cache.verbose:
            context.log(f"Processing: {value}")
        
        self.out('result', value * self.cache.multiplier)
```

### Pattern 3: Simple One-Time Check

```python
def worker(self, context, value: float):
    # OK for settings checked once per execution
    # NOT OK in a tight loop
    
    if self.settings['node.muted']:
        return  # Skip execution
    
    # ... rest of worker
```

## When Settings Access is OK in Worker

| Scenario | OK to Use Directly? |
|----------|---------------------|
| Check once at start of worker | ✅ Yes |
| Conditional that rarely triggers | ✅ Yes |
| Inside a loop (100+ iterations) | ❌ No, cache first |
| Per-pixel/per-sample processing | ❌ No, cache first |
| Debug logging checks | ✅ Yes (usually once) |
| Checking `node.muted` | ✅ Yes (once per execution) |


## Summary

| Access Method | Speed | Use Case |
|---------------|-------|----------|
| `self.settings['key']` | ~1 µs | Occasional access, setup code |
| `self.cache.key` | ~50 ns | Hot paths, loops, frequent access |
| Local variable | ~10 ns | Tightest loops |

**Rule of thumb**: If you access a setting more than once per `worker()` call, cache it.



# Application startup
from haywire.core.di.config import init_library_system

# Initialize (typically in main.py)
init_library_system(config_dir='~/.haywire')

# Now anywhere in your code:
from haywire.core.di.config import get_library_system

registry = get_library_system().get_settings_registry()

# Define custom settings for your plugin/extension
registry.define('my_plugin.feature_x', True, label='Enable Feature X')

# Access values
value = registry.resolve('my_plugin.feature_x')[0]

# In nodes, it's even simpler:
class MyNode(BaseNode):
    def worker(self, context):
        # Direct access to any global setting
        if self.settings.debug.verbose_logging:
            pass
        
        # Local-only settings
        self.settings.define('local_thing', 42, scope=SettingScope.LOCAL_ONLY)
        x = self.settings.local_thing


# examples/my_custom_node.py
"""
Example node showing settings usage.
"""


```python

from haywire.core.node.base import BaseNode
from haywire.core.settings import SettingScope
from haywire.core.execution.execution_context import ExecutionContext

# Assuming you have type definitions like this
# from haywire.core.types import FLOAT, STRING, BOOL


class MyCustomNode(BaseNode):
    """
    Example node demonstrating the settings system.
    """
    
    def init(self):
        """Set up ports and settings."""
        
        # Ports (your existing pattern)
        # self.add(FLOAT.as_inlet('value', label='Input Value'))
        # self.add(FLOAT.as_outlet('result', label='Result'))
        
        # Local-only settings (no global equivalent)
        self.settings.define(
            'cache_enabled', 
            default=True,
            scope=SettingScope.LOCAL_ONLY,
            label='Enable Caching',
            description='Cache intermediate results for faster re-execution',
            category='performance'
        )
        self.settings.define(
            'cache_size', 
            default=100,
            scope=SettingScope.LOCAL_ONLY,
            label='Cache Size',
            min_value=10,
            max_value=10000,
            category='performance'
        )
        
        # Optionally set local override for a global setting
        # (Only if you want a different default for this node type)
        # self.settings['ui.node.bg_color'] = '#e8f4e8'  # Greenish tint
    
    def worker(self, context: ExecutionContext, value: float = 0.0) -> str | None:
        """Main execution logic."""
        
        # Access global settings directly (no define needed)
        if self.settings['debug.verbose_logging']:
            context.log(f"Processing value: {value}")
        
        # Or use dot notation
        if self.settings.debug.show_execution_time:
            context.log(f"Execution started")
        
        # Access local-only settings
        if self.settings.cache_enabled:
            cache_size = self.settings.cache_size
            # ... use cache ...
        
        # Check if a setting is overridden globally
        color_info = self.settings.get_info('ui.node.bg_color')
        if color_info.is_overridden:
            context.log("Note: Background color is forced by global settings")
        
        # Do computation
        result = value * 2
        
        self.out('result', result)
        return None  # Data flow node
    
    def get_background_color(self) -> str:
        """
        Used by UI renderer to get the node's background color.
        
        Demonstrates how UI code can access settings.
        """
        return self.settings['ui.node.bg_color']
    
    def get_display_config(self) -> dict:
        """
        Get all UI-related settings for rendering.
        """
        return {
            'bg_color': self.settings['ui.node.bg_color'],
            'border_color': self.settings['ui.node.border_color'],
            'font_size': self.settings['ui.node.font_size'],
            'show_labels': self.settings['ui.node.show_labels'],
            'border_radius': self.settings['ui.node.border_radius'],
        }


class ConditionalNode(BaseNode):
    """
    Control flow node example showing settings usage.
    """
    
    def init(self):
        # self.add(BOOL.as_inlet('condition', label='Condition'))
        # self.add(EXEC.as_outlet('true_branch', label='True'))
        # self.add(EXEC.as_outlet('false_branch', label='False'))
        
        # Local setting for this node type
        self.settings.define(
            'invert_condition',
            default=False,
            scope=SettingScope.LOCAL_ONLY,
            label='Invert Condition',
            description='Swap true/false branches'
        )
    
    def worker(self, context: ExecutionContext, condition: bool = False) -> str:
        """Execute based on condition."""
        
        # Apply local setting
        if self.settings.invert_condition:
            condition = not condition
        
        if self.settings.debug.verbose_logging:
            context.log(f"Condition: {condition}")
        
        return 'true_branch' if condition else 'false_branch'

    @node(
        label="Accumulator",
        menu="math/statistics",
        is_stateful=True,
        is_pure=False
    )
    class AccumulatorNode(BaseNode):
        
        def init(self):
            # Ports
            self.add(FLOAT.as_inlet('value'))
            self.add(FLOAT.as_outlet('sum'))
            self.add(FLOAT.as_outlet('count'))
            
            # Persistent state (survives save/load)
            self.store.total = 0.0
            self.store.count = 0
            
            # Transient cache (lost on reload)
            self.cache.last_value = None
        
        def worker(self, context, value: float):
            # Use store for persistent state
            self.store.total += value
            self.store.count += 1
            
            # Use cache for transient data
            self.cache.last_value = value
            
            # Check settings
            if self.settings['debug.verbose_logging']:
                context.log(f"Accumulated: {self.store.total}")
            
            self.out('sum', self.store.total)
            self.out('count', self.store.count)

```


# examples/settings_from_ui.py
"""
Example showing how to access settings from UI code.
"""

```python
from haywire.core.di.config import get_library_system
from haywire.core.settings import SettingMode


def render_settings_panel():
    """Example NiceGUI settings panel."""
    from nicegui import ui
    
    registry = get_library_system().get_settings_registry()
    
    with ui.card().classes('p-4'):
        ui.label('Global Settings').classes('text-xl font-bold mb-4')
        
        # Group by category
        for category, definitions in registry.definitions_by_category().items():
            with ui.expansion(category.replace('.', ' > ').title(), value=True):
                for defn in definitions:
                    global_val = registry.get_global(defn.name)
                    current_value = (
                        global_val.value if global_val.mode != SettingMode.AUTO 
                        else defn.default
                    )
                    
                    with ui.row().classes('items-center gap-2 w-full'):
                        ui.label(defn.label).classes('w-48')
                        
                        # Create appropriate widget based on type
                        if defn.type_ == bool:
                            switch = ui.switch(value=current_value)
                            switch.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, e.value))
                        
                        elif defn.choices:
                            select = ui.select(
                                options=defn.choices,
                                value=current_value
                            )
                            select.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, e.value))
                        
                        elif defn.type_ == int:
                            number = ui.number(
                                value=current_value,
                                min=defn.min_value,
                                max=defn.max_value
                            )
                            number.on('change', lambda e, n=defn.name: 
                                      registry.set_global(n, int(e.value)))
                        
                        elif defn.ui_widget == 'color':
                            color = ui.color_input(value=current_value)
                            color.on('change', lambda e, n=defn.name: 
                                     registry.set_global(n, e.value))
                        
                        else:
                            text = ui.input(value=str(current_value))
                            text.on('change', lambda e, n=defn.name: 
                                    registry.set_global(n, e.value))
                        
                        # Override toggle
                        is_override = global_val.mode == SettingMode.OVERRIDE
                        override_btn = ui.button(
                            icon='lock' if is_override else 'lock_open',
                            color='orange' if is_override else 'grey'
                        ).props('flat dense')
                        
                        def toggle_override(name=defn.name):
                            sv = registry.get_global(name)
                            if sv.mode == SettingMode.OVERRIDE:
                                registry.set_global(name, sv.value, SettingMode.SET)
                            else:
                                registry.set_global(name, sv.value, SettingMode.OVERRIDE)
                        
                        override_btn.on('click', toggle_override)
        
        # Save button
        ui.button('Save Settings', on_click=lambda: registry.save_to_toml())


def render_node_settings_panel(node):
    """Render settings panel for a specific node."""
    from nicegui import ui
    
    with ui.card().classes('p-4'):
        ui.label(f'Node Settings: {node.node_id}').classes('text-lg font-bold mb-2')
        
        for name, info in node.settings.get_all_info().items():
            with ui.row().classes('items-center gap-2'):
                # Override indicator
                if info.is_overridden:
                    ui.icon('lock', color='orange').tooltip('Forced by global settings')
                elif info.is_inherited:
                    ui.icon('link', color='grey').tooltip(f'Inherited from {info.source}')
                else:
                    ui.icon('edit', color='green').tooltip('Local override')
                
                ui.label(info.definition.label).classes('w-32')
                
                # Value display/edit
                if info.is_overridden:
                    # Read-only when overridden
                    ui.label(str(info.value)).classes('text-grey')
                else:
                    if info.definition.type_ == bool:
                        switch = ui.switch(value=info.value)
                        switch.on('change', lambda e, n=name: node.settings.set(n, e.value))
                    else:
                        inp = ui.input(value=str(info.value))
                        inp.on('change', lambda e, n=name: node.settings.set(n, e.value))
                
                # Reset button (only if locally overridden)
                if info.local_mode == SettingMode.SET:
                    ui.button(icon='refresh', on_click=lambda n=name: node.settings.reset(n)).props('flat dense')

```

# my_library/settings.py
"""
Custom settings for my library.
"""

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.settings import GlobalSettingsRegistry


CATEGORY = 'my_library'


def register(registry: 'GlobalSettingsRegistry') -> None:
    """Register my library's settings."""
    
    registry.define(
        'my_library.feature_x_enabled', True,
        label='Enable Feature X',
        description='Toggle the fancy feature X',
        category=CATEGORY,
        ui_order=10
    )
    registry.define(
        'my_library.api_url', 'https://api.example.com',
        label='API URL',
        description='Base URL for external API',
        category=CATEGORY,
        ui_order=20
    )
    registry.define(
        'my_library.max_connections', 5,
        label='Max Connections',
        description='Maximum concurrent API connections',
        category=CATEGORY,
        min_value=1,
        max_value=20,
        ui_order=21
    )


# Register when library is loaded
def on_library_load():
    from haywire.core.di.config import get_settings_registry
    register(get_settings_registry())
```

## Summary

The architecture provides:
```
Class-Level (immutable, set by @node decorator):
├── class_identity: NodeIdentity
│   ├── registry_id, label, description
│   ├── search_tags, menu
│   ├── help_md, help_url
│   └── _is_error, _error_priority
│
└── class_behavior: NodeBehaviorFlags
    ├── is_control_node, is_data_node, is_event_node
    ├── is_output_node, is_pure, is_stateful
    ├── is_loopback, has_execute_async, is_mutable

Instance-Level:
├── identity → class_identity (read-only property)
├── behavior → class_behavior (read-only property)
├── settings: SettingsHolder -> GUI-accessible settings
│   ├── Global-aware: ui.node.*, execution.*, etc.
│   └── Local-only: node.muted, node.collapsed, etc.
├── cache: NodeCache (transient, NOT serialized)
├── store: NodeStore (persistent, serialized, NOT GUI)
├── ui: NodeUI (position, dimensions, convenience methods)
└── ports: dict[str, DataPort]
```

## Potential speed Optimization for Settings Resolution

we could add a **fast-path cache** to `SettingsHolder`:

```python
class SettingsHolder:
    def __init__(self, ...):
        # ... existing init ...
        self._resolved_cache: dict[str, Any] = {}
        self._cache_valid = False
    
    def _invalidate_cache(self):
        self._cache_valid = False
        self._resolved_cache.clear()
    
    def __getitem__(self, key: str) -> Any:
        key = key.lower()
        
        # Fast path: check cache first
        if self._cache_valid and key in self._resolved_cache:
            return self._resolved_cache[key]
        
        # Slow path: full resolution
        value, _ = self._resolve(key)
        self._resolved_cache[key] = value
        return value
    
    def _on_global_change(self, name: str, global_val: SettingValue) -> None:
        self._invalidate_cache()
        # ... rest of existing code
```
