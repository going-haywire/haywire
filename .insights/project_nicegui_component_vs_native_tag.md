# A NiceGUI element that is a COMPONENT costs ~3x one that is a native tag

NiceGUI renders the entire page as **one** Vue component
(`nicegui.js`: `render() { return renderRecursively(this.elements, 0) }`).
There is no memoization — upstream added a vnode cache (PR #5761) and
**reverted** it; verified still absent in the shipped 3.13.0 bundle. So every
server message rebuilds a VNode for every element on the page, and the studio's
responsiveness is a function of element count times per-element cost.

The per-element cost is not uniform, and that is the part you cannot see:

```js
Vue.h(app.config.isNativeTag(element.tag) ? element.tag : Vue.resolveComponent(element.tag), ...)
```

A tag Vue considers native (`div`, `i`, `span`) becomes an element VNode.
Anything else (`q-icon`, `nicegui-drag`, any `.vue` component) is resolved to a
component and gets a component instance, its own props validation, and its own
render on patch.

## Measured, on `graphs/10x300nodes.haywire` in headless Chrome

One whole-page update (`$forceUpdate()` → `nextTick`), median of 9:

| tree | update |
|---|---|
| as shipped, 33,954 elements | **723 ms** |
| 6,611 `q-icon` retagged to `div` (count unchanged) | 545 ms |
| 3,294 `nicegui-drag` retagged to `div` | 614 ms |
| both | 513 ms |

**~30% of the cost was paid purely for componentness** — same element count,
same layout, same DOM. Roughly: a plain div ~15 µs, a component ~40-45 µs.

Acting on it for real (pins, `pin_render.py`) measured **723 → 619 ms, −14%**.
Note the retag simulation over-predicted (it suggested −25%): retagging a
mounted element is not the same as constructing a different one, so treat the
retag trick as a *ranking* tool, not a forecast.

## Why this hides

Nothing about it is visible in a rendered card — the retag experiment above
changes no pixels. A skin author who reaches for `ui.icon` instead of a native
tag makes every interaction in the studio slower and sees a pin that looks
exactly right. It also does not show up per-node: one node is imperceptible,
and the cost only becomes a complaint at a few hundred.

`fps` will not find it either, and neither will a profile of the *canvas* — the
tax is paid on the root component's update, so it lands on unrelated
interactions (clicking a Properties field, switching a tab) far from the graph.

## The rule

On anything rendered **per port or per node**, prefer a native tag. If you need
a Quasar component's *look*, take its CSS classes rather than the component:
`.q-icon` and `.material-icons` are plain stylesheet rules and work fine on an
`<i>` you build yourself. That is exactly what
`haywire.ui.skin.pin_render.PinGlyph` does — identical markup and identical
computed box (verified property by property against the old `q-icon`), no
component. Locked by `tests/ui/skin/test_pin_native_tag_contract.py`.

Carry the props the component used to interpret for you: `q-icon`'s `size` and
`color` are meaningless on a native tag and become an inline `font-size` and
either an inline `color` or a `text-*` class (mirroring NiceGUI's
`TextColorElement`).

## Also true, and easy to get wrong

- **The walk currency is NiceGUI elements, not DOM nodes.** A custom Vue
  component is ONE element however much DOM its template emits — the 300-node
  fixture is 33,954 elements against 50,729 DOM nodes. Counting DOM overstates
  some things and hides others.
- **Culling client-side does not work.** Detaching a subtree by editing
  `children` in the client's `elements` is undone: the server re-sends the
  parent and restores it within ~2 s. Viewport culling has to be a real
  server-side unmount.
- **An inactive graph is nearly free.** Slots use `keep-alive`, so a
  deactivated tab's subtree is not re-rendered — a 60-node graph active with
  the 300-node graph kept alive measured 139 ms. This is why "it gets fast
  again when I switch to a small graph" is a symptom of this and not of
  anything graph-specific.

Instruments: `.scratch/pan-perf/session.py` drives a live studio headlessly.
The root instance is reachable as `mounted_app` (a module-scope `let`, NOT on
`window`) or `document.getElementById('c0').__vueParentComponent.proxy`. Do not
time `inst.render.call(app, app)` on its own — outside a rendering instance
`Vue.resolveComponent` takes a warning path and the number is inflated; measure
`$forceUpdate()` → `nextTick` instead.

Related: [[project_large_graph_perf]], [[project_chrome_layerize_3d_transform]].
