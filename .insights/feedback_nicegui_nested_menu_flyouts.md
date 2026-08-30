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

## 2. QMenu z-index (6000) vs the Popup card — RESOLVED, read this before the rest

**This section described a problem that no longer exists. Kept because the
reasoning below it still governs the *dropdown* case, and because the way it
was wrong is instructive.**

The `Popup` card used to render at `z-index: 7001`, above Quasar's `QMenu`
default of 6000, so every menu inside a popup rendered *behind* it and needed a
hand-stamped lift (`_MENU_Z = 7100`, then 7110 for a menu inside that, and so
on). That 7001 was never a design: it was a tactical bump in `d48f1161` to
clear **one** `ui.dialog()` — the marketplace library Edit dialog — that hid a
Popup opened from it. That dialog became a `Popup` itself soon after, and the
bump's justification silently expired while every layer built on top of it
stayed.

**The Popup now sits at 5000/5001, BELOW Quasar's interaction tier.** A menu,
select or colour picker inside a popup clears the card on its own. There is no
`in_popup=` flag, no `POPUP_MENU_Z`, and nothing to opt into — see
design-guide.md §2.9 for the ladder, which derives every rung from the one
external constant (`QMenu`/`QDialog` = 6000).

**The trade:** a `ui.dialog()` opened *from* a Popup is fine and supported; a
Popup opened from an *already-open* `ui.dialog()` renders behind it and is
invisible. Close the dialog first.

### What still needs a lift: a dropdown's body

A `hui.dropdown` panel **is** a QMenu, sitting one rung above the interaction
tier (`FLYOUT_Z` = `--hw-z-menu-over-menu`). So anything inside it that opens
its own portal — a select's option list, a colour picker, a row's context menu
— lands on the bare tier *underneath the panel that spawned it*.
`_lift_nested_popups` exists for exactly this and only this.

Do **not** make that lift unconditional in the wrapper: because the QMenu
teleports to `<body>`, a lifted dropdown escapes its parent's stacking context,
so a panel or node widget behind an overlay would float above it. Only a
dropdown's own body is lifted, by the dropdown itself.

**The trap that bit twice:** `ui.context_menu()` renders a `q-menu` but
`ContextMenu` is a **sibling** of `Menu` (both subclass `Element` directly), so
`isinstance(el, ui.menu)` silently misses every row menu. That is why a
settings row's right-click menu opened behind the dropdown hosting it. The lift
now matches both types; a test asserts the sibling relationship so a future
NiceGUI change that makes them related is noticed rather than assumed.

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

## 6. Sibling-group ownership broke under the Surface model — and `render_surface` is the fix

This module's whole design assumes one thing implicitly: whoever draws a box (a `Popup`,
a flyout body) owns the sibling group for what gets drawn inside it, and every leaf drawn
in that box either belongs to that group directly or is itself a nested box that owns its
own group one level down. `NodeMenuBuilder`, the module's original client, satisfies this
by construction — it recurses through its own tree and threads `siblings` by hand at every
level, so the box-owns-group invariant is trivially true.

**The Surface model breaks that precondition.** A hosting panel's `render_surface(S, ctx)`
call does not recurse through anything the *caller* wrote — it hands off to
`PanelRegistry.get_panels(S)` and renders whatever panels are registered there, from
libraries the hosting panel has never heard of and cannot enumerate. Two panels on two
different surfaces, nested by two different `hosts=` edges, can both render `SubmenuRow`s
into what is visually the *same* popup — `GraphContextPanel` renders `GraphToolBar` and
`GraphContextBody` into one popup's content, for instance — and those rows must share one
sibling group (opening one closes the other) even though neither panel's code ever
constructs or passes a `siblings` list to the other. Nothing in a panel's own `draw()` can
thread a list to a panel it doesn't know exists.

**The fix: the box owns the group, not the code that draws into it.** `open_flyout_group()`
is the primitive a *host* — never a panel — pushes once, as a `ContextVar`
(`_flyout_siblings`), around a box's content: `_open_menu()` pushes it once around a
`Popup`'s content before rendering the (possibly deeply nested) panel tree, and
`render_surface` deliberately does **not** push a second one — nesting stays inside the
same ambient group unless a `SubmenuRow`/`FlyoutIcon`'s own `__enter__` opens a *new* box
(a flyout body is a real visual box; a `render_surface` call is not). Every
`SubmenuRow`/`FlyoutIcon` constructed anywhere in that render — regardless of which panel,
which surface, which nesting depth — reads the *ambient* group via `_flyout_siblings.get()`
and registers itself into it, with no caller ever passing a list explicitly. This is what
makes two unrelated panels' rows close each other correctly: they were never "siblings" by
any code path that ran, only by both having been drawn inside the same ambient box.

**Corollary — retroactive greying needed a second ContextVar, `_in_flyout_body`.** A
`SubmenuRow`/`FlyoutIcon` counts as "content drew" at its *enclosing* level so a container
of only nested rows doesn't grey itself just because none of its own leaves fired — but
only when that enclosing level is *itself* a flyout body. A `SubmenuRow`/`FlyoutIcon`
constructed directly in a host's top-level popup scope (e.g. a hosting panel like
`GraphMorePanel` drawing `hui.flyout(...)` straight into its own `draw()`, not nested
inside another row) is, at that scope, architecturally a container — the same category
`render_panel` already excludes from the popup-emptiness count for hosting panels
(`class_identity.hosts != ()`). Without gating on `_in_flyout_body`, that bump would make a
popup whose only content is one currently-empty flyout icon look non-empty, opening a popup
around a single retroactively-greyed, useless control instead of not opening at all. Two
simpler fixes were tried and rejected before this one: decrementing the counter in
`__exit__` when a body turns out empty (breaks the disabled-nested-child case, which never
calls `__enter__`/`__exit__` at all — there is nothing to decrement from); and never
bumping the enclosing counter at all (breaks the legitimate nested-container case, where a
row containing only further rows must still read as "drew something"). See
`packages/haywire-core/src/haywire/ui/elements/flyout.py` (`_in_flyout_body`'s docstring)
for the traced-through reasoning, and `.superpowers/sdd/task-C-report.md`'s last section for
the full incident trace.
