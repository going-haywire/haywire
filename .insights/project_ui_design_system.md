---
name: Haywire UI design system (hui module)
description: Design rules and hui API for building editors/panels — colours, spacing, components, anti-patterns; updated 2026-04-06
type: project
---

## Status: Active as of 2026-04-06

Full spec: `docs/documentation/design/haywire-ui-design-guide.md`

**`hui`** = `haywire.ui.elements` — thin wrapper library encoding design rules as Python functions.
Import as: `from haywire.ui import elements as hui`

**Package structure:**
- `haywire/ui/elements/__init__.py` — re-exports via `*`, exposes `icon = AppIcon`
- `haywire/ui/elements/elements.py` — all hui component functions
- `haywire/ui/elements/icons.py` — `AppIcon` class (semantic icon registry)

**Icon usage:** `hui.icon.add`, `hui.icon.canvas`, `hui.icon.expand_full`, etc.
All icons are class-level string constants on `AppIcon`. Use `hui.icon.<name>` everywhere —
never raw Material icon strings.

**CSS injection:** hui CSS (`.hw-text-*` utilities, hover transitions) lives in `shell.py`
`_static_css`, NOT in a per-function `_ensure_css()`. The old `_ensure_css` + `_CSS_INJECTED`
global flag were removed (bug: flag was shared across sessions, so CSS was only injected once).

**Rule:** Always prefer `hui.*` over raw NiceGUI/Quasar calls for any pattern defined in the guide.

---

## Core principles

1. **IDE-density** — compact, minimal chrome. If a spacing class can be removed without losing clarity, it was too much.
2. **Theme-driven** — no fixed colour values anywhere. All colours via `--hw-*` CSS custom properties. Hard rule — violations break light/user themes.
3. **Quiet by default, loud on interaction** — resting UI is muted; colour appears on hover/focus/select/error.
4. **Panels own their scroll** — shell is `overflow: hidden`. Each editor/panel manages its own `ui.scroll_area()`.
5. **One pattern, one implementation** — repeated visual patterns must go through `hui`, not copy-pasted classes.

---

## Background elevation (colour-stepped, no box shadows)

```
Layer 0   --hw-bg-page        Ground plane (editor backgrounds, area containers)
Layer 1   --hw-bg-surface     Topbar, info bars, panel header backgrounds
Layer 2   --hw-bg-elevated    Dropdowns, tooltips, popovers, dialog cards
Layer 3   --hw-bg-overlay     Modal backdrops
```

`box-shadow` reserved exclusively for canvas nodes (`--hw-node-shadow`). Panel chrome never uses shadow.
Dialog/popup shadow: `var(--hw-popup-shadow)` (distinct from node shadow).

---

## Status / semantic colour tokens

| Token | Use |
|---|---|
| `--hw-danger` | Error, destructive, failure — text/icon colour |
| `--hw-warning` | Caution — text/icon colour |
| `--hw-success` | Success state indicators, result labels |
| `--hw-info` | Informational |
| `--hw-positive` | Confirm/OK button emphasis (interactive affordance, not status) |

**Rule:** `--hw-positive` is for interactive confirm buttons only. Use `.style("color: var(--hw-positive)")` — never `color=positive` Quasar prop (not theme-mapped, uses hardcoded green).

---

## Truncation rules (§3.5)

Any text that can overflow must have `.truncate`. Parent flex container must have `.min-w-0`.

**Current state of hui components (as of 2026-04-06):**
- `hui.label` — has `truncate` ✓
- `hui.section_label` — has `truncate` ✓
- `hui.panel_header` title — has `truncate flex-1` ✓
- `hui.info_row` — value has `truncate flex-1`, row has `min-w-0` ✓
- `hui.expansion_section` — has `header-class="truncate"` ✓
- `hui.category_group` — has `truncate` in header-class ✓
- `hui.button` — uses `no-wrap` Quasar prop (correct for QBtn inner span) ✓

**Rule for QBtn:** Use `no-wrap` prop, NOT `.truncate` class — `truncate` can't reach the inner `<span>` that Quasar renders for the label.

---

## Key hui components (as of 2026-04-06)

| Function | Purpose |
|---|---|
| `hui.panel_header(title, icon=None)` | Slim bar at top of panel — action buttons inside |
| `hui.info_bar(label, badge=None, suffix=None)` | 28px contextual metadata bar |
| `hui.empty_state(message, icon, hint=None)` | Centered placeholder for empty panels |
| `hui.list_item(...)` | Themed row with hover/active states |
| `hui.label(text)` | Body-tier text label (`text-sm hw-text-body truncate`) |
| `hui.section_label(text)` | Uppercase dim tracking label for group separators |
| `hui.icon_action(icon, tooltip, on_click)` | Icon-only inline action button |
| `hui.button(label, icon=None, tooltip, on_click, disabled)` | Full-width flat labelled button (`w-full align=left no-wrap`) |
| `hui.toolbar_button(icon, is_active, tooltip, on_click)` | Activity/context bar button (40×40px) |
| `hui.scope_button(icon, is_active, available, tooltip, on_click)` | Properties scope toolbar button (36×36px) |
| `hui.expansion_section(...)` | Collapsible panel section with state persistence |
| `hui.category_group(label, default_open)` | Collapsible category for settings fields |
| `hui.input_field(...)` / `hui.number_field(...)` / `hui.select_field(...)` | Themed form fields |
| `hui.tabs(...)` | Themed tab bar |
| `hui.separator()` | Theme-aware divider |
| `hui.section_divider(text=None)` | Labelled horizontal rule |
| `hui.error_label(text)` / `hui.warning_label(text)` / `hui.success_label(text)` | Semantic status labels |
| `hui.info_row(label, value, copy_value=None)` | Key-value metadata row |
| `hui.code_snippet(code, label=None)` | Read-only code snippet (note: function name is `code_snippet`, not `code_block`) |
| `hui.tag(text, color)` | Quasar badge tag |
| `hui.dialog_card(width=None)` | Themed modal card — use instead of `ui.card()` inside `ui.dialog()` |
| `hui.dialog_actions(on_confirm, on_cancel, confirm_label, cancel_label)` | Standardised OK/Cancel row |

---

## PanelLayout — dual-mode layout helper

`PanelLayout` is passed to `BasePanel.draw(context, layout)`. Two modes:

**Simple mode** — call helpers for the 90% case:
```python
def draw(self, context, layout):
    layout.section_label("FILES")
    layout.separator()
    layout.button("Delete Node", icon="delete", on_click=self._delete)
    layout.empty_state("Nothing selected")
```

**Power mode** — use as context manager for full `hui` access:
```python
def draw(self, context, layout):
    with layout:
        hui.section_label("ADVANCED")
        with hui.expansion_section("Node", context=context):
            hui.info_row("Key", node.registry_key)
```

**Available helpers on `PanelLayout`:** `panel_header`, `section_label`, `separator`,
`section_divider`, `empty_state`, `error_label`, `warning_label`, `icon_action`,
`expansion_section`, `label`, `button` — all delegate to `hui`.

**Location:** `packages/haywire-core/src/haywire/ui/panel/base.py`

---

## Dialog pattern (§8.23)

```python
with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
    # content — hui.dialog_card carries hw-panel class, so colour cascade works
    hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
```

**`hui.dialog_card`** applies: `--hw-bg-elevated` bg, `--hw-border-strong` border, 8px radius,
`--hw-popup-shadow`, and crucially the **`hw-panel` class** so Quasar field colours and
`.hw-text-*` utilities work inside the dialog.

**Rule:** Never use raw `ui.card()` inside `ui.dialog()`.

---

## `hw-panel` class — what it does

Defined in `app/shell.py` `_static_css`. Sets `color: var(--hw-text-body)` on the element
and all descendants. Also:
- Overrides Quasar outlined field borders to use `--hw-border` / `--hw-border-strong`
- Sets `q-field__control` background to `--hw-bg-input`
- Dims icons to `--hw-text-dim`

Apply `hw-panel` to any container that needs theme-correct Quasar field rendering.

---

## Anti-patterns (hard rules)

- Never hardcode hex/rgb colour values — use `--hw-*` CSS vars
- Never use `box-shadow` on panel chrome (only `--hw-node-shadow` on canvas nodes)
- Never rely on a parent scrolling for you — always add `ui.scroll_area()` inside your editor
- Never copy-paste Quasar class strings across editors — wrap in `hui`
- Never use `color=positive` Quasar prop — use `.style("color: var(--hw-positive)")`
- Never use `color=primary` on buttons — use `--hw-accent`
- Never use `rgba(0,0,0,0.5)` as modal backdrop — use `var(--hw-bg-overlay)`
- Never use `ui.card()` inside `ui.dialog()` — use `hui.dialog_card()`
- Never use raw Material icon strings — use `hui.icon.<name>`
- Never use `truncate` on a `ui.button` label — use `no-wrap` Quasar prop instead
- Never use in-method `from haywire.ui import elements as hui` — import at module level

---

## How to apply

When building a new editor or panel:
1. Check the design guide (`docs/documentation/design/haywire-ui-design-guide.md`) for the pattern.
2. Use the `hui.*` function if one exists.
3. If no `hui` function exists yet, implement it in `haywire/ui/elements/elements.py` first, then use it.
4. Document the new function in the design guide (§8.x).
