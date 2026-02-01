# Settings System Overview

This document provides an architectural overview of Haywire's settings system, which manages configuration at multiple levels—from global application defaults to per-node customizations.

## Introduction

### The Problem

Node-based applications need configuration at multiple levels:

- **Global defaults** — Application-wide settings (colors, timeouts, behaviors)
- **Per-node overrides** — Individual nodes may need different values
- **Runtime state** — Temporary data during execution
- **Persistent state** — Data that survives save/load cycles

Without a unified system, developers end up with:
- Scattered configuration files
- Inconsistent APIs
- No inheritance or override mechanism
- Manual serialization for each data type

### The Solution

Haywire provides a **three-tier data model** with clear separation of concerns:

| Container | Purpose | Serialized | GUI-Visible |
|-----------|---------|------------|-------------|
| `self.cache` | Transient runtime data | ❌ No | ❌ No |
| `self.store` | Persistent internal state | ✅ Yes | ❌ No |
| `self.settings` | User-configurable options | ✅ Yes | ✅ Yes |

---

## Architecture

### App Startup: Global Registry

When the application starts, the `GlobalSettingsRegistry` is created and populated:

```
┌─────────────────────────────────────────────────────────────────┐
│                     GlobalSettingsRegistry                       │
├─────────────────────────────────────────────────────────────────┤
│  1. Created as singleton via DI                                 │
│                                                                  │
│  2. Builtin modules register definitions (schema):              │
│     - ui_node.py    → 'ui.node.bg_color', 'ui.node.font_size'  │
│     - ui_edge.py    → 'ui.edge.color', 'ui.edge.width'         │
│     - execution.py  → 'execution.timeout_seconds'               │
│     - debug.py      → 'debug.verbose_logging'                   │
│     - editor.py     → 'editor.undo_limit'                       │
│                                                                  │
│  3. Load settings.toml → applies user VALUES                    │
│                                                                  │
│  4. File watcher (optional) → hot-reload on file change         │
└─────────────────────────────────────────────────────────────────┘
```

The `settings.toml` file contains **values only**, not schema:

```toml
[ui.node]
bg_color = "#f0f0f0"                        # SET mode (implicit)
font_size = { override = true, value = 14 } # OVERRIDE mode (explicit)

[execution]
timeout_seconds = 120

[debug]
verbose_logging = true
```

### Node Creation: Local Holder

When a node instance is created, it gets its own `SettingsHolder`:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Node Instance Created                         │
├─────────────────────────────────────────────────────────────────┤
│  1. SettingsHolder created, linked to GlobalSettingsRegistry    │
│                                                                  │
│  2. Built-in LOCAL-ONLY settings registered:                    │
│     - 'node.muted' (default: False)                             │
│     - 'node.collapsed' (default: False)                         │
│     - 'node.pinned' (default: False)                            │
│     - 'node.color_override' (default: None)                     │
│     These have NO global equivalent.                            │
│                                                                  │
│  3. Node developer can add more in initialize():                │
│                                                                  │
│     # Local-only (no global equivalent)                         │
│     self.settings.define('my_node.cache_size', 100,             │
│                          scope=SettingScope.LOCAL_ONLY)         │
│                                                                  │
│     # Override a global setting for this node                   │
│     self.settings['ui.node.bg_color'] = '#e8f4e8'              │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Runtime Resolution

When you access a setting, the system resolves it through a hierarchy:

```
┌─────────────────────────────────────────────────────────────────┐
│              self.settings['ui.node.bg_color']                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Resolution Order:                                               │
│                                                                  │
│  1. Global OVERRIDE? ───────→ Return global value (forced)      │
│         │                                                        │
│         ↓ No                                                     │
│  2. Local SET? ─────────────→ Return local value (node-specific)│
│         │                                                        │
│         ↓ No                                                     │
│  3. Global SET? ────────────→ Return global value (app default) │
│         │                                                        │
│         ↓ No                                                     │
│  4. Return definition default                                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

For **LOCAL-ONLY** settings (e.g., `node.muted`):

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Local SET? ─────────────→ Return local value                │
│         │                                                        │
│         ↓ No                                                     │
│  2. Return definition default                                    │
│                                                                  │
│  (No global lookup — these don't exist in GlobalRegistry)       │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Concepts

### Modes

Settings can be in one of three modes:

| Mode | Meaning | Use Case |
|------|---------|----------|
| `AUTO` | Inherit from parent level | Default state, no override |
| `SET` | Explicit value at this level | User customization |
| `OVERRIDE` | Force value on all children | Global enforcement |

### Scopes

Settings are defined with one of two scopes:

| Scope | Meaning | Example |
|-------|---------|---------|
| `GLOBAL_AWARE` | Participates in global/local hierarchy | `ui.node.bg_color` |
| `LOCAL_ONLY` | Exists only at node level | `node.muted`, `node.collapsed` |

### The Three Containers

#### `self.cache` — Transient Runtime Data

```python
# NOT serialized — lost on save/load or app restart
self.cache.lookup_table = {}
self.cache.last_result = None
self.cache.temp_buffer = []
```

**Use for:**
- Computation caches
- Temporary buffers
- Memoization
- Runtime-only state that can be recomputed

#### `self.store` — Persistent Internal State

```python
# Serialized with node — survives save/load
self.store.execution_count = 0
self.store.accumulated_sum = 0.0
self.store.history = []
```

**Use for:**
- Counters and accumulators
- State machines
- Results that must persist
- Internal data users don't need to see/edit

#### `self.settings` — User-Configurable Options

```python
# Serialized, GUI-visible, hierarchical resolution
color = self.settings['ui.node.bg_color']      # Read global
self.settings['ui.node.bg_color'] = '#ff0000'  # Local override
self.settings.define('my_option', 42, scope=SettingScope.LOCAL_ONLY)
```

**Use for:**
- Anything users should see in properties panel
- Options that benefit from global defaults
- Configuration that should be editable

---

## Decision Guide: Which Container?

```
                        ┌─────────────────────┐
                        │ Do users need to    │
                        │ see/edit this?      │
                        └─────────┬───────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                   YES                          NO
                    │                           │
                    ▼                           ▼
           ┌───────────────┐         ┌─────────────────────┐
           │ self.settings │         │ Must it persist     │
           └───────────────┘         │ across save/load?   │
                                     └──────────┬──────────┘
                                                │
                                  ┌─────────────┴─────────────┐
                                  │                           │
                                 YES                          NO
                                  │                           │
                                  ▼                           ▼
                         ┌─────────────┐            ┌─────────────┐
                         │ self.store  │            │ self.cache  │
                         └─────────────┘            └─────────────┘
```

### Quick Reference

| Data Type | Container | Example |
|-----------|-----------|---------|
| User-editable option | `settings` | Background color, timeout |
| Computation cache | `cache` | Lookup tables, memoization |
| Accumulated result | `store` | Running totals, counters |
| Temporary buffer | `cache` | Processing queue |
| Node visual state | `settings` | Collapsed, muted, pinned |
| Position/dimensions | `ui.state` | x, y, width, height |
| User notes | `metadata` | Annotations, tags |

---

## Serialization

### What Gets Saved Where

| Data | Serialized In | Format |
|------|---------------|--------|
| Global settings | `~/.haywire/settings.toml` | TOML |
| Node settings (local overrides) | Node dict in graph file | JSON |
| Node store | Node dict in graph file | JSON |
| Node cache | **Not saved** | — |
| Node UI state (position) | Node dict in graph file | JSON |
| Node metadata | Node dict in graph file | JSON |

### Node Serialization Example

```json
{
  "node_id": "abc123",
  "ports": { ... },
  "settings": {
    "local_values": {
      "node.muted": {"mode": "SET", "value": true},
      "ui.node.bg_color": {"mode": "SET", "value": "#ff0000"}
    },
    "local_definitions": {
      "my_node.cache_size": {
        "default": 100,
        "type": "int",
        "scope": "LOCAL_ONLY"
      }
    }
  },
  "store": {
    "execution_count": 42,
    "accumulated_sum": 123.45
  },
  "ui": {
    "state": {"pos_x": 100, "pos_y": 200}
  },
  "metadata": {
    "notes": ["Remember to optimize this"],
    "tags": ["important"]
  }
}
```

**Key points:**
- Only non-`AUTO` local values are saved
- Global definitions are **not** saved (they exist in code)
- Global values are **not** saved in nodes (only the local overrides)

---

## Next Steps

- **[Node Development Guide](02-node-development.md)** — Using cache, store, and settings in nodes
- **[Library Development Guide](03-library-development.md)** — Creating custom global settings
- **[UI Integration Guide](04-ui-integration.md)** — Building settings panels with NiceGUI
- **[API Reference](05-reference.md)** — Complete API documentation
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
