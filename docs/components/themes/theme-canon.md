---
status: draft
template: canonical-example
scope: Authoring WorkbenchTheme and NodeTheme subclasses, registering them in a library, hot-reload behaviour
see-also:
  - ../skins/skin-canon.md
  - ../libraries/library-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../architecture/hot-reload/hot-reload-arch.md
  - ../../reference/glossary.md
---

# Theme — Canonical Example

## 1. What it solves

A **theme** controls the visual appearance of haywire. Two independent theme types exist:

- **`WorkbenchTheme`** — the *application shell*: page backgrounds, sidebars, top bar, status bar, panel surfaces, canvas grid, accent colours, edge colours, etc. Values are injected as CSS custom properties on `:root` and cascade through the entire app.
- **`NodeTheme`** — the *node chip rendering*: header colour, port colours, error state, body background. Values are read by the canvas-side node renderer.

Both are independent — a user can mix any workbench theme with any node theme. As an author, you subclass the relevant base, override only the tokens you want to change, decorate with `@theme(label=...)`, and register the class in your library's `register_components()`.

Themes are *not* the same as **skins** (per-node visual variants of the node body — see [components/skins](../skins/skin-canon.md)) or as **CSS tokens in panels** (which read from the active workbench theme; component authors don't redefine them).

## 2. How it fits

```text
Author declares                Library registers              Studio applies
────────────────               ─────────────────              ──────────────
@theme(label=...)              theme_registry.register_       Active theme:
class FooTheme(                  workbench(FooTheme)              workbench.theme
    WorkbenchTheme):           theme_registry.register_           in TOML
   bg_page = '#0a0f1a'           node_theme(BarTheme)
   accent  = '#3498db'                                         AppShell.apply_
                                                                 workbench_theme()
                                                                 → injects :root
                                                                   CSS variables
                                                                   live, no reload
```

Both classes share two architectural facts:

- **Plain string class attributes**, not `field()` descriptors. `__init_subclass__` wraps them into `_FieldProxy` objects collected in `_fields`.
- **`ThemeRegistry`** (a `BaseRegistry` subclass) tracks registered classes by `registry_key`. Hot-reload is automatic — when a library reloads, the registry re-registers and the active theme is re-applied.

**Boundaries.** What CSS tokens *are* (the `--hw-*` design system) lives in [reference/design-guide](../../reference/design-guide.md). The studio shell that consumes themes lives in [architecture/studio](../../architecture/studio/studio-arch.md). The hot-reload pipeline that re-binds themes lives in [architecture/hot-reload](../../architecture/hot-reload/hot-reload-arch.md). The `theme` setting that selects the active theme lives in the [settings system](../settings/setting-canon.md).

## 3. Important concepts

**The `@theme` decorator.** Required on every theme subclass. Sets `class_identity` (used by `BaseRegistry` for hot-reload), derives `registry_key` from the library and class name, and accepts a `label` for display.

```python
@theme(label='My Dark Theme')
class MyDarkTheme(WorkbenchTheme): ...
```

**Plain string attributes, not descriptors.** Every theme field is a class-level string assignment:

```python
class FooTheme(WorkbenchTheme):
    bg_page = '#0a0f1a'      # ← plain string class attribute
    accent  = '#3498db'      # ← not a field() descriptor
```

`WorkbenchTheme.__init_subclass__` collects these into `_fields`. Defining a field that isn't in the token map is silently ignored (no error). Omitting a field is silently inherited from the parent class — partial themes work without ceremony.

**`WorkbenchTheme` token map.** ~30 named tokens covering backgrounds, borders, text, accents, status colours, node chrome, edges, canvas, top bar, sidebars, panels, status bar, and console. Defined in `_CSS_TOKEN_MAP` mapping `field_name` → `--hw-<token>`. The full list is in [reference/design-guide](../../reference/design-guide.md); examples in §4.

**`NodeTheme` tokens.** A smaller set:

| Token | Purpose |
|---|---|
| `header_bg` / `header_text` | Node header strip |
| `body_bg` / `body_text` | Node content area |
| `border` / `border_selected` | Default and selected outlines |
| `port_inlet` / `port_outlet` | Data port fill colours |
| `port_exec_inlet` / `port_exec_outlet` | Control-flow port colours |
| `error_bg` / `error_border` | Error-state colours |
| `muted_opacity` | CSS opacity for disabled state |

Access tokens via `theme.get_color('token_name')` — returns `''` for missing tokens (no exception, safe to call unconditionally).

**Subclassing for partial overrides.** Override only the tokens you want; everything else inherits:

```python
from haywire.ui.themes.builtin import HaywireDarkTheme

@theme(label='Dark — Red Accent')
class DarkRedAccentTheme(HaywireDarkTheme):
    accent = '#e74c3c'
    accent_hover = '#ec7063'
    node_selected = '#e74c3c'
    edge_selected = '#e74c3c'
```

**`to_css_vars()`** (WorkbenchTheme only). Returns the complete `{'--hw-token': value, ...}` dict by walking `_CSS_TOKEN_MAP`. Tokens missing from the subclass fall back to parent values; tokens defined in the class but not in the map are silently dropped.

**Active theme selection.** Two TOML keys (under settings):

```toml
[workbench]
theme = "mylib:theme:workbench:my-dark"

[node]
theme = "mylib:theme:node:my-nodes"
```

The studio's `AppShell.apply_workbench_theme()` reads the workbench theme key, calls `theme_registry.get_workbench(key)`, then injects each token via `document.documentElement.style.setProperty(...)`. Live — no page reload.

**Imports.** Use these (verified against codebase 2026-05):

```python
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.registry import ThemeRegistry
```

(Older docs reference `haywire.ui.themes.theme_registry` — that path is out of date; the file is `registry.py`.)

**Registration in a library.** Themes are discovered via `register_components()` like any other component:

```python
def register_components(self, registries):
    theme_registry = registries.get(ThemeRegistry)
    if theme_registry:
        theme_registry.register_workbench(MyDarkTheme)
        theme_registry.register_node_theme(MyNodeTheme)
```

A library can register any number of workbench and node themes. `registry_id` values must be unique within the library — and globally unique once libraries merge in `ThemeRegistry`. Prefix with the library name (`mylib-dark`, `mylib-nodes`) to avoid collisions.

**Hot-reload.** `ThemeRegistry` extends `BaseRegistry`, so when a library's theme file changes:

1. `BaseRegistry._unregister_class(registry_key)` removes the old class.
2. The reloaded module re-runs `register_components()`, registering the updated class.
3. Sessions with that theme active receive the new tokens; `apply_workbench_theme()` re-injects CSS variables; node renderers re-fetch token colours.

No author code is needed — the framework handles the loop.

## 4. One comprehensive example

A library `haybale-blueprint` ships a paired set: a `BlueprintWorkbenchTheme` (full token list demonstrating every category), a partial `BlueprintRedAccentTheme` (subclass overriding only the accent colours), a `BlueprintNodeTheme` (full node tokens), and the registration hookup. All decorations exercise `@theme`, all hot-reload paths are wired through `register_components()`.

```python
# haybale_blueprint/themes/workbench.py
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.decorator import theme


@theme(label='Blueprint — Dark')
class BlueprintWorkbenchTheme(WorkbenchTheme):
    """Full workbench theme. Every token explicitly set."""

    # Backgrounds
    bg_page    = '#060d18'
    bg_surface = '#0f1c2e'
    bg_sidebar = '#0d1726'
    bg_elevated = '#162337'
    bg_overlay = 'rgba(0,0,0,0.6)'
    bg_input   = '#0a0f1a'

    # Borders
    border        = 'rgba(255,255,255,0.08)'
    border_strong = '#2a4a6a'

    # Text
    text_body      = 'rgba(200,220,255,0.9)'
    text_muted     = 'rgba(200,220,255,0.55)'
    text_dim       = 'rgba(200,220,255,0.45)'
    text_expansion = 'rgba(200,220,255,0.75)'
    text_on_accent = '#ffffff'

    # Accent
    accent        = '#3498db'
    accent_hover  = '#5dade2'
    accent_active = '#1f6aa5'

    # Status
    danger  = '#e74c3c'
    warning = '#f39c12'
    success = '#2ecc71'
    info    = '#3498db'

    # Node chrome (cascaded into node body via CSS tokens)
    node_bg          = '#0f1c2e'
    node_border      = '#1a3050'
    node_header_bg   = '#162337'
    node_header_text = 'rgba(200,220,255,0.9)'
    node_selected    = '#3498db'
    node_shadow      = 'rgba(0,0,0,0.5)'

    # Edges
    edge_default  = '#2a4a6a'
    edge_selected = '#3498db'

    # Canvas
    canvas_bg   = '#060d18'
    canvas_grid = '#0d1726'

    # TopBar
    topbar_bg   = '#0a0f1a'
    topbar_text = 'rgba(200,220,255,0.9)'

    # Sidebars / ActivityBar
    sidebar_bg          = '#060d18'
    sidebar_icon        = '#3a5a7a'
    sidebar_icon_active = '#3498db'

    # Panels
    panel_bg   = '#0f1c2e'
    panel_text = 'rgba(200,220,255,0.87)'

    # StatusBar
    statusbar_bg   = '#0a2040'
    statusbar_text = 'rgba(200,220,255,0.7)'

    # Console
    console_bg   = '#060d18'
    console_text = '#4ade80'


# Partial override demonstrating subclassing — only red accents differ.
@theme(label='Blueprint — Red Accent')
class BlueprintRedAccentTheme(BlueprintWorkbenchTheme):
    """Inherits every token from BlueprintWorkbenchTheme; overrides only
    the four accent-related ones. Demonstrates partial themes."""
    accent        = '#e74c3c'
    accent_hover  = '#ec7063'
    accent_active = '#c0392b'
    node_selected = '#e74c3c'
    edge_selected = '#e74c3c'
```

```python
# haybale_blueprint/themes/node.py
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme


@theme(label='Blueprint — Nodes')
class BlueprintNodeTheme(NodeTheme):
    """Full node theme — paired with BlueprintWorkbenchTheme above.
    Independent of workbench themes; user can mix freely."""

    header_bg        = '#0d2137'
    header_text      = '#a0d8ef'
    body_bg          = '#091929'
    body_text        = '#c0e0f8'
    border           = '#1a3a5c'
    border_selected  = '#00bfff'
    port_inlet       = '#00aaff'
    port_outlet      = '#ff6600'
    port_exec_inlet  = '#ffffff'
    port_exec_outlet = '#ffffff'
    error_bg         = '#1f0a0a'
    error_border     = '#ff4444'
    muted_opacity    = '0.4'
```

```python
# haybale_blueprint/__init__.py
from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library
from haywire.ui.themes.registry import ThemeRegistry

from .themes.workbench import (
    BlueprintWorkbenchTheme,
    BlueprintRedAccentTheme,
)
from .themes.node import BlueprintNodeTheme


@library(label='Blueprint Theme', file_watcher=True)
class Library(BaseLibrary):
    """Hot-reload enabled — editing any theme file applies the change live
    via the BaseRegistry hot-reload pipeline."""

    def register_components(self, registries):
        theme_registry = registries.get(ThemeRegistry)
        if theme_registry is None:
            return

        # Multiple workbench themes from one library
        theme_registry.register_workbench(BlueprintWorkbenchTheme)
        theme_registry.register_workbench(BlueprintRedAccentTheme)

        # Plus a node theme
        theme_registry.register_node_theme(BlueprintNodeTheme)

    def validate(self) -> bool:
        return True
```

What this example exercises:

| Concept | Where it shows up |
|---|---|
| Full `WorkbenchTheme` covering every token category | `BlueprintWorkbenchTheme` |
| Partial subclass overriding only specific tokens | `BlueprintRedAccentTheme(BlueprintWorkbenchTheme)` |
| Full `NodeTheme` with all node-specific tokens | `BlueprintNodeTheme` |
| `@theme(label=...)` decorator on every class | all three |
| Plain string attributes (not `field()` descriptors) | every token assignment |
| Imports from canonical module paths | `haywire.ui.themes.workbench`, `haywire.ui.themes.node_theme`, `haywire.ui.themes.decorator`, `haywire.ui.themes.registry` |
| Registration via `register_components()` | `Library.register_components` |
| Multiple themes per library | three classes registered |
| Hot-reload via `file_watcher=True` | `@library(file_watcher=True)` |

**Active theme selection** (user-side, in their TOML):

```toml
[workbench]
theme = "haybale_blueprint:theme:workbench:blueprint-dark"

[node]
theme = "haybale_blueprint:theme:node:blueprint-nodes"
```

**Reading tokens at runtime** (e.g. in tests):

```python
from haywire.ui.themes.registry import ThemeRegistry

r = ThemeRegistry()
r.register_workbench(BlueprintWorkbenchTheme)
r.register_node_theme(BlueprintNodeTheme)

theme = r.get_workbench(BlueprintWorkbenchTheme.class_identity.registry_key)
css = theme.to_css_vars()
assert css['--hw-bg-page'] == '#060d18'
assert css['--hw-accent']  == '#3498db'
assert all(k.startswith('--hw-') for k in css)

node_theme = r.get_node_theme(BlueprintNodeTheme.class_identity.registry_key)
assert node_theme.get_color('header_bg') == '#0d2137'
assert node_theme.get_color('nonexistent') == ''   # safe — no error
```

For the design tokens themselves (the `--hw-*` palette) and rules about when to use them, see [reference/design-guide](../../reference/design-guide.md). For the studio shell that applies themes and the live re-injection mechanism, see [architecture/studio/app-shell](../../architecture/studio/app-shell/app-shell-arch.md).

---

## Quick reference

### Authoring checklist

- [ ] `@theme(label='...')` decorator on every subclass
- [ ] Class name ends in `Theme` and is library-prefixed for uniqueness
- [ ] Inherit from `WorkbenchTheme` or `NodeTheme` (or another `@theme`-decorated class)
- [ ] Override only the tokens you need; rest inherits silently
- [ ] Register in `Library.register_components()` via the right method (`register_workbench` / `register_node_theme`)
- [ ] Tests: `r.get_workbench(...).to_css_vars()` keys all start with `--hw-`; `node_theme.get_color('missing')` returns `''`

### Imports

```python
from haywire.ui.themes.workbench import WorkbenchTheme
from haywire.ui.themes.node_theme import NodeTheme
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.registry import ThemeRegistry
```

### Registry methods

```python
theme_registry.register_workbench(MyTheme)
theme_registry.register_node_theme(MyNodeTheme)
theme_registry.list_workbench_keys()       # ['core:theme:workbench:haywire-dark', ...]
theme_registry.list_node_theme_keys()      # ['core:theme:node:default', ...]
theme_registry.get_workbench(registry_key) # fresh instance — themes are stateless
theme_registry.get_node_theme(registry_key)
```
