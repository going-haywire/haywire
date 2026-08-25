# CSS-var theming: three ways to fail silently

Node styling is a CSS custom-property cascade (ADR-0030). It is declarative and
cheap, and every one of its failure modes is *quiet* — no exception, no log, no
CSS parse error. Three to know before debugging a node that renders wrong.

## 1. `background-color` silently drops a gradient token

A custom property holds an arbitrary token sequence, so this is a perfectly
valid declaration:

```python
node_bg = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"
```

Whether it *renders* is decided by the consuming property, not the var:

| consumer | `#1e1e2e` | `linear-gradient(…)` |
| --- | --- | --- |
| `background-color: var(--hw-node-bg)` | ✅ | ❌ dropped |
| `background: var(--hw-node-bg)` | ✅ | ✅ |

`background-color` accepts only a `<color>`; a gradient is an `<image>`, so the
declaration is invalid at computed-value time and vanishes — taking the card's
colour with it, not falling back to anything.

**Rule:** every consumer of a colour token uses the `background` shorthand.
`reroute_skin.py` was the last `background-color` holdout; it was fixed when the
cascade landed.

## 2. A field absent from `_CSS_TOKEN_MAP` is dropped

`to_css_vars()` walks the **map**, not `_fields`. A theme subclass can declare
any attribute it likes; if the name isn't a key in the shared token map, it
produces no var and no warning:

```python
@theme(label="Mine")
class MyNodeTheme(NodeTheme):
    node_backgruond = "#ff0000"   # typo → silently nothing
```

This is how `NodeTheme` stayed inert for a long time: it declared `body_bg`,
`port_inlet`, `error_bg` and friends, none of which were ever in the map, so
selecting a node theme changed no pixel — while the docs claimed its values were
"read by the canvas-side node renderer".

**Rule:** a new token means editing `_CSS_TOKEN_MAP` too. If a theme change has
no visible effect, check the map before checking anything else.

## 3. `.ui-node-slot` vars cannot reach `[data-node-id]`

Custom properties inherit **downward only**. The canvas DOM nests like this:

```text
.graph-canvas                    ← graph tier writes here
  [data-node-id]                 ← canvas.vue's selected/active/shadow rules
    .ui-node-slot                ← node tier + color_override write here
      .node-card                 ← the skin's own style
```

So a node-tier theme setting `node_selected` writes a var onto an element
*below* the rules that consume it. The declaration exists, is valid, and does
nothing. The graph and global tiers sit above `[data-node-id]` and work fine.

`NODE_TIER_TOKENS` exists to encode this: it lists Tier 1 only, so the per-node
write path cannot promise an override that silently fails. If a per-node theme
appears to ignore a token, check whether it's Tier 2.

## Bonus: a skin that defines a var on its own card becomes un-overridable

A skin with a look of its own must supply it as a `var()` **fallback**, not as a
definition:

```python
# WRONG — shadows every tier above; nothing can ever override this skin
main_card.style("--hw-node-bg: linear-gradient(...); background: var(--hw-node-bg);")

# RIGHT — the skin's value applies only while no tier has spoken
main_card.style("background: var(--hw-node-bg, linear-gradient(...));")
```

The card is a *child* of `.ui-node-slot`, so a var defined on the card wins over
the node, graph, and global tiers alike. `example_skin.py` shows the correct
form.
