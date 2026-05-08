---
name: NiceGUI/Quasar dialog theming — colour inheritance and hw-panel
description: How to correctly theme modal dialogs in NiceGUI/Quasar so text, underlines, and field chrome all use hw-* tokens
type: feedback
---

The correct way to theme a modal dialog in Haywire is to use `hui.dialog_card()`, which
applies the `hw-panel` class to the card. This is non-obvious — raw approaches fail.

**Why:** Quasar's `ui.card()` applies its own colour reset, and `color:` set via `.style()`
on the card is overridden by Quasar internals. Quasar input underlines use `currentColor`
from `.q-field__control::before/::after`, not from inherited `color` on the outer element.

**What works:** The `hw-panel` class, defined in `app/shell.py` `_static_css`, sets
`color: var(--hw-text-body)` on the element and **all descendants** via a `*, .hw-panel *`
selector. This reaches Quasar's internal elements (including underlines) that inline `.style()`
does not. It also applies all field background overrides (`--hw-bg-input`, border colours).

**What does NOT work:**
- `.style("color: var(--hw-text-body)")` on the card — Quasar resets it on children
- `input-style="color: var(--hw-text-body);"` prop — reaches the `<textarea>` text but not underline
- `--q-color-primary` CSS var via `.style()` — doesn't reach `::before`/`::after` pseudo-elements
- `hw-text-body` CSS class — only works inside an `.hw-panel` ancestor

**The pattern:**
```python
with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
    ui.textarea(...).classes("w-full text-xs").props("dense autogrow")
    hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
```

`hui.dialog_card` applies `hw-panel` + `--hw-bg-elevated` bg + `--hw-border-strong` border
+ 8px radius + `--hw-popup-shadow`. All text, field chrome, and underlines inherit correctly.

**Why:** Investigated 2026-04-05 when `_open_modal` in `render_utils.py` had black text and
black underlines on a dark background despite inline style attempts. Root cause was Quasar's
colour reset on `q-card` and `currentColor`-based underline rendering not reached by outer styles.

**How to apply:** Always use `hui.dialog_card()` for any modal dialog. Never use raw `ui.card()`
inside `ui.dialog()`.
