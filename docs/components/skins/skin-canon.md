---
status: placeholder
doc_template: canonical-example
scope: Authoring node skins (visual variants of a node's rendering)
see-also:
  - ../widgets/widget-canon.md
---

# Skin — Canonical Example

*This is a placeholder — the worked example below has not been written yet. One section
is filled in: [The card's class list is a contract](#the-cards-class-list-is-a-contract),
because omitting a class from it fails silently and has already cost real debugging time.*

**Template:** `canonical-example` — when filled in, this file will follow the four-part shape:

1. **What it solves.** Capability statement: "you can do X with this."
2. **How it fits.** Where this component sits in the system; what it depends on; what depends on it.
3. **Important concepts.** The named entities and rules an author needs in their head.
4. **One comprehensive example.** A single worked example exercising every concept above.

**Scope.** Authoring node skins (visual variants of a node's rendering).

## The card's class list is a contract

A skin's `render()` receives a `ui.card` and decides its classes. Some of the classes it
must apply are **not** styling choices — the canvas and pan layers key behaviour off them,
so a card that omits one loses that behaviour with no error, no console warning, and
usually no visible symptom until a user does something specific.

```python
main_card.classes("w-full min-w-64 max-w-sm node-card zoom-pan-lod0 my-skin-card")
```

| Class | Owner | What it buys | Symptom if omitted |
| --- | --- | --- | --- |
| `node-card` | `canvas.vue`, `pan.vue` | Manual-resize clamp release; `pointer-events` / `user-select` restored inside the pan container | Card stops growing partway through a resize drag; text selection and pointer behaviour fall back to the pan container's suppression |
| `zoom-pan-lod0` | `pan.vue` | Hover box-shadow, magnifier transform transition, and the hover tracking that drives `zoom-pan-lod1..3` reveal on descendants | No hover affordance; nested LOD elements may not reveal on hover |
| `drag-handle` | `canvas.vue` | Makes the element (or a child carrying it) the drag grip | Node cannot be dragged by that region |

### `node-card` is a literal token, not a prefix

CSS class selectors match **whole tokens**. `my-skin-card`, `math-node-card`, and
`error-node-card` do *not* match `.node-card` — they are sibling classes, not variants.
Name your skin's own class whatever you like, but apply `node-card` **alongside** it.

The rule that bites is the manual-resize clamp release in `canvas.vue`:

```css
--8<-- "packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:node-card-manual-resize"
```

Manual size axes are user **minimums** written onto the host slot; content needing more
space expands the node, and nothing clips. For the card to track the slot, the skin's own
clamps (`min-w-64 max-w-sm`) have to be released — which is what that rule does, and only
for elements carrying `node-card`.

So a skin without the class renders correctly at rest and **caps at `max-w-sm` (384px)
the moment someone drags the resize grip**, while the slot underneath keeps expanding.
Nothing reports it. If you are debugging "my node stops growing", check the class list
first.

> Related: a node's minimum size is not computed in Python at all — it is whatever CSS
> intrinsic sizing produces from the card subtree. Measuring it in `auto` mode measures
> the clamp rather than the content. See `.insights/feedback_css_containment_node_floor.md`.

### Do not style `.widget-container`

Inline-widget reveal is owned by the framework, not by the skin. `canvas.vue` declares:

```css
--8<-- "packages/haywire-core/src/haywire/ui/components/graph/canvas.vue:widget-container-reveal"
```

Two consequences for skin authors:

1. A skin's own `opacity` / `max-height` rules on `.widget-container` are silently
   outranked. A `:hover`-based reveal in a skin's stylesheet simply never fires — the
   framework reveals on **`.node-selected`**, which it puts on the `[data-node-id]`
   container (an *ancestor* of the card), not on the card itself.
2. `!important` on the `transition` shorthand replaces the whole property, so even
   properties the framework does not set — `transform`, say — stop animating.

Per-widget size and reveal ceilings are declared on the widget instead, through
`@widget(min_width=, min_height=, max_height=)`. See
[widget-canon.md](../widgets/widget-canon.md).

## TODO

- [ ] Write content
- [ ] Document `@skin(hidden=True)` — registers a skin normally but excludes it from the skin picker (used by the error/fallback skin, which sets `_is_error=True, hidden=True`). See glossary term **Hidden component**.
- [ ] Verify against codebase
- [ ] Archive source files
