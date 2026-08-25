---
status: draft
doc_template: canonical-example
scope: Authoring WorkbenchTheme and NodeTheme subclasses, registering them in a library, hot-reload behaviour
see-also:
  - ../skins/skin-canon.md
  - ../../haybale/haybale-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../architecture/hot-reload/hot-reload-arch.md
  - ../../reference/glossary.md
---

# Theme — Canonical Example

## 1. What it solves

A **theme** controls the visual appearance of haywire. Two theme types exist:

- **`WorkbenchTheme`** — the *application shell*: page backgrounds, sidebars, top bar, status bar, panel surfaces, canvas grid, accent colours, edge colours, and the node tokens. Carries the **full** token vocabulary, injected as CSS custom properties on `:root`.
- **`NodeTheme`** — the **node-scoped subset** of that same vocabulary. Not a second theme system: it declares the same token names (`node_bg`, `node_border_color`, …) and emits them through the same `to_css_vars()`. What differs is only *where* the result is injected, and therefore what it overrides.

Both share one `_CSS_TOKEN_MAP`, deliberately: a node theme cannot name a token the workbench does not have. As an author, you subclass the relevant base, override only the tokens you want to change, decorate with `@theme(label=...)`, and register the class in your library's `register_components()`.

**Nothing reads a theme in Python.** A skin emits `background: var(--hw-node-bg)` once and never branches on a theme, a graph, or a node. Overriding is pure CSS cascade — which is what makes a per-node colour a *style-write on a stable element* rather than a card redraw.

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

**`NodeTheme` tokens — Tier 1.** The node-scoped subset, listed in `NODE_TIER_TOKENS`:

| Token | Purpose |
|---|---|
| `node_bg` | Card background. May hold a **gradient** — see the trap below |
| `node_border_color` | Card border colour |
| `node_border_width` | Card border thickness, e.g. `"3px"` |
| `node_border_radius` | Card corner radius, e.g. `"16px"` |
| `node_header_bg` | Header strip background |
| `node_header_text_color` | Header label colour |
| `node_text_color` | Card body text colour |

Lengths carry their unit **inside the value** (`"3px"`, not `3`): `var()` is textual substitution, so `border: 3 solid red` is invalid CSS and fails silently.

**Tier 2 — global and graph tiers only.** `node_selected`, `node_active`, and `node_shadow` are real tokens, but `canvas.vue` consumes them on `[data-node-id]`, which is an **ancestor** of the element a node-tier theme writes to. Custom properties inherit downward only, so:

| Tier | Written on | Reaches Tier 2? |
| --- | --- | --- |
| global | `:root` | yes |
| graph | `.graph-canvas` | yes |
| node | `.ui-node-slot` | **no** |

A node theme selected on a single node silently cannot restyle that node's selection ring. This is a real asymmetry, not an oversight — put selection/active/shadow changes on the graph or global tier.

There is no `get_color()`. `to_css_vars()` is the only way to read a theme, because the only consumer is CSS injection.

**The tier chain.** A node theme can be selected at three levels, each writing its vars onto a different element. CSS inheritance does the layering — no code merges anything:

```text
:root                 WorkbenchTheme                    every token
:root                 global NodeTheme                  ui.node.default.skin.studio_node_theme
.graph-canvas         graph's  props.node_theme         only if ≠ global
.ui-node-slot         node's   props.node_theme         only if ≠ graph
.ui-node-slot         node's   props.color_override     --hw-node-bg, composed LAST
```

Two rules make this cheap and predictable:

- **A tier writes nothing unless it diverges** from the tier above, decided by comparing resolved values. Identical values produce identical CSS, so writing them is waste — on a 200-node graph, the difference between one declaration set and two hundred.
- **`color_override` always wins** over a node's own theme, because it is composed last in the same declaration string, and later declarations of a custom property win.

Clearing a field returns it to inheriting: emptiness *is* the unset mechanism, so no "is this locally set?" question arises anywhere in the chain.

**Switching the global node theme clears before it sets.** `setProperty` only writes what the new theme mentions, so a theme that omits a token would otherwise leave the previous theme's value stranded on `:root`. Every `NODE_TIER_TOKENS` var is removed first, letting the workbench theme's own value show through for anything the new theme is silent on.

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

## 4. Live examples from the codebase

Source: [`barn/haybale-testing/haybale_testing/themes/`](../../../barn/haybale-testing/haybale_testing/themes/)

**WorkbenchTheme** — `TestDarkTheme` sets every token category (backgrounds, borders, text, accents, status, node chrome, edges, canvas, topbar, sidebars, panels, statusbar, console). `TestLightTheme` inherits from `WorkbenchTheme` directly and overrides only the values that differ from a light palette — demonstrating partial subclassing:

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/workbench.py:11:68"
```

from: `TestDarkTheme` — registry_key: `haybale-testing:theme:workbench:TestDarkTheme`

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/workbench.py:70:129"
```

from: `TestLightTheme` — registry_key: `haybale-testing:theme:workbench:TestLightTheme`

**NodeTheme** — `TestNodeTheme` sets all node-specific tokens. Independent of workbench themes; users mix freely:

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/node.py:9:28"
```

from: `TestNodeTheme` — registry_key: `haybale-testing:theme:node:TestNodeTheme`

What these examples exercise:

| Concept | Where it shows up |
|---|---|
| Full `WorkbenchTheme` covering every token category | `TestDarkTheme` |
| Second `WorkbenchTheme` variant in the same file | `TestLightTheme` |
| `@theme(label=...)` decorator on every class | all three |
| Plain string attributes (not descriptors) | every token assignment |
| Full `NodeTheme` with all node-specific tokens | `TestNodeTheme` |
| Imports from canonical module paths | `haywire.ui.themes.workbench`, `haywire.ui.themes.node_theme`, `haywire.ui.themes.decorator` |

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
node_css = node_theme.to_css_vars()
assert node_css['--hw-node-header-bg'] == '#0d2137'
assert '--hw-not-a-token' not in node_css   # unmapped fields are dropped
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
- [ ] Tests: `r.get_workbench(...).to_css_vars()` keys all start with `--hw-`; a `NodeTheme` emits only `NODE_TIER_TOKENS`

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
