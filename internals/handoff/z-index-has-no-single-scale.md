---
name: z-index-has-no-single-scale
description: Handoff — stacking is ad-hoc literals across 10 files, the design guide's z token scale is documented but never defined in CSS, and a settings row's context menu opens behind the dropdown that spawned it
metadata:
  type: project
  status: open
---

# Stacking order is a pile of literals, not a scale

Raised 2026-08-30 during the ADR-0032 menu work, deferred until that feature
lands. There is a reproducible bug at the end of this, but the bug is a symptom:
**nothing in the app owns stacking order**, so every new layer is a fresh
negotiation with whatever it happens to overlap.

## The reproducible bug

Toolbar → **Appearance** → the appearance panel → **right-click a settings
row**. The row's context menu opens *behind* the dropdown it was spawned from,
so it is invisible.

The chain, all verified:

| Layer | z | Where |
| --- | --- | --- |
| Popup overlay | 7000 | `popup.vue` `overlayStyle` |
| Popup card | 7001 | `popup.vue` `cardStyle` |
| Flyout / dropdown QMenu | 7100 | `flyout.py` `FLYOUT_Z` |
| Popup spawned *inside* a dropdown | 7110 | `flyout.py` `_NESTED_POPUP_Z` |
| **A settings row's `ui.context_menu()`** | **6000** | Quasar default — nothing lifts it |

`_lift_nested_popups` already solves this shape for the controls a dropdown body
usually holds — selects, colour pickers — by stamping the lift while they are
built (they teleport to `<body>`, so no descendant CSS rule can reach them).
A bare `ui.context_menu()` is simply not in the set it lifts, and the settings
rows use exactly that (`render_utils.py:421` and `:618`, both
`ui.context_menu().props('data-row-menu="true"')`).

So the narrow fix is one more case in `_lift_nested_popups`. **Resist it.**
That is the fourth such patch, and the next layer will need a fifth.

## The actual problem

**The documented scale is not the real one.** `docs/reference/design-guide.md`
publishes a clean four-token ladder:

| token | value |
| --- | --- |
| `--hw-z-panel` | 10 |
| `--hw-z-dropdown` | 100 |
| `--hw-z-tooltip` | 200 |
| `--hw-z-modal` | 300 |

**None of those four tokens is defined anywhere in CSS.** The only z tokens that
exist at runtime are declared in one line of `shell.py:99`:

```py
" :root { --hw-z-popup: 7001; --hw-z-popup-menu: 7100; }"
```

Everything else is a literal. 28 `z-index` declarations across 10 files, and the
canvas alone spans `1`, `2`, `9`, `10`, `100`, `999`, `1000`, `1001`, `10003` —
including two set from JavaScript at drag time.

The 7000-series exists solely to clear **Quasar's 6000**, which is itself an
undocumented external constant the app is negotiating with by guesswork.

## What the fix should look like

1. **One ladder, defined once, in CSS custom properties.** Either reconcile the
   design guide's four tokens with reality or replace them — but the guide and
   the code must name the same numbers. Right now a reader who trusts the guide
   writes `z-index: var(--hw-z-modal)` and gets `300`, i.e. underneath
   everything.
2. **Name the layers that actually exist**: canvas content, dragged element,
   node overlay, popup overlay, popup card, menu from a popup, menu from a menu.
   The last two are the ones that keep biting.
3. **Decide the Quasar relationship explicitly.** Every 7xxx number is "6000 plus
   enough". Write down that the app sits above Quasar's dialog layer and derive
   the ladder from one constant, so the next Quasar upgrade is one edit.
4. **Then** make `ui.context_menu()` pick up its layer from the ladder instead of
   needing a per-site lift, which retires `_lift_nested_popups` rather than
   extending it.

## Where to start

- `packages/haywire-core/src/haywire/ui/app/shell.py:99` — the only real token
  declarations
- `packages/haywire-core/src/haywire/ui/elements/flyout.py` — `FLYOUT_Z`,
  `_NESTED_POPUP_Z`, `_lift_nested_popups`
- `packages/haywire-core/src/haywire/ui/elements/elements.py:37` —
  `POPUP_MENU_Z`
- `packages/haywire-core/src/haywire/ui/components/popup/popup.vue` —
  `overlayStyle` / `cardStyle`
- `packages/haywire-core/src/haywire/ui/panel/render_utils.py:421,618` — the
  unlifted row menus that surfaced this
- `docs/reference/design-guide.md:234-237` — the scale that is documented but
  not defined; whatever lands here, that table must become true

## Related

`.insights/feedback_nicegui_nested_menu_flyouts.md` §2 records the QMenu-6000 vs
popup-7001 collision and the deliberate decision **not** to make the lift
unconditional in the wrapper. That reasoning is sound for a per-site lift and is
exactly what a real ladder would make unnecessary — read it before changing the
wrapper, not after.
