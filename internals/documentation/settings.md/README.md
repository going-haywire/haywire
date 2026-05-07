# Settings System

Haywire's settings system manages configuration at three levels: global application defaults, per-node instance overrides, and transient runtime data.

## The Three Containers

Every node instance exposes three containers:

| Container | Serialized | GUI-visible | Hierarchical |
|-----------|-----------|-------------|--------------|
| `self.cache` | No | No | No |
| `self.store` | Yes | No | No |
| `self.settings` | Yes (local overrides only) | Yes | Yes |

**Use `self.cache`** for transient computation data (lookup tables, buffers, memoization).
**Use `self.store`** for persistent internal state users don't see (counters, accumulators, state machines).
**Use `self.settings`** for anything users should be able to see and configure.

## Settings: Descriptor-Based Schema

Settings are declared as an inner `class node(NodeSettings)` using `setting()`, `shadow()`, and `watch()` descriptors:

```python
from haywire.core.settings import NodeSettings, setting, shadow, watch, Color
from haywire.core.settings.builtins.ui_node import NodeUISettings
from haywire.core.settings.builtins.debug import DebugSettings

class MyNode(BaseNode):

    class node(NodeSettings):
        # Local setting — stored in graph, shown in panel
        threshold = setting[float](0.5, min=0.0, max=1.0, label='Threshold')

        # shadow() — writable mirror; inherits global default; per-node override with reset affordance
        bg_color = shadow(NodeUISettings.bg_color)

        # watch() — read-only mirror; invisible in panel, never stored
        verbose = watch(DebugSettings.verbose_logging)

    def worker(self, context, value: float):
        result = value * self.node.threshold
        if self.node.verbose:
            context.log(f"result: {result}")
        self.out('result', result)
```

## Architecture

```
SettingsRegistry
├── FrameworkSettings schemas (auto-registered via _pending_global at registry init)
│   ├── NodeUISettings (namespace='ui.node')
│   ├── EdgeUISettings (namespace='ui.edge')
│   ├── DebugSettings  (namespace='debug')
│   ├── ExecutionSettings (namespace='execution')
│   └── EditorSettings (namespace='editor')
│
├── LibrarySettings schemas (registered via BaseRegistry hot-reload machinery)
│
├── global ~/.haywire/settings.toml                    — user VALUES, global tier (hand-edited)
└── workspace <workspace>/.haywire/settings.toml       — workspace VALUES, set via UI
```

Schema classes define the *shape* of settings. TOML files provide *values only*.

## Resolution Chain

```
self.node.threshold
    │
    ▼
1. Global tier OVERRIDE?    → return it (admin policy, hand-edited TOML)
    │ No
    ▼
2. Workspace tier OVERRIDE? → return it (workspace-wide force)
    │ No
    ▼
3. Local instance value?    → return it (per-node override, stored in graph JSON)
    │ No
    ▼
4. Workspace tier SET?      → return it (set via UI, saved to workspace TOML)
    │ No
    ▼
5. Global tier SET?         → return it (user global default)
    │ No
    ▼
6. Descriptor _default      → return it
```

## Documentation

- **[Overview](01-overview.md)** — Architecture, containers, descriptor types, serialization format
- **[Node Development](02-node-development.md)** — Declaring `NodeSettings` class, using descriptors, `on_change` callbacks
- **[Library Development](03-library-development.md)** — Creating `LibrarySettings`, referencing with `shadow()` and `watch()`
- **[UI Integration](04-ui-integration.md)** — Building settings panels, widget factory, inheritance indicators
- **[API Reference](05-reference.md)** — Complete descriptor, schema, registry, and chain API
- **[Testing Guide](06-testing.md)** — `create_test_bag()`, `SettingsTestContext`, fixtures
