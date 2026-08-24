---
name: A layout panel defeats the no-popup path — emptiness is a property of the tree
description: The right-click menu's "nothing drew, no popup, on_close still runs" contract survived the Surface model, but its mechanism had to move from the root panel list to a leaf counter, because a hosting panel's own poll() answers the wrong question. The toolbar hit the same blind spot in its render-skip diff and dropped the diff entirely.
type: project
---

# A layout panel defeats the no-popup path — emptiness is a property of the tree

## The contract that has to keep holding

A right-click on the canvas is a gesture, and Haywire's context menus have always had a
"nothing to show" case: right-click a pin with no applicable commands, or right-click into
a selection state nothing polls true for, and no popup should appear at all — not an empty
box, not a box with one greyed-out row nobody can use. When no popup opens,
`on_close`-style cleanup (resuming a paused edge-drag, resetting `active_port`/`active_edge`)
still has to run **immediately**, because the gesture is over even though nothing appeared.
This is old behaviour, predating the Surface model, and every stage of that model was
required to preserve it exactly.

## Why a hosting panel breaks the old mechanism

The old mechanism could ask a cheap question: does the root surface's panel list contain
anything whose `poll()` returns true? If the root surface had a `GraphContextPanel`-style
panel and nothing else, and that panel polled true unconditionally, this worked, because
polling true *was* drawing something.

A **hosting panel breaks that equivalence.** `GraphContextPanel` polls true unconditionally
— it's pure layout, an icon row and a prime area — but polling true only means it drew its
own arrangement, not that anything landed inside it. If `GraphToolBar` and
`GraphContextBody` (the surfaces it hosts) both currently have nothing applicable, the
popup would contain one row and one column, both empty, and the old "root panel list
answers the question" mechanism would report the menu as non-empty and open a visibly blank
box.

**Emptiness is a property of the whole tree, not of the root surface's panel list**
(ADR-0029). Once nesting exists, no static list — not even a recursive walk of `hosts=` —
can answer "will anything actually draw", because `poll()` results depend on live context
state at render time, not on the declared shape of the tree.

## The fix: render first, count leaves, open only if non-empty

`_open_menu()` (`packages/haywire-core/src/haywire/ui/panel/context_menu_base.py`) resolves
this by **rendering the whole tree into a popup that starts invisible**, then deciding
whether to keep it:

1. Build the `Popup` — invisible until explicitly opened.
2. Render the whole panel tree into it: the root surface's panels, and every
   `render_surface()` call any of them make, recursively, under `counting_leaves()`.
3. `counting_leaves()` wraps a fresh `_leaves_drawn` counter
   (`haywire.ui.elements.flyout`, shared with the sibling-group machinery — see
   `.insights/feedback_nicegui_nested_menu_flyouts.md` §6). `render_panel` bumps it once per
   panel that actually drew (`draw()` or `draw_disabled()`) **and declares no `hosts=`** — a
   hosting panel is deliberately excluded, because a layout panel draws its arrangement
   whether or not anything lands in it; only a *leaf* is "content" for this purpose.
4. After the render, `leaves() > 0` decides: open the popup if anything counted, otherwise
   `popup.delete()` (reclaiming the whole rendered subtree) and run the close cleanup
   immediately — exactly the same path as "nothing polled true" always took.

The render-then-discard approach costs a wasted render on the empty-menu path, but it is the
only way to get a correct answer once "does this surface have content" can only be resolved
by actually resolving the whole nested tree's `poll()` results.

## Why the toolbar used to have the same blind spot (fixed, but worth knowing why)

`SelectionToolbarProvider` (the floating toolbar) originally used a different mechanism: it
diffed the previous render's panel set against the current one (`visible != self._rendered_panels`)
and skipped re-rendering when the set was unchanged, to avoid redrawing on every
`selectionBounds` frame. That diff compared the **panels registered directly on
`SelectionToolbar`** — reasonable when a toolbar's own panel list *was* its content, before
nesting existed.

Once `SelectionToolbar`'s "…" became a hosting panel (rendering an overflow surface via
`render_surface`), that diff went blind exactly the way the popup-emptiness question did: a
`poll()` flip *inside* the flyout, or a library installing a new command into the overflow
surface, changes nothing about the **root** surface's panel set, so the diff would report
"unchanged" and skip the redraw — showing stale overflow content until something unrelated
forced a full rebuild. `barn/haybale-graph-editor/haybale_graph_editor/editors/graph_canvas/handlers/selection_toolbar.py`'s
`show_at()` now renders unconditionally on every call instead of diffing, with a comment
explaining exactly this — it stopped being an optimization worth keeping once nesting made
"unchanged" impossible to determine cheaply. The trade is one extra render per gesture
*end* (not per frame — `selectionBounds` is edge-triggered, hidden during drag/pan and shown
on release, plus a 120 ms trailing debounce for wheel-zoom), which is cheap enough that the
diff was worth deleting rather than teaching it to walk `hosts=`.

## The symptom that sends you looking in the wrong place

If either of these breaks, the visible symptom is arbitrarily far from the cause: **an
edge-drag that never resumes.** `on_close` cleanup is what un-pauses a paused connection
drag after a right-click gesture completes. If a hosting panel's popup-emptiness accounting
is wrong — say, a future edit makes a hosting panel count itself as a leaf, or a leaf
undercounts because it's nested inside another `render_surface` call that doesn't propagate
the counter — the popup can open when it shouldn't (or vice versa), and either way
`on_close` may not fire on the path you expect. The canvas will look frozen mid-drag, and
nothing about that symptom points at panel-tree leaf-counting. If you hit this, check
`_open_menu()`'s `leaves() > 0` decision and whether every `render_surface` call in the path
is running inside the same `counting_leaves()` scope before suspecting the drag/gesture code
itself.
