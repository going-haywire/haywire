---
name: popup-overlay-should-stop-capturing
description: Handoff — a backdrop_click_close Popup covers the viewport at pointer-events auto, so outside clicks are intercepted rather than passed through; the context-menu symptom is patched, the underlying design is not
metadata:
  type: project
  status: open
---

# The positioned Popup overlay captures clicks it should let through

Identified 2026-08-30 while making the node context menu swap on a second
right-click (ADR 0032 follow-up). The symptom there is fixed; **this is the
option we did not take**, recorded because the next person to meet the overlay
will meet it the same way.

## The shape of it

`HwPopup` renders a full-viewport `inset: 0` overlay above everything. For a
popup that was given an explicit position — which is every context menu — the
overlay's hit-testing is decided by one line:

```js
// packages/haywire-core/src/haywire/ui/components/popup/popup.vue, overlayStyle()
pointerEvents: this.backdropClickClose ? 'auto' : 'none',
```

`BaseContextMenuProvider._build_popup` passes `backdrop_click_close=True`, so
every context menu in the app puts a transparent, click-eating sheet over the
entire window. Dismiss-on-outside-click is implemented **by that sheet**
swallowing the click (`@click.self="onOverlayClick"`).

That conflates two things which are not the same: *"clicking outside dismisses
me"* and *"I consume the click that dismissed me"*.

## What it costs

Every gesture aimed past an open menu has to be re-implemented on the overlay,
one event type at a time, or it is silently wrong:

- **`contextmenu`** — was missing entirely. A right-click while a menu was open
  hit the overlay, nothing called `preventDefault()`, and the **browser's own**
  context menu appeared over ours. Now handled (`onOverlayContextMenu`), which
  closes and re-dispatches at `document.elementFromPoint`.
- **`mousedown` / drag** — starting a node drag or a box-selection through an
  open menu does not work; the gesture is eaten and the menu just closes.
- **`wheel`** — zooming the canvas with a menu open. Not verified either way.
- Anything added later. Each is a fresh discovery, and each fails silently.

The re-dispatch we shipped is the tell: it exists only to undo the interception.

## The change not made

Give the positioned branch `pointerEvents: 'none'` unconditionally, and move
dismissal to a **capture-phase document listener** the popup installs while
open, closing when the event's target is outside `.hw-popup-card`.

Then the overlay is a paint layer, not an input layer. Right-clicks reach nodes
on their own; `onOverlayContextMenu` and its `elementFromPoint` re-dispatch
delete; drag-through and wheel-through work without anyone deciding they should.

## Why it was deferred

`backdrop_click_close` is not context-menu-specific. It is passed by ~10
modals (`confirm_modal`, `diff_modal`, `save_as_modal`, …) and by three menu
providers — the graph canvas, the **account menu**, and the **file-browser
menu**. The modals take the *other* branch of `overlayStyle` (centred, real
backdrop, always `pointer-events: auto`), so they are unaffected in principle —
but "in principle" is exactly what wants verifying before the flag's meaning
changes under all of them.

Doing it as a rider on a context-menu fix would have put that verification on
the wrong change. It deserves its own branch and its own pass over every
`backdrop_click_close=True` call site.

## Where to start

- `packages/haywire-core/src/haywire/ui/components/popup/popup.vue` —
  `overlayStyle()`, `onOverlayClick`, `onOverlayContextMenu`
- `packages/haywire-core/src/haywire/ui/panel/context_menu_base.py` —
  `_build_popup`, `close_open_menu`
- `tests/ui/graph_canvas/test_session_context_menu_provider.py` —
  `TestMenuSupersedesTheOpenOne` pins the Python half of the swap; the browser
  half has no coverage (it is Vue, and the harness would need Playwright)

**Check on the way in:** whether `onOverlayContextMenu`'s re-dispatch can be
deleted outright once the overlay stops capturing. If it can, that is the
signal the change landed correctly.

## One thing that is easy to get wrong

Do **not** move the close into `BaseContextMenuProvider._open_menu`. Intent
handlers seed `EditState` and `_OpenMenuContext` *before* opening a menu, and
the previous popup's `on_close` resets exactly those — so closing from inside
`_open_menu` makes the old gesture's cleanup wipe the new gesture's state. The
close belongs at the dispatcher (`ContextMenuHandlers.process_context_menu`),
which is the last point where "the old menu" and "the new gesture" are still
cleanly separable.
