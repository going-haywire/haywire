---
name: theme-full-vocabulary-and-collapse
description: A theme may override any token in the shared vocabulary regardless of tier, widget content inside a node card is brought into the token cascade via CSS forwarding, WorkbenchTheme/NodeTheme collapse into one BaseTheme class distinguished by a required theme_type decorator argument, and theme registry keys drop to the standard 3-segment shape
status: accepted
level: architectural
---

# A theme may draw from the full token vocabulary; one BaseTheme class; 3-segment keys

> **Extends [ADR 0030](0030-node-theme-cascade.md).** The cascade model,
> tier-divergence rules, and `color_override` composition from 0030 are
> unchanged. What changes is the *vocabulary* a node/graph-tier theme may
> draw from (all of it, not a curated subset) and the *class shape* authors
> write against (one `BaseTheme` class). 0030's own token table and
> `NODE_TIER_TOKENS` references describe the superseded, narrower
> vocabulary — this ADR is current.

## Decision

**1. A node-flavoured theme may declare any token in `_CSS_TOKEN_MAP`.**
`NODE_TIER_TOKENS` — a curated 7-token allow-list — does not exist. The
node-tier write path (`ui_node.py`) and the global clear-then-set
(`shell.py`) both iterate the full token map. `node_selected`/`node_active`/
`node_shadow` remain structurally inert at the node tier: `[data-node-id]`
(where `canvas.vue` consumes them) sits above `.ui-node-slot`, and custom
properties inherit downward only. A node-authored theme may still declare
those three tokens; they simply have no visible effect there. The graph
tier is unfiltered and reaches all three.

**2. Widget content inside a node card is part of the cascade.**
Quasar-backed form controls (`ui.input`, `ui.select`, ...) do not inherit
`color`/`background` from an ancestor's plain CSS `color:` declaration —
they paint their own field internals (`q-field__control`, `q-field__label`,
...) from Quasar's own defaults. `shell.py`'s `STATIC_CSS` carries a
`.ui-node-slot`-scoped forwarding block (mirroring the `.hw-panel` one
panels use) so a theme's `text_body`/`bg_input`/etc. reaches widget content
inside a node card, not just the card's own chrome. Scoped strictly to
`.ui-node-slot`, never bare `.graph-canvas`: a `Popup`/context-menu already
carries `.hw-panel` and may render inside `.graph-canvas` (the canvas
right-click menu) but outside any `.ui-node-slot`, so it cannot match this
block and stays on the workbench tier exclusively.

The node title's own text colour resolves `var(--hw-node-text-color,
var(--hw-text-body))` rather than the bare semantic token — a matched class
selector always beats plain inheritance, so a bare `var(--hw-text-body)`
here would outrank the skin's own inline `color: var(--hw-node-text-color)`
on the card root. The fallback form keeps both live: an explicit node/graph
`node_text_color` wins; otherwise the body-text token shows through.

**3. `WorkbenchTheme` and `NodeTheme` collapse into one `BaseTheme` class.**
Workbench vs. node is a property of `class_identity.theme_type`
(`'workbench'`/`'node'`), a required keyword argument on `@theme`, not a
class you subclass:

```python
@theme(theme_type='workbench', label='...')
class MyWorkbenchTheme(BaseTheme): ...

@theme(theme_type='node', label='...')
class MyNodeTheme(BaseTheme): ...
```

`ThemeRegistry`'s typed accessors (`get_workbench`/`get_node_theme`, the
`list_*` methods) filter on `class_identity.theme_type` rather than
`issubclass`. `ThemeRegistry` is parametrized `BaseRegistry[BaseTheme]`.

**4. Theme registry keys are the standard 3-segment shape.** A theme's
`registry_key` is `lib:theme:id` — the same shape every other component
kind uses (`node`, `skin`, `widget`, `setting`, ...). `theme_type` lives
entirely on `class_identity`, not in the key.

## Consequences

A node-flavoured theme can now set `text_body`, `bg_input`, `accent`, and
every other token in the full vocabulary, scoped to its own DOM subtree —
not just the `node_*` group. `design-guide.md` §2.7 and `theme-canon.md`
describe this current vocabulary.

Every `@theme`-decorated class in the codebase passes `theme_type` and
subclasses `BaseTheme`; there is no other supported form.

A theme registry key saved before this change (4-segment format) does not
resolve — the framework's existing unresolvable-key fallback (log-warn, the
tier above shows through) applies, same as any other unknown key.
Re-selecting the theme writes a current 3-segment key.

## Alternatives considered

**Two decorators, `@workbench_theme` / `@node_theme`**, each hardcoding
`theme_type` internally instead of one `@theme(theme_type=...)`. Rejected:
every other component decorator in this codebase (`@node`, `@panel`,
`@skin`, `@settings`) takes its discriminating field as a keyword argument
on one decorator, not as a choice between named entry points — `@theme`
follows the same pattern.

**A separate node-scoped token family for widgets** (e.g.
`node_widget_text`, `node_widget_bg`), parallel to the existing `node_*`
group. Rejected: the semantic tokens (`text_body`, `bg_input`) already mean
"body text" / "input background" everywhere else; a node theme overriding
them within its own DOM scope says the same thing without a second
vocabulary that could drift from the one panels use.
