---
name: NiceGUI headless tab_panels for DOM-preserving slot switches
description: Use ui.tab_panels without a bound ui.tabs as a keep-alive container when you want to switch between sibling editors without redrawing
type: feedback
originSessionId: bc503609-edad-46a1-a73c-f92ae17e541e
---
`ui.tab_panels(value=..., keep_alive=True)` works fine without a bound `ui.tabs` — the `tabs` arg is optional. Drive it from external chrome (activity bars, custom tab bars) by calling `set_value(key)` directly. Each child `ui.tab_panel(name)` lives in the DOM simultaneously; Quasar toggles visibility via CSS.

**Why:** The shell's four slots were doing `container.clear() + editor.draw()` on every switch, which meant a full redraw of heavy editors (GraphEditor etc.) every time the user flipped between them. Switching to a headless `ui.tab_panels` made the editors feel noticeably snappier — user-confirmed 2026-04-14. The DOM cost is bounded (one `ui.tab_panel` per binding) and first-draw can still be lazy (draw on first `switch_to`, cache after).

**How to apply:** Whenever you have a container that hosts N alternative editors/views driven by external navigation, reach for this pattern instead of clear-and-redraw. Keep editor `draw()` lazy on first activation if any editor measures DOM size on draw (canvas, minimap) — drawing into a hidden `ui.tab_panel` reads zero size. Reference implementation: [packages/haywire-core/src/haywire/ui/app/slot.py](../../../../../../Volumes/Ddrive/06_open_tracking_tool/haywire/haywire-repo/packages/haywire-core/src/haywire/ui/app/slot.py) — `_create_panel`, `_ensure_drawn`, `_redraw`, and the `switch_to` → `set_value` path.
