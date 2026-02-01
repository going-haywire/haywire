# Node Development Guide

This guide covers how to use the cache, store, and settings containers when developing Haywire nodes.

## Quick Start

Here's a minimal node using all three containers:

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import SettingScope

@node(label="Quick Start Example")
class QuickStartNode(BaseNode):
    
    def initialize(self):
        # Define ports
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('result'))
        
        # Cache: transient, not serialized
        self.cache.lookup = {}
        
        # Store: persistent, serialized, not GUI-visible
        self.store.call_count = 0
        
        # Settings: persistent, serialized, GUI-visible
        self.settings.define(
            'multiplier', 
            default=1.0,
            scope=SettingScope.LOCAL_ONLY,
            label='Multiplier',
            min_value=0.0,
            max_value=100.0
        )
    
    def worker(self, context, value: float):
        self.store.call_count += 1
        result = value * self.settings.multiplier
        self.cache.lookup[value] = result
        self.out('result', result)
```

---

## The Cache Container

`self.cache` is a `SimpleNamespace`-like container for transient runtime data.

### Characteristics

- ❌ **Not serialized** — Data is lost on save/load
- ❌ **Not GUI-visible** — Users cannot see or edit
- ✅ **Fast access** — Direct attribute access
- ✅ **Any Python object** — No serialization constraints

### When to Use

| Use Case | Example |
|----------|---------|
| Computation caches | `self.cache.lookup = {}` |
| Temporary buffers | `self.cache.buffer = []` |
| Memoization | `self.cache.memo = {}` |
| Last computed value | `self.cache.last_result = None` |
| Runtime flags | `self.cache.needs_refresh = True` |

### API

```python
# Set attributes freely
self.cache.my_data = {"key": "value"}
self.cache.counter = 0
self.cache.items = []

# Access attributes
value = self.cache.my_data
self.cache.counter += 1

# Clear all cached data
self.cache.clear()
```

### Example: Memoization Cache

```python
@node(label="Expensive Computation")
class ExpensiveNode(BaseNode):
    
    def initialize(self):
        self.add(FLOAT.as_inlet('x'))
        self.add(FLOAT.as_outlet('result'))
        self.cache.memo = {}
    
    def worker(self, context, x: float):
        # Check cache first
        if x in self.cache.memo:
            self.out('result', self.cache.memo[x])
            return
        
        # Expensive computation
        result = self._expensive_compute(x)
        
        # Cache for next time
        self.cache.memo[x] = result
        self.out('result', result)
    
    def _expensive_compute(self, x: float) -> float:
        # Simulate expensive operation
        import time
        time.sleep(0.1)
        return x ** 2 + x + 1
```

---

## The Store Container

`self.store` is a persistent container for internal node state.

### Characteristics

- ✅ **Serialized** — Survives save/load cycles
- ❌ **Not GUI-visible** — Users cannot see or edit
- ✅ **Attribute access** — `self.store.counter`
- ✅ **Dict access** — `self.store['counter']`
- ⚠️ **JSON-serializable types only** — Primitives, lists, dicts, sets

### When to Use

| Use Case | Example |
|----------|---------|
| Counters | `self.store.execution_count = 0` |
| Accumulators | `self.store.running_sum = 0.0` |
| History tracking | `self.store.history = []` |
| State machines | `self.store.current_state = 'idle'` |
| Persistent flags | `self.store.has_initialized = False` |

### API

```python
# Set attributes
self.store.counter = 0
self.store.history = []
self.store.data = {"nested": {"values": [1, 2, 3]}}

# Access attributes
count = self.store.counter
self.store.history.append(new_item)

# Dict-style access
self.store['counter'] = 0
count = self.store['counter']

# Check existence
if self.store.has('counter'):
    ...

# Get with default
value = self.store.get('missing', default=0)

# Clear all
self.store.clear()

# Iterate
for key in self.store:
    print(key, self.store[key])
```

### Serialization

The store automatically handles common Python types:

```python
# These all serialize correctly
self.store.string = "hello"
self.store.number = 42
self.store.float_val = 3.14
self.store.boolean = True
self.store.list_val = [1, 2, 3]
self.store.dict_val = {"key": "value"}
self.store.set_val = {1, 2, 3}  # Saved as {"__type__": "set", "values": [1, 2, 3]}
self.store.tuple_val = (1, 2)   # Saved as {"__type__": "tuple", "values": [1, 2]}
```

### Example: Accumulator Node

```python
@node(
    label="Accumulator",
    is_stateful=True,
    is_pure=False
)
class AccumulatorNode(BaseNode):
    
    def initialize(self):
        self.add(FLOAT.as_inlet('value'))
        self.add(FLOAT.as_outlet('sum'))
        self.add(FLOAT.as_outlet('count'))
        self.add(FLOAT.as_outlet('average'))
        
        # Persistent state
        self.store.total = 0.0
        self.store.count = 0
        self.store.history = []
    
    def worker(self, context, value: float):
        # Update persistent state
        self.store.total += value
        self.store.count += 1
        self.store.history.append(value)
        
        # Limit history size
        if len(self.store.history) > 100:
            self.store.history = self.store.history[-100:]
        
        # Output results
        self.out('sum', self.store.total)
        self.out('count', self.store.count)
        self.out('average', self.store.total / self.store.count)
```

---

## The Settings Container

`self.settings` provides user-configurable options with hierarchical resolution.

### Characteristics

- ✅ **Serialized** — Survives save/load cycles
- ✅ **GUI-visible** — Shown in properties panel
- ✅ **Hierarchical** — Global defaults with local overrides
- ✅ **Validated** — Type checking, min/max, choices
- ✅ **Reactive** — Change callbacks for UI updates

### Access Patterns

```python
# Dict-style access
color = self.settings['ui.node.bg_color']
self.settings['ui.node.bg_color'] = '#ff0000'

# Dot notation (nested namespaces)
color = self.settings.ui.node.bg_color
font = self.settings.ui.node.font_size

# Get with default
value = self.settings.get('missing.setting', default=42)

# Check existence
if 'ui.node.bg_color' in self.settings:
    ...
```

### Defining Local Settings

```python
from haywire.core.settings import SettingScope

def initialize(self):
    # Local-only setting (no global equivalent)
    self.settings.define(
        'cache_size',
        default=100,
        scope=SettingScope.LOCAL_ONLY,
        label='Cache Size',
        description='Maximum items to cache',
        category='performance',
        min_value=10,
        max_value=10000,
        ui_order=10
    )
    
    # Boolean setting
    self.settings.define(
        'enable_logging',
        default=False,
        scope=SettingScope.LOCAL_ONLY,
        label='Enable Logging',
        category='debug'
    )
    
    # Choice setting
    self.settings.define(
        'algorithm',
        default='fast',
        scope=SettingScope.LOCAL_ONLY,
        label='Algorithm',
        choices=['fast', 'accurate', 'balanced'],
        category='processing'
    )
```

### Accessing Global Settings

Global settings can be accessed directly without `define()`:

```python
def worker(self, context, value: float):
    # Access any global setting
    if self.settings['debug.verbose_logging']:
        context.log(f"Processing: {value}")
    
    # Dot notation works too
    timeout = self.settings.execution.timeout_seconds
    bg_color = self.settings.ui.node.bg_color
```

### Overriding Global Settings Locally

```python
def initialize(self):
    # Set a different default for this node type
    self.settings['ui.node.bg_color'] = '#e8f4e8'  # Greenish tint
```

### Reset to Inherited Value

```python
# Reset single setting
self.settings.reset('ui.node.bg_color')

# Reset all local overrides
self.settings.reset_all()
```

### Change Callbacks

```python
def initialize(self):
    self.settings.define('multiplier', 1.0, scope=SettingScope.LOCAL_ONLY)
    self.settings.on_change(self._on_setting_changed)
    
    # Track if cache needs refresh
    self.cache.settings_valid = False

def _on_setting_changed(self, name: str, value: Any, source: str):
    """Called when any setting changes."""
    if name == 'multiplier':
        self.cache.settings_valid = False
        # Optionally trigger re-execution
        self.wrapper.mark_dirty()
```

### Introspection

```python
# Get full info about a setting
info = self.settings.get_info('ui.node.bg_color')
print(f"Value: {info.value}")
print(f"Source: {info.source}")  # 'local', 'global', 'default', 'global_override'
print(f"Is overridden: {info.is_overridden}")
print(f"Is inherited: {info.is_inherited}")

# Get all settings info (for UI)
all_info = self.settings.get_all_info()

# Get only settings with local overrides
local_overrides = self.settings.get_local_settings()
```

---

## Complete Example Node

This comprehensive example demonstrates all containers and best practices:

```python
from haywire.core.node import BaseNode, node
from haywire.core.settings import SettingScope
from haywire.core.execution import ExecutionContext
from typing import Any

@node(
    label="Signal Processor",
    description="Processes signals with configurable filtering and statistics",
    menu="processing/signals",
    search_tags=["signal", "filter", "statistics"],
    is_stateful=True,
    is_pure=False
)
class SignalProcessorNode(BaseNode):
    """
    A comprehensive example node demonstrating:
    - Cache for transient computation data
    - Store for persistent statistics
    - Settings for user-configurable options
    - Performance-conscious patterns
    """
    
    def initialize(self):
        """Set up ports, settings, and initial state."""
        
        # -----------------------------------------------------------------
        # Ports
        # -----------------------------------------------------------------
        self.add(FLOAT.as_inlet('signal', label='Input Signal'))
        self.add(BOOL.as_inlet('reset', label='Reset Statistics', default=False))
        self.add(FLOAT.as_outlet('filtered', label='Filtered Output'))
        self.add(FLOAT.as_outlet('average', label='Running Average'))
        self.add(INT.as_outlet('count', label='Sample Count'))
        
        # -----------------------------------------------------------------
        # Settings: User-configurable, GUI-visible
        # -----------------------------------------------------------------
        
        # Processing settings
        self.settings.define(
            'filter_strength',
            default=0.5,
            scope=SettingScope.LOCAL_ONLY,
            label='Filter Strength',
            description='Smoothing factor (0=none, 1=maximum)',
            category='processing',
            min_value=0.0,
            max_value=1.0,
            ui_widget='slider',
            ui_order=10
        )
        
        self.settings.define(
            'filter_type',
            default='exponential',
            scope=SettingScope.LOCAL_ONLY,
            label='Filter Type',
            description='Type of smoothing filter to apply',
            category='processing',
            choices=['none', 'exponential', 'moving_average'],
            ui_order=20
        )
        
        self.settings.define(
            'window_size',
            default=10,
            scope=SettingScope.LOCAL_ONLY,
            label='Window Size',
            description='Number of samples for moving average',
            category='processing',
            min_value=2,
            max_value=100,
            ui_order=30
        )
        
        # Statistics settings
        self.settings.define(
            'track_statistics',
            default=True,
            scope=SettingScope.LOCAL_ONLY,
            label='Track Statistics',
            description='Calculate running statistics',
            category='statistics',
            ui_order=10
        )
        
        self.settings.define(
            'max_history',
            default=1000,
            scope=SettingScope.LOCAL_ONLY,
            label='Max History',
            description='Maximum samples to keep in history',
            category='statistics',
            min_value=10,
            max_value=100000,
            ui_order=20
        )
        
        # -----------------------------------------------------------------
        # Store: Persistent internal state
        # -----------------------------------------------------------------
        self.store.sample_count = 0
        self.store.running_sum = 0.0
        self.store.min_value = float('inf')
        self.store.max_value = float('-inf')
        
        # -----------------------------------------------------------------
        # Cache: Transient runtime data
        # -----------------------------------------------------------------
        self.cache.last_filtered = 0.0
        self.cache.history_buffer = []
        self.cache.settings_valid = False
        
        # Cached settings for hot path
        self.cache.filter_strength = 0.5
        self.cache.filter_type = 'exponential'
        self.cache.window_size = 10
        self.cache.track_statistics = True
        
        # Subscribe to setting changes
        self.settings.on_change(self._on_setting_changed)
    
    def _on_setting_changed(self, name: str, value: Any, source: str):
        """Invalidate cache when settings change."""
        self.cache.settings_valid = False
    
    def _refresh_settings_cache(self):
        """Refresh cached settings from settings container."""
        self.cache.filter_strength = self.settings['filter_strength']
        self.cache.filter_type = self.settings['filter_type']
        self.cache.window_size = self.settings['window_size']
        self.cache.track_statistics = self.settings['track_statistics']
        self.cache.settings_valid = True
    
    def startup(self, context: ExecutionContext):
        """Called once before first execution."""
        # Initialize settings cache
        self._refresh_settings_cache()
        
        # Log startup if verbose
        if self.settings['debug.verbose_logging']:
            context.log(f"SignalProcessor starting with {self.store.sample_count} samples")
    
    def worker(self, context: ExecutionContext, signal: float, reset: bool = False):
        """Main processing logic."""
        
        # Handle reset
        if reset:
            self._reset_statistics()
            if self.settings['debug.verbose_logging']:
                context.log("Statistics reset")
        
        # Refresh settings cache if needed (once per execution, not in loop)
        if not self.cache.settings_valid:
            self._refresh_settings_cache()
        
        # Apply filter (using cached settings for speed)
        filtered = self._apply_filter(signal)
        
        # Update statistics if enabled
        if self.cache.track_statistics:
            self._update_statistics(signal)
        
        # Output results
        self.out('filtered', filtered)
        self.out('average', self._get_average())
        self.out('count', self.store.sample_count)
    
    def _apply_filter(self, signal: float) -> float:
        """Apply configured filter to signal."""
        filter_type = self.cache.filter_type
        
        if filter_type == 'none':
            result = signal
        
        elif filter_type == 'exponential':
            alpha = self.cache.filter_strength
            result = alpha * self.cache.last_filtered + (1 - alpha) * signal
        
        elif filter_type == 'moving_average':
            self.cache.history_buffer.append(signal)
            window = self.cache.window_size
            
            # Keep buffer at window size
            if len(self.cache.history_buffer) > window:
                self.cache.history_buffer = self.cache.history_buffer[-window:]
            
            result = sum(self.cache.history_buffer) / len(self.cache.history_buffer)
        
        else:
            result = signal
        
        self.cache.last_filtered = result
        return result
    
    def _update_statistics(self, value: float):
        """Update persistent statistics."""
        self.store.sample_count += 1
        self.store.running_sum += value
        self.store.min_value = min(self.store.min_value, value)
        self.store.max_value = max(self.store.max_value, value)
    
    def _get_average(self) -> float:
        """Calculate running average."""
        if self.store.sample_count == 0:
            return 0.0
        return self.store.running_sum / self.store.sample_count
    
    def _reset_statistics(self):
        """Reset all statistics to initial state."""
        self.store.sample_count = 0
        self.store.running_sum = 0.0
        self.store.min_value = float('inf')
        self.store.max_value = float('-inf')
        self.cache.history_buffer = []
        self.cache.last_filtered = 0.0
    
    def get_statistics(self) -> dict:
        """Get current statistics (for UI or API access)."""
        return {
            'count': self.store.sample_count,
            'sum': self.store.running_sum,
            'average': self._get_average(),
            'min': self.store.min_value if self.store.sample_count > 0 else None,
            'max': self.store.max_value if self.store.sample_count > 0 else None,
        }
```

---

## Performance Considerations

### Access Speed Comparison

| Access Method | Approximate Time | Use Case |
|---------------|------------------|----------|
| `self.cache.key` | ~50-100 ns | Hot paths, loops |
| `self.store.key` | ~50-100 ns | Hot paths, loops |
| `self.settings['key']` (cached) | ~50-100 ns | After first access |
| `self.settings['key']` (uncached) | ~300-800 ns | First access |
| Local variable | ~10 ns | Tightest loops |

### When Direct Settings Access is OK

| Scenario | Direct Access OK? |
|----------|-------------------|
| Once at start of `worker()` | ✅ Yes |
| Checking `node.muted` | ✅ Yes |
| Debug logging check | ✅ Yes |
| Inside loop (10+ iterations) | ❌ Cache first |
| Per-sample processing | ❌ Cache first |
| High-frequency calls | ❌ Cache first |

### Recommended Pattern: Settings Cache

```python
def initialize(self):
    # Set up cache invalidation
    self.cache.settings_valid = False
    self.settings.on_change(lambda n, v, s: setattr(self.cache, 'settings_valid', False))

def worker(self, context, value: float):
    # Refresh cache only when needed
    if not self.cache.settings_valid:
        self.cache.multiplier = self.settings['my_node.multiplier']
        self.cache.verbose = self.settings['debug.verbose_logging']
        self.cache.settings_valid = True
    
    # Use cached values in hot path
    result = value * self.cache.multiplier
```

---

## Best Practices

### Naming Conventions

```python
# Settings: use dot-separated namespaces
self.settings.define('my_node.processing.algorithm', ...)
self.settings.define('my_node.display.show_grid', ...)

# Store: use snake_case
self.store.execution_count = 0
self.store.last_processed_id = None

# Cache: use snake_case
self.cache.lookup_table = {}
self.cache.temp_buffer = []
```

### Category Organization

```python
# Group related settings by category for UI
self.settings.define('option1', ..., category='processing', ui_order=10)
self.settings.define('option2', ..., category='processing', ui_order=20)
self.settings.define('option3', ..., category='display', ui_order=10)
```

### Documentation

```python
self.settings.define(
    'threshold',
    default=0.5,
    scope=SettingScope.LOCAL_ONLY,
    label='Detection Threshold',  # Short, shown in UI
    description='Minimum confidence level for detection. '
                'Lower values catch more but may include false positives.',  # Tooltip
    category='detection'
)
```

### Initialize All Containers in `initialize()`

```python
def initialize(self):
    # Always initialize all containers to known state
    
    # Ports first
    self.add(...)
    
    # Settings definitions
    self.settings.define(...)
    
    # Store with explicit defaults
    self.store.counter = 0
    self.store.data = {}
    
    # Cache with explicit defaults
    self.cache.buffer = []
    self.cache.last_value = None
```

---

## Next Steps

- **[Library Development Guide](03-library-development.md)** — Creating custom global settings
- **[UI Integration Guide](04-ui-integration.md)** — Building settings panels
- **[API Reference](05-reference.md)** — Complete API documentation
