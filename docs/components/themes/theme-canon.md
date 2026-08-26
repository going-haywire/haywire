---
status: draft
doc_template: canonical-example
scope: Authoring BaseTheme subclasses with @theme, registering them in a library, hot-reload behaviour
see-also:
  - ../skins/skin-canon.md
  - ../../haybale/haybale-canon.md
  - ../../architecture/studio/studio-arch.md
  - ../../architecture/hot-reload/hot-reload-arch.md
  - ../../reference/glossary.md
---

# Theme — Canonical Example

## 1. What it solves

A **theme** controls the visual appearance of haywire. There is one theme class, `BaseTheme`, carrying the full `--hw-*` token vocabulary. A theme is either workbench-flavoured or node-flavoured, decided by the required `theme_type` argument on the `@theme` decorator — not by which class you subclass:

- **`theme_type='workbench'`** — the *application shell*: page backgrounds, sidebars, top bar, status bar, panel surfaces, canvas grid, accent colours, edge colours, and the node tokens. Injected as CSS custom properties on `:root`.
- **`theme_type='node'`** — the same token vocabulary, injected at a later cascade position (`.graph-canvas` or `.ui-node-slot` instead of `:root`), so it overrides only what the tier above it also set.

`theme_type` is stamped onto `class_identity`; that field, not the class you subclass, is what `ThemeRegistry` and the studio branch on. As an author, you subclass `BaseTheme`, override only the tokens you want to change, decorate with `@theme(theme_type='workbench', label=...)` or `@theme(theme_type='node', label=...)`, and register the class in your library's `register_components()`.

**Nothing reads a theme in Python.** A skin emits `background: var(--hw-node-bg)` once and never branches on a theme, a graph, or a node. Overriding is pure CSS cascade — which is what makes a per-node colour a *style-write on a stable element* rather than a card redraw.

Themes are *not* the same as **skins** (per-node visual variants of the node body — see [components/skins](../skins/skin-canon.md)). A node-flavoured theme may override the same panel-facing tokens skins and panels read (`text_body`, `bg_input`, ...), scoped to the DOM subtree its declarations are injected into (`.graph-canvas` or `.ui-node-slot`), never globally. See §3, "Full token vocabulary at every tier."

## 2. How it fits

```text
Author declares                Library registers              Studio applies
────────────────               ─────────────────              ──────────────
@theme(theme_type='workbench') theme_registry.register_       Active theme:
class FooTheme(                  workbench(FooTheme)              workbench.theme
    BaseTheme):                theme_registry.register_           in TOML
   bg_page = '#0a0f1a'           node_theme(BarTheme)
   accent  = '#3498db'                                         AppShell.apply_
                                                                 workbench_theme()
@theme(theme_type='node')                                       → injects :root
class BarTheme(BaseTheme):                                         CSS variables
   node_bg = '#123456'                                             live, no reload
```

Every `BaseTheme` subclass shares two architectural facts:

- **Plain string class attributes**, not `field()` descriptors. `__init_subclass__` wraps them into `_FieldProxy` objects collected in `_fields`.
- **`ThemeRegistry`** (a `BaseRegistry` subclass) tracks registered classes by `registry_key`. Hot-reload is automatic — when a library reloads, the registry re-registers and the active theme is re-applied.

**Boundaries.** What CSS tokens *are* (the `--hw-*` design system) lives in [reference/design-guide](../../reference/design-guide.md). The studio shell that consumes themes lives in [architecture/studio](../../architecture/studio/studio-arch.md). The hot-reload pipeline that re-binds themes lives in [architecture/hot-reload](../../architecture/hot-reload/hot-reload-arch.md). The `theme` setting that selects the active theme lives in the [settings system](../settings/setting-canon.md).

## 3. Important concepts

**The `@theme` decorator.** Required on every theme subclass, with `theme_type` a required keyword argument (`'workbench'` or `'node'`). Sets `class_identity` (used by `BaseRegistry` for hot-reload), derives `registry_key` from the library and class name, and accepts a `label` for display.

```python
@theme(theme_type='workbench', label='My Dark Theme')
class MyDarkTheme(BaseTheme): ...

@theme(theme_type='node', label='My Node Theme')
class MyNodeTheme(BaseTheme): ...
```

**Plain string attributes, not descriptors.** Every theme field is a class-level string assignment:

```python
class FooTheme(BaseTheme):
    bg_page = '#0a0f1a'      # ← plain string class attribute
    accent  = '#3498db'      # ← not a field() descriptor
```

`BaseTheme.__init_subclass__` collects these into `_fields`. Defining a field that isn't in the token map is silently ignored (no error). Omitting a field is silently inherited from the parent class — partial themes work without ceremony.

**`_CSS_TOKEN_MAP`.** ~40 named tokens covering backgrounds, borders, text, accents, status colours, node chrome, edges, canvas, top bar, sidebars, panels, status bar, and console. Defined in `_CSS_TOKEN_MAP` mapping `field_name` → `--hw-<token>`. The full list is in [reference/design-guide](../../reference/design-guide.md); examples in §4.

**Full token vocabulary at every tier.** A node-flavoured theme may declare any token in `_CSS_TOKEN_MAP`, `text_body`/`bg_input`/`accent` included, not just the `node_*` group:

| Token | Purpose |
| --- | --- |
| `node_bg` | Card background. May hold a **gradient** — see the trap below |
| `node_border_color` | Card border colour |
| `node_border_width` | Card border thickness, e.g. `"3px"` |
| `node_border_radius` | Card corner radius, e.g. `"16px"` |
| `node_header_bg` | Header strip background |
| `node_header_text_color` | Header label colour |
| `node_text_color` | Card body text colour, incl. inline widgets — see the forwarding note below |

...plus every other token in the map (`text_body`, `bg_input`, `accent`, `border`, ...), scoped to whichever DOM subtree the theme's tier writes into.

Lengths carry their unit **inside the value** (`"3px"`, not `3`): `var()` is textual substitution, so `border: 3 solid red` is invalid CSS and fails silently.

**Widget content inside a node card follows the node theme too.** A Quasar-backed widget (`ui.input`, `ui.select`, ...) does not inherit `color`/`background` from an ancestor the way a plain element does — Quasar paints its own field internals from its own defaults. `shell.py`'s `STATIC_CSS` carries a `.ui-node-slot`-scoped forwarding block (mirroring the `.hw-panel` one panels use) that routes `q-field__control`, `q-field__label`, etc. through the same semantic tokens (`--hw-text-body`, `--hw-bg-input`, ...) — so a node-flavoured theme overriding those tokens reaches widget text/backgrounds inside its scope, not just the card chrome. The node title's text colour specifically resolves `--hw-node-text-color` with a fallback to `--hw-text-body`, so an explicit node-tier `node_text_color` still wins there.

**Tier 2 tokens are declarable everywhere, but only reachable from global and graph tiers.** `node_selected`, `node_active`, and `node_shadow` are real, mapped tokens — a node-flavoured theme may set them like any other. But `canvas.vue` consumes them on `[data-node-id]`, which is an **ancestor** of `.ui-node-slot` (the element a node-tier theme writes to). Custom properties inherit downward only, so:

| Tier | Written on | Reaches Tier 2? |
| --- | --- | --- |
| global | `:root` | yes |
| graph | `.graph-canvas` | yes |
| node | `.ui-node-slot` | **no** |

A node theme selected on a single node writes a value for these three tokens but it is never visibly applied — that node's selection ring silently ignores it. Put selection/active/shadow changes on the graph or global tier.

There is no `get_color()`. `to_css_vars()` is the only way to read a theme, because the only consumer is CSS injection.

**The tier chain.** A node theme can be selected at three levels, each writing its vars onto a different element. CSS inheritance does the layering — no code merges anything:

```text
:root                 the active workbench theme        every token
:root                 global node theme                 ui.node.default.skin.studio_node_theme
.graph-canvas         graph's  props.node_theme          only if ≠ global
.ui-node-slot         node's   props.node_theme           only if ≠ graph
.ui-node-slot         node's   props.color_override       --hw-node-bg, composed LAST
```

Two rules make this cheap and predictable:

- **A tier writes nothing unless it diverges** from the tier above, decided by comparing resolved values. Identical values produce identical CSS, so writing them is waste — on a 200-node graph, the difference between one declaration set and two hundred.
- **`color_override` always wins** over a node's own theme, because it is composed last in the same declaration string, and later declarations of a custom property win.

Clearing a field returns it to inheriting: emptiness *is* the unset mechanism, so no "is this locally set?" question arises anywhere in the chain.

**Switching the global node theme clears before it sets.** `setProperty` only writes what the new theme mentions, so a theme that omits a token would otherwise leave the previous theme's value stranded on `:root`. Every token in `_CSS_TOKEN_MAP` is removed first, letting the active workbench theme's own stylesheet value show through for anything the new theme is silent on. This only touches the inline style on `documentElement`, never the `:root {}` rule the initial page load writes into the page's stylesheet, so the workbench baseline is always there to fall back to.

**Subclassing for partial overrides.** Override only the tokens you want; everything else inherits:

```python
from haywire.ui.themes.builtin import HaywireDarkTheme

@theme(theme_type='workbench', label='Dark — Red Accent')
class DarkRedAccentTheme(HaywireDarkTheme):
    accent = '#e74c3c'
    accent_hover = '#ec7063'
    node_selected = '#e74c3c'
    edge_selected = '#e74c3c'
```

**`to_css_vars()`.** Returns the complete `{'--hw-token': value, ...}` dict by walking `_CSS_TOKEN_MAP`. Tokens missing from the subclass fall back to parent values; tokens defined in the class but not in the map are silently dropped.

**Active theme selection.** Two TOML keys (under settings):

```toml
[workbench]
theme = "mylib:theme:my-dark"

[node]
theme = "mylib:theme:my-nodes"
```

The studio's `AppShell.apply_workbench_theme()` reads the workbench theme key, calls `theme_registry.get_workbench(key)`, then injects each token via `document.documentElement.style.setProperty(...)`. Live — no page reload.

**Imports.**

```python
from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.registry import ThemeRegistry
```

**Registration in a library.** Themes are discovered via `register_components()` like any other component:

```python
def register_components(self, registries):
    theme_registry = registries.get(ThemeRegistry)
    if theme_registry:
        theme_registry.register_workbench(MyDarkTheme)
        theme_registry.register_node_theme(MyNodeTheme)
```

A library can register any number of workbench and node themes. `registry_id` values must be unique within the library — and globally unique once libraries merge in `ThemeRegistry`. Prefix with the library name (`mylib-dark`, `mylib-nodes`) to avoid collisions.

**Registry key format.** A theme's `registry_key` is the standard 3-segment `lib:theme:id` shape, the same shape every other component kind uses. `theme_type` lives entirely in `class_identity`, read by `ThemeRegistry`'s typed accessors (`get_workbench`/`get_node_theme` each filter by it and raise `KeyError` for the wrong flavour).

**Hot-reload.** `ThemeRegistry` extends `BaseRegistry`, so when a library's theme file changes:

1. `BaseRegistry._unregister_class(registry_key)` removes the old class.
2. The reloaded module re-runs `register_components()`, registering the updated class.
3. Sessions with that theme active receive the new tokens; `apply_workbench_theme()` re-injects CSS variables; node renderers re-fetch token colours.

No author code is needed — the framework handles the loop.

## 4. Live examples from the codebase

Source: [`barn/haybale-testing/haybale_testing/themes/`](../../../barn/haybale-testing/haybale_testing/themes/)

**Workbench-flavoured** — `TestDarkTheme` sets every token category (backgrounds, borders, text, accents, status, node chrome, edges, canvas, topbar, sidebars, panels, statusbar, console). `TestLightTheme` inherits from `BaseTheme` directly and overrides only the values that differ from a light palette — demonstrating partial subclassing:

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/workbench.py:11:68"
```

from: `TestDarkTheme` — registry_key: `haybale-testing:theme:TestDarkTheme`

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/workbench.py:70:129"
```

from: `TestLightTheme` — registry_key: `haybale-testing:theme:TestLightTheme`

**Node-flavoured** — `TestNodeTheme` sets node-specific tokens. Independent of workbench themes; users mix freely:

```python
--8<-- "barn/haybale-testing/haybale_testing/themes/node.py:9:23"
```

from: `TestNodeTheme` — registry_key: `haybale-testing:theme:TestNodeTheme`

What these examples exercise:

| Concept | Where it shows up |
| --- | --- |
| Full `BaseTheme` covering every token category | `TestDarkTheme` |
| Second workbench-flavoured variant in the same file | `TestLightTheme` |
| `@theme(theme_type=..., label=...)` decorator | all three |
| Plain string attributes (not descriptors) | every token assignment |
| Node-flavoured theme with node-specific tokens | `TestNodeTheme` |
| Imports from canonical module paths | `haywire.ui.themes.workbench`, `haywire.ui.themes.decorator` |

**Active theme selection** (user-side, in their TOML):

```toml
[workbench]
theme = "haybale_blueprint:theme:blueprint-dark"

[node]
theme = "haybale_blueprint:theme:blueprint-nodes"
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

- [ ] `@theme(theme_type=..., label='...')` decorator on every subclass — `theme_type` is required
- [ ] Class name ends in `Theme` and is library-prefixed for uniqueness
- [ ] Inherit from `BaseTheme` (or another decorated `BaseTheme` subclass)
- [ ] Override only the tokens you need; rest inherits silently
- [ ] Register in `Library.register_components()` via the right method (`register_workbench` / `register_node_theme`)
- [ ] Tests: `r.get_workbench(...).to_css_vars()` keys all start with `--hw-`; `class_identity.theme_type` matches the decorator argument used

### Imports

```python
from haywire.ui.themes.workbench import BaseTheme
from haywire.ui.themes.decorator import theme
from haywire.ui.themes.registry import ThemeRegistry
```

### Registry methods

```python
theme_registry.register_workbench(MyTheme)
theme_registry.register_node_theme(MyNodeTheme)
theme_registry.list_workbench_keys()       # ['core:theme:haywire-dark', ...]
theme_registry.list_node_theme_keys()      # ['core:theme:default', ...]
theme_registry.get_workbench(registry_key) # fresh instance — themes are stateless
theme_registry.get_node_theme(registry_key)
```
