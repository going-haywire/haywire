---
name: A flyout that stretches to the viewport edge is an inline-level leaf, not a menu width bug
description: QBtn is display:inline-flex, so w-full buttons stacked in a QMenu share one line box and the menu's max-content becomes their SUM — measured 653px for five short labels. Fix the leaf (display:flex), never the menu (width/max-width there only re-measures or truncates the same wrong number).
type: feedback
---

# A flyout that stretches to the viewport edge is an inline-level leaf

## Symptom

The node/selection toolbar's `⋯` flyout (`hui.flyout` → `FlyoutMenu`) opens as a
band running to the browser's right border instead of hugging its icons and
labels. Near a viewport edge it also appears to *resize while the mouse moves
over items*, always growing from a pinned left edge.

## Why

A `QMenu` is shrink-to-fit (`display: inline-block`, `position: fixed`, only
`left` is ever set — Quasar's position engine sets `right: unset`), so its width
is `min(available, max-content)`. Available, near an edge, is "the rest of the
viewport".

The leaves are the problem. Quasar's `.q-btn` is `display: inline-flex` — an
**inline-level** box. Five stacked `hui.button`s are therefore five inline boxes
on **one line box**, and `w-full` cannot break them apart: during intrinsic
sizing percentage widths resolve to `auto` (same rule as
[feedback_css_containment_node_floor.md](feedback_css_containment_node_floor.md)),
so `width: 100%` contributes nothing to max-content. The menu's max-content is
the *sum* of every button's label — measured at 653px for five short "… Node"
labels, i.e. always ≥ available, so the menu takes the whole remaining width.

That also explains the "resize on hover": at that size the width is the
*available* width, and any Quasar reposition (`updatePosition` on scroll/resize)
re-clamps it from a new `left`, which is stuck because `right` is never set.

## The fix goes on the leaf

`hui.button` carries `flex` (i.e. `display: flex`) alongside `w-full`. Quasar's
own `.q-btn { flex-direction: column; align-items: stretch }` still applies, so
the button looks identical — only its line-level participation changes. The menu
then measures the widest single row (158px in the same repro).

Measured with Playwright against a repro of the real primitives:

| variant | menu width |
|---|---|
| baseline | 653px (= available) |
| `.q-menu { width: max-content }` | 653px — max-content *is* the sum |
| `.q-menu { width: fit-content }` | 653px |
| leaves `display: flex` | 158px |

## What not to do

Do **not** put `width` / `max-width` on the flyout (`FLYOUT_Z`). `max-content`
re-measures the same wrong number, and a `max-width` cap truncates real labels
(`.q-menu` is `overflow-x: hidden`) while leaving every uncapped case broken. The
same trap applies to any content-sized popup, not just flyouts: an inline-level
leaf with `w-full` inside a shrink-to-fit box is always a latent full-width band.
