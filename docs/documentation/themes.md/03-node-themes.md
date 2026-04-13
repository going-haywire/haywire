# Node Themes

This guide covers creating and registering custom node rendering themes.

---

## Anatomy of a NodeTheme

```python
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label='Blueprint')
class BlueprintNodeTheme(NodeTheme):
    """Blueprint-style node rendering — dark blue with cyan ports."""

    # Node chrome
    header_bg        = '#0d2137'
    header_text      = '#a0d8ef'
    body_bg          = '#091929'
    body_text        = '#c0e0f8'
    border           = '#1a3a5c'
    border_selected  = '#00bfff'

    # Port colours
    port_inlet       = '#00aaff'
    port_outlet      = '#ff6600'
    port_exec_inlet  = '#ffffff'
    port_exec_outlet = '#ffffff'

    # Error state
    error_bg         = '#1f0a0a'
    error_border     = '#ff4444'

    # Misc
    muted_opacity    = '0.4'
```

---

## Available Tokens

| Token | Purpose |
|-------|---------|
| `header_bg` | Node header background |
| `header_text` | Node header label text |
| `body_bg` | Node body/content background |
| `body_text` | Node body text |
| `border` | Default node border |
| `border_selected` | Border when node is selected |
| `port_inlet` | Data inlet port fill colour |
| `port_outlet` | Data outlet port fill colour |
| `port_exec_inlet` | Control-flow inlet port colour |
| `port_exec_outlet` | Control-flow outlet port colour |
| `error_bg` | Background when node has an error |
| `error_border` | Border when node has an error |
| `muted_opacity` | CSS opacity for disabled/muted elements |

---

## Accessing Tokens

The node renderer accesses tokens via `NodeTheme.get_color(token)`:

```python
theme = node_theme_instance   # NodeTheme subclass instance

header_color = theme.get_color('header_bg')    # '#0d2137'
missing_tok  = theme.get_color('nonexistent')  # ''  — empty string, no error
```

---

## Rules

| Rule | Detail |
|------|--------|
| **Decorator required** | `@theme(registry_id=...)` must appear before the class |
| **Unique `registry_id`** | Must not clash with other ids within the same library |
| **Plain string attributes** | Values are plain class attributes, not `setting()` descriptors |
| **Undefined tokens** | `get_color()` returns `''` for missing tokens — safe to call unconditionally |

---

## Partial Override

Subclass an existing theme and override only the tokens you need:

```python
from haywire.ui.themes.builtin import DefaultNodeTheme


@theme(label='High Contrast Nodes')
class HighContrastNodeTheme(DefaultNodeTheme):
    """Default node theme with high-contrast borders."""
    border          = '#ffffff'
    border_selected = '#ffff00'
    header_text     = '#ffffff'
    body_text       = '#ffffff'
```

---

## Registration

```python
# In library's register_components():
from haywire.ui.themes.theme_registry import ThemeRegistry
from .themes import BlueprintNodeTheme


def register_components(self, registries):
    theme_registry: ThemeRegistry = registries.get(ThemeRegistry)
    if theme_registry:
        theme_registry.register_node_theme(BlueprintNodeTheme)
```

---

## Pairing with a WorkbenchTheme

Node themes are independent of workbench themes — a user can mix any combination.
If your library ships a matching pair, document the recommended pairing in the library README:

```toml
# Recommended combination for the Blueprint style:
[workbench]
theme = "blueprint-dark"   # WorkbenchTheme

[node]
theme = "blueprint"        # NodeTheme
```

---

## Testing

```python
from haywire.ui.themes.theme_registry import ThemeRegistry
from my_lib.themes import BlueprintNodeTheme


def test_blueprint_node_theme():
    r = ThemeRegistry()
    r.register_node_theme(BlueprintNodeTheme)

    theme = r.get_node_theme(BlueprintNodeTheme.class_identity.registry_key)

    assert theme.get_color('header_bg')    == '#0d2137'
    assert theme.get_color('port_inlet')   == '#00aaff'
    assert theme.get_color('nonexistent')  == ''
```

---

## Next Steps

- **[04-library-themes.md](04-library-themes.md)** — Packaging themes in a haybale library
- **[01-overview.md](01-overview.md)** — CSS token map, ThemeRegistry, architecture
