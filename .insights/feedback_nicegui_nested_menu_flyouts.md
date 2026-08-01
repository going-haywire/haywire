---
name: NiceGUI nested menu flyouts inside a popup
description: Why ui.menu submenus break under NiceGUI 3.x and inside the context-menu Popup — z-index, click-not-hover, auto-close doesn't switch siblings, cascade-close
type: feedback
---

## Context

`NodeMenuBuilder` (`barn/haybale-graph-editor/.../graph_canvas/node_menu_builder.py`)
renders the "Add Nodes" menu as a button → `ui.menu` → nested `ui.menu` flyouts.
It lives **inside the draggable context-menu `Popup`** (`packages/haywire-core/.../components/popup/popup.py`).
Several non-obvious things must all be true for hover-flyout submenus to work. They
were rediscovered the hard way during the NiceGUI 2.x → 3.x upgrade.

## 1. NiceGUI 3.x drops closed-menu children from the DOM

In 2.x, `Menu` was a plain `ValueElement` — its children were always in the DOM and
Quasar toggled visibility. In **3.x** `Menu._render_markdown()` returns `''` when
`value` is `False`, so a closed submenu's `q-menu` is **not in the DOM at all**.

Consequence: the old hover machinery (`_add_hover_behavior` with `asyncio` close
timers + `submenu.on("mouseenter", cancel_close)`) broke, because it bound events to
elements that didn't exist yet and re-injected/re-anchored the menu on every hover.
**Do not** reintroduce close-timer machinery. Verify with:
`ui.menu()._render_markdown()` → `''` when closed.

## 2. QMenu z-index (6000) is BELOW the Popup card (7001)

The `Popup` Vue card renders at `z-index: 7001` (see `popup.vue` `cardStyle`). Quasar's
`QMenu` defaults to `z-index: 6000`, so an unstyled flyout renders **behind** the popup
("menu appears behind the context menu"). Fix: every menu gets `.style(_MENU_Z)` where
`_MENU_Z = "z-index: 7100"`. The QMenu teleports to `<body>`, so the popup card's
`overflow: auto` does NOT clip it — only the z-order was wrong.

**This bites `ui.select` too, and it looks like a different bug.** A select's
dropdown IS a QMenu, so inside a `Popup` the option list opens behind the card:
the DOM is correct and the options are present, but the user sees an empty,
unusable select. Diagnosing it from server-side `_props`/`_to_dict` will show
everything is fine — the failure is purely stacking. Use
`hui.select_field(in_popup=True)`, which applies the lift via the
`--hw-z-popup-menu` token (design-guide.md §2.9).

Do **not** make the lift unconditional in the wrapper: because the QMenu
teleports to `<body>`, a lifted dropdown escapes its parent's stacking context,
so a panel or node widget *behind* a popup would have its dropdown float above
that popup. Only in-popup selects opt in.

## 3. Direction: fly out to the side, not down

Inside the fixed-size popup, the default `anchor="bottom left"` drops the menu over the
popup body. Use `_FLYOUT_PROPS = 'anchor="top end" self="top start"'` so the top-level
menu and all submenus cascade to the **right** of their anchor.

## 4. QMenu opens on anchor CLICK, not hover

There is no Quasar prop for "open on hover of anchor". Hover-open must be wired
explicitly: `anchor.on("mouseenter", submenu.open)`. (Quasar's own nested-menu docs
example also opens on click.)

## 5. `auto-close` does NOT switch siblings — needs manual sibling/cascade close

`auto-close` dismisses a flyout on item-select or click-away, but NOT when the mouse
moves to a **sibling** category at the same level → flyouts pile up. Solution: every
list of sibling categories shares a `siblings: List[ui.menu]` group; on hover, close all
siblings before opening the hovered one. Closing must **cascade**: each submenu stores
`submenu._child_flyouts`, and `_close_flyout` recurses depth-first, so closing a parent
also closes an open grandchild (e.g. Core→Loops left hanging when you jump to Emit).
Net invariant: exactly one open path from the root at any time.

## Known rough edge (not yet fixed)

No open-delay: a fast diagonal mouse path that crosses a sibling item will switch
flyouts. If this feels twitchy, add a small (~120 ms) open delay — but keep closing on
`auto-close`; do NOT bring back the 2.x close-timer tangle (see #1).
