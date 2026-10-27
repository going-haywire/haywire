---
status: draft
doc_template: design-guide
scope: Visual / UX rules, do/don't, design tokens, component patterns, layout primitives, accessibility, anti-patterns
see-also:
  - glossary.md
  - ../components/themes/theme-canon.md
  - ../components/panels/panel-canon.md
  - ../components/skins/skin-canon.md
---

# Haywire Design Guide

A prescriptive design reference for developers building editors, panels, and components in the Haywire workbench. This document defines the rules — not just what exists today, but what every new (and eventually every existing) piece of UI should follow.

Where the `hui` module is referenced, it means `haywire.ui.elements` — the
thin wrapper library that encodes these rules into reusable Python functions.
Prefer `hui.*` over raw NiceGUI/Quasar calls for any pattern that appears here.

this guide is a living document. If you encounter a design aspect that is not covered, report back to the user and suggest an addition. If the pattern you need doesn't exist in `hui`, add it — but follow the design rules and document the new function here in the guide.

---

## 1. Design Principles

### 1.1 IDE-density, not dashboard-density

Haywire is a professional tool. Every pixel is working space. Panels are compact,
chrome is minimal, and whitespace is used structurally — never decoratively.
A good test: if you can remove a `gap-*` or `p-*` class and the layout still
reads clearly, it was too much.

### 1.2 Theme-driven, never hardcoded

No fixed colour values anywhere in structural UI. Every colour must reference a
`--hw-*` CSS custom property or its `hui` equivalent. This is not a guideline —
it is a hard rule. Violations break light themes and user-authored themes.

The only exception: Quasar `color=` props that require named strings for semantic
status badges (e.g. `color=green` for an "enabled" indicator). Even here, prefer
the token-mapped approach when possible.

### 1.3 Quiet by default, loud on interaction

Resting UI is muted and recessive. Colour and contrast appear in response to user
action — hover, focus, selection, error. An unfocused panel should feel like a
grey instrument panel; interaction lights it up.

### 1.4 Panels own their scroll

The shell is `overflow: hidden` at every level. Each editor or panel is
responsible for its own scrolling via `ui.scroll_area()`. Never assume a parent
will scroll for you.

### 1.5 One pattern, one implementation

If a visual pattern appears in more than one editor, it must be implemented via
`hui`. Copy-pasting class strings between editors is a design debt that compounds.

---

## 2. Colour System

### 2.1 Background Elevation

Haywire uses colour-stepped elevation rather than box shadows. Each layer in the
visual stack uses a progressively lighter (or more opaque) background.

```
Layer 0   --hw-bg-page        Ground plane. Deepest.
Layer 1   --hw-bg-surface     Raised panels, topbar, cards.
Layer 2   --hw-bg-elevated    Dropdowns, tooltips, popovers.
Layer 3   --hw-bg-overlay     Modal scrims (rgba overlay).
```

**Rule:** `box-shadow` is reserved exclusively for canvas nodes
(`--hw-node-shadow`). Panel chrome never uses shadow.

**Rule:** Each container should be exactly one elevation step above its parent.
Do not skip levels (e.g. page → elevated without a surface in between).

### 2.2 Background Tokens

| Token              | Layer | Use for                                                              |
| ------------------ | ----- | -------------------------------------------------------------------- |
| `--hw-bg-page`     | 0     | Area containers, editor backgrounds                                  |
| `--hw-bg-surface`  | 1     | Topbar, info bars, panel header backgrounds                          |
| `--hw-bg-sidebar`  | 0–1   | Activity bar, context bar                                            |
| `--hw-bg-elevated` | 2     | Dropdown menus, tooltips, toolbar hover                              |
| `--hw-bg-overlay`  | 3     | Modal backdrops                                                      |
| `--hw-bg-input`    | —     | Input field backgrounds (special-purpose)                            |
| `--hw-bg-hover`    | —     | Row hover background. Theme-aware; equals `--hw-bg-surface` at rest. |
| `--hw-bg-active`   | —     | Selected/active row. Distinct from hover; not as heavy as a surface. |

### 2.3 Text Tokens

Four tiers. Every piece of text in the application must use one of these.

| Token                 | Tier | Use for                                          |
| --------------------- | ---- | ------------------------------------------------ |
| `--hw-text-body`      | 1    | Primary content. Headings, labels, body copy.    |
| `--hw-text-muted`     | 2    | Supporting text. Descriptions, tab labels.       |
| `--hw-text-dim`       | 3    | Decorative text. Placeholders, captions, icons.  |
| `--hw-text-expansion` | —    | Expansion panel header labels (special-purpose). |
| `--hw-text-on-accent` | —    | Text rendered on accent-coloured backgrounds.    |

**Utility classes:** `.hw-text-body`, `.hw-text-muted`, `.hw-text-dim` are
globally available inside `.hw-panel` containers.

**Rule:** Never use Tailwind's `text-gray-*` classes for UI text. They are
theme-unaware and will break on non-dark themes.

### 2.4 Border Tokens

| Token                | Use for                                          |
| -------------------- | ------------------------------------------------ |
| `--hw-border`        | Subtle structural dividers. Felt, not seen.      |
| `--hw-border-strong` | Visible separators. Section breaks, panel edges. |
| `--hw-separator`     | Divider lines (`hui.separator()`, menu bands). Optional; falls back to `--hw-border`. |

**Rule:** Every `border-b`, `border-r`, `border-l`, `border-t` in the shell
and editor UI must use `var(--hw-border)` via inline style or an appropriate
`hui` wrapper. Never use Tailwind border-colour utilities.

### 2.5 Accent & Interactive Tokens

| Token                | State                              |
| -------------------- | ---------------------------------- |
| `--hw-accent`        | Rest. Focus rings, active markers. |
| `--hw-accent-hover`  | Hover.                             |
| `--hw-accent-active` | Pressed / active.                  |

### 2.6 Status Tokens

| Token           | Semantic                                              |
| --------------- | ----------------------------------------------------- |
| `--hw-danger`   | Error, destructive, failure.                          |
| `--hw-warning`  | Caution, attention.                                   |
| `--hw-success`  | Confirmation, success state (indicators, labels).     |
| `--hw-info`     | Informational, neutral attention.                     |
| `--hw-positive` | Affirming action emphasis — confirm buttons, OK CTAs. |

**Rule:** Error text uses `var(--hw-danger)`, not `text-red-400`. Warning text
uses `var(--hw-warning)`, not `text-yellow-400`. This applies everywhere —
inline messages, error labels, validation hints.

**Rule:** `--hw-positive` is for interactive affordances (button text/icons)
that signal a confirming action. It is distinct from `--hw-success`, which is
for status indicators and result labels. Do not use Quasar `color=positive` —
it bypasses the theme. Style with `.style("color: var(--hw-positive)")` instead.

### 2.7 Canvas & Node Tokens

These tokens are defined on every theme and used by the graph canvas, node
skins, and edge renderers. Panel and shell code must not reference them.

The reverse is not restricted: a node-flavoured theme may override any token
in the full vocabulary (Section 2.2–2.6 included), scoped to its own
node/graph subtree — see [theme-canon](../components/themes/theme-canon.md).
A node card's widget content (inputs, selects, ...) is brought into that
cascade via a `.ui-node-slot`-scoped forwarding block in `shell.py`,
mirroring the one panels get from `.hw-panel`.

| Token                   | Use for                                                                                                                    |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `--hw-node-bg`          | Default node card background                                                                                               |
| `--hw-node-border`      | Default node card border                                                                                                   |
| `--hw-node-header-bg`   | Node header strip background                                                                                               |
| `--hw-node-header-text` | Node header text colour                                                                                                    |
| `--hw-node-selected`    | Node border/glow when a node is selected (a selection member)                                                              |
| `--hw-node-active`      | Accent ring on the single *active* node; `--hw-accent`-based, layered on the selected glow. See Active axis in the glossary |
| `--hw-node-shadow`      | Node card drop shadow (only permitted `box-shadow` in the app)                                                             |
| `--hw-edge-default`        | Edge colour where a pin gives none (the edge SVG's `color`, drawn as `currentColor`) |
| `--hw-edge-selected`       | Glow of a selected edge |
| `--hw-edge-selected-extra` | Not applied: a selected edge keeps its own width |
| `--hw-edge-glow-size`      | Optional blur length of a selected edge's glow (default `12px`) |
| `--hw-edge-glow-strength`  | Optional opacity of a selected edge's glow, in percent (default `60%`) |
| `--hw-edge-active`         | Ring of the two end dots on the single *active* edge, which keeps its own stroke; mutually exclusive with `--hw-node-active` |
| `--hw-edge-active-extra`   | Not applied: an active edge keeps its own width |
| `--hw-canvas-bg`        | Canvas background fill                                                                                                     |
| `--hw-canvas-grid`      | Canvas grid dot/line colour                                                                                                |
| `--hw-ghost-pin`        | Ghost/unconnected pin indicator colour (rgba, low opacity)                                                                 |
| `--hw-danger-bg`        | Error node background fill (used by error skin)                                                                            |

Edge states read the semantic status tokens: an invalid edge `--hw-danger`, a warning glow `--hw-warning`, drop targets `--hw-success` / `--hw-danger`. An edge's width and arrow head are graph settings, not tokens (ADR 0045).

**Rule:** `--hw-node-shadow` is the only permitted use of `box-shadow` in the
entire application. Panel and shell chrome must use elevation colours instead.

**Rule:** `--hw-ghost-pin` replaces all hardcoded `rgba(128,128,128,…)` values
used for ghost/unconnected pin indicators in node skins.

**Rule:** `--hw-danger-bg` replaces all hardcoded `#fef2f2`/`#fee2e2` values
used in the error node skin. It should resolve to a low-saturation tint of
`--hw-danger` at the theme level.

### 2.8 Component-Specific Tokens

Tokens for named shell regions that need colours beyond the generic set.

| Token                      | Use for                                     |
| -------------------------- | ------------------------------------------- |
| `--hw-topbar-bg`           | TopBar background (may differ from surface) |
| `--hw-topbar-text`         | TopBar text and icon colour                 |
| `--hw-sidebar-bg`          | ActivityBar / ContextBar background         |
| `--hw-sidebar-icon`        | Sidebar icon colour at rest                 |
| `--hw-sidebar-icon-active` | Sidebar icon colour when active             |
| `--hw-panel-bg`            | Panel background (may equal `--hw-bg-page`) |
| `--hw-panel-text`          | Panel text colour                           |
| `--hw-panel-header-0-bg`   | Outer (depth-0) expansion header bg         |
| `--hw-panel-header-1-bg`   | Inner (depth-1) expansion header bg         |
| `--hw-statusbar-bg`        | StatusBar background                        |
| `--hw-statusbar-text`      | StatusBar text colour                       |
| `--hw-console-bg`          | Console editor background                   |
| `--hw-console-text`        | Console editor text colour                  |
| `--hw-slot-bar-bg-active`  | Bars of the active slot (optional; falls back to `--hw-bg-elevated`) |
| `--hw-popup-shadow`        | Drop shadow for floating popups and menus   |

### 2.8a Menu-Row Tokens

The whole look of a menu command — every menu, every level. Each is optional:
the `.hw-menu-row` block falls back to the semantic token beside it, so a theme
sets these only to give menus a look of their own. Nothing else styles a menu
row; there is no second place to change.

| Token                        | Falls back to      | Use for                                       |
| ---------------------------- | ------------------ | --------------------------------------------- |
| `--hw-menu-row-text`         | `--hw-text-body`   | Command label colour                          |
| `--hw-menu-row-icon`         | `--hw-text-dim`    | Leading icon and submenu chevron colour       |
| `--hw-menu-row-icon-size`    | `1.125rem`         | Icon size                                     |
| `--hw-menu-row-hover-bg`     | `--hw-bg-hover`    | Row hover background                          |
| `--hw-menu-row-font-size`    | `0.875rem`         | Label size                                    |
| `--hw-menu-row-font-weight`  | `400`              | Label weight                                  |
| `--hw-menu-row-text-transform` | `none`           | e.g. `uppercase` for a shouty menu            |

### 2.9 Z-Index Scale

Stacking order is **two scales, not one**, and they never compare. Both are
static CSS in `ui/app/shell.py` — not theme tokens, because stacking order is
structural, not a user-swappable colour.

#### The overlay ladder

Every app-global layer that portals to `<body>` and so genuinely competes.
Derived from **one** external constant: Quasar hardcodes `QMenu` and `QDialog`
both at **6000** and arbitrates between them by DOM order. Quasar exposes no
custom property for this, so the app restates it and every rung is arithmetic
on it.

| Layer                       | Value | Use for                                          |
| --------------------------- | ----- | ------------------------------------------------ |
| `--hw-z-popup-backdrop`     | 5000  | A `Popup`'s overlay / backdrop                   |
| `--hw-z-popup`              | 5001  | The `Popup` card                                 |
| `--hw-z-quasar-interaction` | 6000  | *External.* `QMenu`, `QDialog` — Quasar's own    |
| `--hw-z-menu-over-menu`     | 6001  | A flyout: a `QMenu` opened from inside a `QMenu` |

**`Popup` sits below the interaction tier on purpose.** That is what makes a
plain `ui.context_menu()`, `ui.select` or colour picker inside a `Popup` work
with **no lift and no special wrapper** — the QMenu teleports to `<body>` and
its 6000 simply wins over the card. Do not "fix" a Popup that a menu covers by
raising the Popup; that is what created the lift machinery this replaced.

**Ceiling — do not exceed 9000.** Quasar's *feedback* tier sits above
everything haywire draws: `QTooltip` at **9000**, `QNotification` at **9500**.
A toast or tooltip must stay visible over any app overlay. That is deliberate,
not an oversight to correct.

**Rule:** never a bare `z-index: 9999` or arbitrary integer in this tier. Add a
rung to the table above, derived from `--hw-z-quasar-interaction`.

#### The Popup/dialog direction rule

- `ui.dialog()` opened **from** a `Popup` — fine. The dialog's 6000 lands above.
- A `Popup` opened from an **already-open** `ui.dialog()` — broken. It renders
  behind the dialog and is invisible. **Close the dialog first**, as
  `_overview_install_flow.py` does before handing off to the install modals.

Nothing enforces this: the failure is loud and immediate (the modal simply
does not appear), so it reports itself the first time anyone hits it.

#### The canvas ladder

Local to the graph canvas and ordered *within its own stacking context*, so it
never competes with the overlay ladder despite larger raw numbers. Edge SVG <
node container < selected node < resize gadget < marquee < canvas overlays.

Inside the node container a card's z-index is its **stacking order** rank
(`0` up, written by `UINode`), so the lifts above the cards start high:
`--hw-z-canvas-selected` 1000000, `--hw-z-canvas-hover` 1000001,
`--hw-z-canvas-gadget` 1000002, the edge handles 1000003. A stage canvas
(`data-hw-stage`) skips the selected, hover and drag lifts.

**Rule:** never write a z-index on a card from JS or a skin — it is the
stacking rank. Lift with a class, as `.dragging-node` does.

Pin-interior values (`10000`+ on `.connection-pin`) are **trapped inside a
node** and rank nothing outside it — a pin's 10000 does not beat the resize
gadget's `--hw-z-canvas-gadget`. Magnitude here implies no cross-context rank; see the comments
in `canvas.vue` for the cases where that tie had to be broken in JS instead.

See .insights/feedback_nicegui_nested_menu_flyouts.md (#2) for the original diagnosis.

**Note:** NiceGUI's `ui.scroll_area()` creates a stacking context. Any `position: absolute` child inside a scroll area is clipped to it — this is expected behaviour.

### 2.10 Hover and Selection

Interactive list items and rows use a **theme-derived token** for hover, not a
hardcoded white-alpha value.

| State             | Token            | Notes                                                      |
| ----------------- | ---------------- | ---------------------------------------------------------- |
| Hover             | `--hw-bg-hover`  | Equals `--hw-bg-surface` on the default dark theme.        |
| Active / selected | `--hw-bg-active` | Clearly distinguishable from hover. Applied to active row. |

**Rule:** Never use `hover:bg-white/10`, `hover:bg-black/10`, or any
opacity-alpha class for hover states. These only work on one background tone
and break on light themes.

**Rule:** Active rows must not show the hover background in addition to the
active background. Use `pointer-events: none` or CSS specificity to suppress
hover styling when a row is active.

**Rationale:** `hover:bg-white/10` only works on dark themes. On a light theme
it creates a washed-out flash. `bg-blue-900/40` (seen in graph_manager_editor)
is likewise hardcoded and must be replaced with `--hw-bg-active`.

### 2.11 Disabled State

Disabled elements use reduced opacity. No other visual treatment is applied.

| Element            | Style                                |
| ------------------ | ------------------------------------ |
| Input, select      | `opacity: 0.5; pointer-events: none` |
| Icon action button | `opacity: 0.4; pointer-events: none` |
| Surface button     | `opacity: 0.3; pointer-events: none` |
| Menu row (`hui.submenu_row` / `hui.flyout`, disabled or retroactively greyed) | `opacity: 0.4; pointer-events: none` |

**Rule:** Always set both `opacity` and `pointer-events: none` together.
Never use a grey fill or border change to indicate disabled state — opacity
is the single, consistent signal. A menu row follows the same rule whether it
was constructed `enabled=False` or greyed *retroactively* after its flyout
body drew nothing (see `.insights/feedback_nicegui_nested_menu_flyouts.md`,
"Sibling-group ownership and retroactive greying") — both read identically to
the user, and neither ever gets a grey fill.

**Rule:** Quasar's `:disable` prop handles both correctly for `QBtn` and
`QInput`. Prefer it over manual class application where available.

### 2.12 Drag-and-Drop Tokens

These tokens are used when items are dragged within or between panels.

| Token             | Use for                                    |
| ----------------- | ------------------------------------------ |
| `--hw-drag-over`  | Drop-target highlight (border or bg tint)  |
| `--hw-drag-ghost` | Dragged item ghost opacity (typically 0.5) |

**Rule:** Drag-over state is indicated by a `2px solid var(--hw-drag-over)`
border, not a background fill. The border is added/removed via a CSS class
(e.g. `hw-drop-target`) toggled in JS drag event handlers.

---

## 3. Typography

### 3.1 Type Scale

Haywire uses four deliberately chosen size tiers. The system font stack is
inherited from Quasar (Roboto / system sans-serif).

| Tier    | Tailwind class | Line-height | Use for                              |
| ------- | -------------- | ----------- | ------------------------------------ |
| Display | `text-2xl`     | default     | Library name in detail view. Rare.   |
| Heading | `text-base`    | default     | Component label, panel title.        |
| Body    | `text-sm`      | default     | Descriptions, list items, body copy. |
| Caption | `text-xs`      | default     | Metadata, versions, registry keys.   |

**Rule:** `text-lg` is not a design tier. It is only used for the application
wordmark ("Haywire" in the topbar). Do not use it elsewhere.

**Rule:** `text-2xl` is only for the library detail display title. Do not use
it elsewhere.

### 3.2 Weight

| Weight        | Tailwind class | Use for                                  |
| ------------- | -------------- | ---------------------------------------- |
| Regular (400) | (default)      | Body text, descriptions                  |
| Medium (500)  | `font-medium`  | List item names, panel header labels     |
| Bold (700)    | `font-bold`    | Headings, section group labels, emphasis |

### 3.3 Monospace

Use `.font-mono` for: file paths, registry keys, code snippets, module paths, import statements, and any machine-readable identifier.

Always pair `.font-mono` with `.text-xs` — monospace text at `text-sm` feels too large relative to proportional text at the same size.

### 3.4 Tracking Labels

Section group headers (REQUIRED, ENABLED, IDENTIFIERS, etc.) follow a fixed
formula:

```
.text-xs .font-bold .tracking-wider .uppercase .hw-text-dim
```

These labels are structural markers, not content — they should be the dimmest text in the panel.

The formula is the `.hw-section-label` class; draw one with `hui.section_label()`
(§8.5b) or, for a settings category, `hui.category_group()` (§8.21). Never
write the classes by hand. Pass the text in sentence case: the class
uppercases it.

### 3.5 Truncation

**Rule:** Any text that can overflow its container must include `.truncate`.
The parent flex container must include `.min-w-0` to allow truncation to work inside flex layouts.

**Exception — `QBtn` labels:** Quasar renders a button's label inside an inner
`<span>` that `.truncate` cannot reach. Use the `no-wrap` Quasar prop instead
(`hui.button` already applies this). Do not add `.truncate` to a `ui.button`.

For values that are programmatically too long, truncate in Python and provide the full value via `.tooltip()`:

```python
short = (value[:48] + "…") if len(value) > 50 else value
hui.info_row("Module", short, copy_value=full_value)
```

### 3.6 Label Hierarchy

Inside a panel, popup, dialog or flow step, text takes one of five roles. Each
role is a CSS class in the shell stylesheet and a `hui` helper; the helper is
how you draw it.

| Role          | Class               | Helper                | Look                                   | Use for                                                       |
| ------------- | ------------------- | --------------------- | -------------------------------------- | ------------------------------------------------------------- |
| Heading       | `.hw-heading`       | `hui.heading()`       | `text-sm font-medium`, `--hw-text-body` | The one title line of a dialog or flow step.                  |
| Section label | `.hw-section-label` | `hui.section_label()` | §3.4                                   | A group within the screen.                                    |
| Subject       | `.hw-subject`       | `hui.subject()`       | `text-xs font-medium`, `--hw-text-body` | The name a row or box is about (a package, a conflict).       |
| Body          | —                   | `ui.label().classes("text-sm")` | `text-sm`                    | A statement or a question the user acts on.                   |
| Hint          | `.hw-hint`          | `hui.hint()`          | `text-xs`, `--hw-text-muted`           | Explanation, status, metadata.                                |

**Rule:** a screen has at most one heading. In a step flow the stepper draws
it from the flow's `STEP_TITLES`; a panel never draws its own, and never
repeats the popup title.

**Rule:** a hint is `--hw-text-muted`, not `--hw-text-dim`: it is read, and dim
is reserved for structural labels (§11.2).

**Rule:** the Heading tier of §3.1 (`text-base`) is the title of a detail
view (Component Docs), not of a dialog or flow step.

---

## 4. Spacing System

### 4.1 The Scale

Haywire uses a constrained subset of Tailwind's spacing scale. Using values
outside this set requires justification.

| Token | Value | Name     | Primary use                             |
| ----- | ----- | -------- | --------------------------------------- |
| `0`   | 0px   | None     | Between tightly coupled elements        |
| `0.5` | 2px   | Hairline | Between toggle buttons, icon groups     |
| `1`   | 4px   | Tight    | Between port rows, compact field stacks |
| `1.5` | 6px   | Snug     | Vertical padding on list items          |
| `2`   | 8px   | Base     | Section padding, search bar, icon+label |
| `3`   | 12px  | Loose    | Between major sections, topbar padding  |
| `4`   | 16px  | Spacious | Content area padding (docs, detail)     |
| `6`   | 24px  | Page     | Page-level padding (library detail)     |

### 4.2 Panel Padding Rules

| Panel region          | Horizontal  | Vertical    |
| --------------------- | ----------- | ----------- |
| Panel header          | `px-2`      | `py-1.5`    |
| Info bar              | `px-3`      | `py-1`      |
| List item             | `px-2`      | `py-1.5`    |
| Section group label   | `px-2`      | `pt-2 pb-1` |
| Content area (scroll) | `p-4`       | —           |
| Detail page content   | `px-6 pt-6` | —           |

### 4.3 Gap Rules

| Context                    | Gap     |
| -------------------------- | ------- |
| Column of list items       | `gap-0` |
| Compact field stack        | `gap-1` |
| Icon + label in a row      | `gap-2` |
| Sections within a panel    | `gap-3` |
| Empty state icon + message | `gap-3` |

### 4.4 Height Fixtures

Certain UI elements have fixed heights. These are not negotiable — they ensure
the shell geometry is predictable.

| Element              | Height  | Set via                   |
| -------------------- | ------- | ------------------------- |
| TopBar               | 48px    | inline style              |
| StatusBar            | 24px    | inline style              |
| ActivityBar width    | 48px    | inline style              |
| ContextBar width     | 48px    | inline style              |
| Middle tab bar       | 36px    | `min-height` inline style |
| Slot bar             | 36px    | tab bar row, `hui.slot_header` |
| Editor toolbar       | 32px    | `hui.editor_toolbar`      |
| Scope toolbar button | 36×36px | inline style              |
| Compact field input  | 26px    | `--hw-compact-field-h`    |

### 4.5 Compact-Fields System

Settings panels use a compact layout system for dense label/widget rows: tight
Quasar fields, and a label that takes half the row up to a maximum width
(`--hw-max-label-width`, default 9rem) while the widget takes the rest. So a row
is split 50/50 until it is twice the maximum wide, then only the widget grows.
A widget node's stage face uses the same rule and sets the maximum per node.

**How to use:**

```python
with ui.column().classes("w-full gap-0 compact-fields"):
    # Each row uses _ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
    with ui.row().classes("w-full items-center justify-between gap-0 px-2"):
        ui.label("My Field").classes("text-xs truncate sf-label")
        my_widget.classes("sf-widget")
```

**CSS classes in this system:**

| Class            | Purpose                                                     |
| ---------------- | ----------------------------------------------------------- |
| `compact-fields` | Applied to the outer column. Tightens the Quasar fields inside. |
| `sf-label`       | Label cell: `min(50%, var(--hw-max-label-width, 9rem))` wide. |
| `sf-widget`      | Widget cell. Takes the remaining space.                     |

**CSS tokens for this system:**

| Token                    | Default | Purpose                                 |
| ------------------------ | ------- | --------------------------------------- |
| `--hw-compact-field-h`   | 26px    | Fixed input height for compact widgets. |
| `--hw-max-label-width`   | 9rem    | The widest an `sf-label` gets; set on a row or any ancestor. |
| `--hw-compact-gap`       | 1px     | Vertical gap between compact rows.      |
| `--hw-compact-row-min-h` | 28px    | Minimum row height in compact mode.     |

**Rule:** Only use `compact-fields` for settings/property panels. Regular
editor content uses the standard gap/padding system (§4.1–4.3).

**Rule:** Never apply `compact-fields` and `p-4` to the same container. Compact
panels use `p-0` or `p-1` on their outer column.

### 4.6 Insets and Indentation

Two tokens place labels and lists horizontally:

| Token              | Default  | Purpose                                                                 |
| ------------------ | -------- | ----------------------------------------------------------------------- |
| `--hw-inset`       | `0.5rem` | Where a section label's text starts. 0 in a popup body, a dialog card and a `hui.box()`, which pad their own content. |
| `--hw-indent-step` | `12px`   | One level of indentation.                                               |

So a section label lines up with `hui.list_item` rows (`px-2`) in a panel, and
with the body text in a popup, without the caller choosing.

- `hui.indented()` is the column for items listed under a label: one step in
  from where the label's text starts. Nest it once per level.
- `hui.box()` is a bordered group (`1px solid var(--hw-border)`, 4px, `p-2`,
  `--hw-bg-surface`). A section label as its first child has no top padding.

**Rule:** never indent with `ml-*` / `pl-*` or an inline `margin-left`. Use
`hui.indented()`. Canvas content (skins, node widgets) follows §9.6 instead.

```python
hui.section_label("Will be written")
hui.hint("These sources will be contacted:")
with hui.indented():
    for url in urls:
        ui.label(url).classes("text-xs font-mono")
```

---

## 5. Border Radius

### 5.1 The Scale

| Token  | Value | Use for                                 |
| ------ | ----- | --------------------------------------- |
| `none` | 0     | Scope toolbar buttons, tab indicators   |
| `sm`   | 4px   | Inputs, list items, code blocks, badges |
| `md`   | 8px   | Cards, dialogs, expansion panels        |
| `lg`   | 10px  | Toolbar icon buttons                    |
| `full` | 9999  | Status dots, circular icon buttons      |

**Rule:** Toolbar icon buttons (activity bar, context bar) use `border-radius: 10px`
(the `lg` tier). This is their identity — don't flatten them to `0` or round
them to `full`.

**Rule:** Scope toolbar buttons in the properties editor use `border-radius: 0`.
They tile vertically and any radius creates visual gaps.

**Rule:** Quasar `.rounded` maps to `4px` which is our `sm` tier. Use `.rounded`
on list items and interactive rows.

---

## 6. Iconography

### 6.1 Icon Set

Material Icons via Quasar. No other icon set.

### 6.2 Size Rules

| Context               | Size    | Implementation           |
| --------------------- | ------- | ------------------------ |
| Toolbar button        | 24px    | Quasar default (no prop) |
| Panel header inline   | 16px    | `size="16px"`            |
| Info bar inline       | 14px    | `size="14px"`            |
| Empty state           | 36–48px | `size="40px"` typical    |
| Inline text indicator | 10–14px | `size="10px"` / `"14px"` |

### 6.3 Colour Rules

| Context                 | Colour                                                          |
| ----------------------- | --------------------------------------------------------------- |
| Decorative / structural | `.hw-text-dim`                                                  |
| Interactive (rest)      | Inherited (`--hw-text-muted`)                                   |
| Interactive (hover)     | Inherited (`--hw-text-body`)                                    |
| Interactive (active)    | Inherited (`--hw-accent`)                                       |
| Quasar `color=` prop    | Add `.hw-use-props-color` to opt out of the global dim override |

**Rule:** Never use `text-purple-500`, `text-blue-400`, or any Tailwind colour
class on an icon. If an icon needs a semantic colour, use Quasar's `color=`
prop with `.hw-use-props-color`, or style it with a `--hw-*` token.

### 6.4 Standard Icon Vocabulary

Icons are named via `AppIcon` (`haywire/ui/elements/icons.py`), exposed as the
`hui.icon` alias. Each Material icon string appears at most once — one icon,
one concept.

```python
hui.icon_action(hui.icon.refresh, on_click=self._refresh)
```

See `hui.icon` for the most current mappings between use and icon name.

**Rule:** Never use a raw Material icon string (`icon="refresh"`) in editor or
panel code. Always reference `hui.icon.<name>`. If the concept you need has no
entry yet, add one to `AppIcon` rather than inlining the raw string.

---

## 7. Transitions & Motion

Two tiers of transition timing exist in Haywire. They are deliberately different
because shell UI and canvas objects have different perceptual scales.

### 7.1 Shell / Panel Transitions (0.15s)

All interactive state changes in the shell, panels, editors, and toolbars use:

```
transition: <property> 0.15s ease;
```

This applies to toolbar buttons, list item hover, scope buttons, input focus,
and icon colour changes. `hui` encodes this via the `_TRANSITION_BG` constant.

### 7.2 Canvas / Node Transitions (up to 0.3s)

Node skins and canvas-level animations may use longer durations because objects
on the canvas are perceived at a greater visual distance and need slightly more
time to read as intentional motion.

```
transition: <property> 0.2s ease;   /* node state changes */
transition: <property> 0.3s ease;   /* node enter/exit, error flash */
```

**Rule:** Durations above `0.3s` are not permitted anywhere in the codebase.

**Rule:** `transition: all` is not permitted. Always name the specific property.

### 7.3 Animated Properties

| Property           | Tier   | Context                                    |
| ------------------ | ------ | ------------------------------------------ |
| `background-color` | Shell  | Toolbar buttons, list item hover           |
| `color`            | Shell  | Icon and text colour on hover              |
| `box-shadow`       | Shell  | Active toolbar button ring                 |
| `opacity`          | Both   | Disabled scope buttons; node widget appear |
| `border-color`     | Shell  | Input focus                                |
| `background`       | Canvas | Node error state, node skin state changes  |

### 7.4 Not Animated

Layout changes (panel show/hide, content rebuilds, scroll) are instant. No
`transition` on `width`, `height`, `flex`, `padding`, `margin`, or `display`.

---

## 8. Component Patterns (hui API)

Each pattern below is defined as a `hui` wrapper function. The function
signature, visual rules, and example usage are documented together.

**Import convention:** `hui` is imported once at module level —
`from haywire.ui import elements as hui` — never inside a method or function
body. This matches the pattern used throughout `haywire/ui/panel/` and every
editor in the barn.

**Panels specifically** (as opposed to editors) receive a `PanelLayout`
container in `draw(context, layout)` rather than a raw NiceGUI element. It is
not a façade over `hui` — activate it with `with layout:` and call `hui.*`
directly inside. See [components/panels/panel-canon.md](../components/panels/panel-canon.md)
for the full `BasePanel` / `PanelLayout` authoring contract, including
`layout.state_bag` for persisting panel UI state (collapsed sections, scroll
position) across redraws.

### 8.1 `hui.panel_header(title, icon=None)`

A slim bar at the top of a panel. Returns a `ui.row` context manager.
Action buttons should be placed inside the `with` block.

**Anatomy:**

```
┌─[icon 16px]─[title text-sm font-medium]────────────[action buttons]─┐
│                         border-b                                      │
```

**Visual rules:**

- Padding: `px-2 py-1.5`
- Background: inherited from parent (transparent)
- Bottom border: `1px solid var(--hw-border)`
- `flex-shrink-0` to prevent compression
- Icon: 16px, `hw-text-dim`
- Title: `text-sm font-medium hw-text-body truncate flex-1`
- Actions: `hui.icon_action()` buttons floated right

```python
with hui.panel_header("Files", icon="folder") as header:
    hui.icon_action("refresh", tooltip="Refresh", on_click=self._refresh)
```

### 8.1a `hui.slot_header(title=None, icon=None, is_dirty=False)` and `hui.editor_toolbar()`

Every slot has one **slot bar** on top: the shell's tab bar in EDIT and INFO,
the editor's `hui.slot_header` in ACTION and CONTEXT. Both are 36px,
`var(--hw-bg-surface)`, with a `--hw-border` line beneath. A second row an
EDIT or INFO editor draws under the tab bar is an **editor toolbar**:
`hui.editor_toolbar`, 32px, same background and line.

The **active slot** — the last slot clicked that shows an editor, or comes to
show one before the next click (a collapsed rail expanding), which takes the
key presses — lights its slot bar and, in ACTION and CONTEXT, its selected
rail icon with `--hw-slot-bar-bg-active`. An editor toolbar never lights.

- `slot_header` holds `panel_header`'s icon, dirty dot and title, then the
  actions inside the `with` block; with no `title` it holds only the icon and
  dirty dot asked for, and the caller fills the rest (Component Source draws
  its path there).
- An ACTION or CONTEXT editor with no header (Properties, Shortcuts, Component
  Docs) shows the active slot through its rail icon alone.
- `panel_header` stays the header of a panel *inside* an editor.

**Rule:** a Save icon in a slot header or editor toolbar shows only while its
document has something to save — unsaved edits, or text that differs from the
file — and hides again after a save. A document never saved shows no Save
until it is edited; Save As stays available. Ctrl+S works either way.

**Rule:** never use a bare Tailwind `border`, `border-b`, `border-t` … class.
Tailwind 4's preflight leaves its colour `currentColor`, so the line is drawn
in the text colour — near-white on the dark theme. Write
`border-bottom: 1px solid var(--hw-border)` (`_BORDER` in `elements.py`).
`tests/ui/test_slot_bars.py` fails on a bare one in an editor or the shell.

```python
with hui.slot_header("Files", icon="folder"):
    hui.icon_action("refresh", tooltip="Refresh", on_click=self._refresh)

with hui.editor_toolbar():
    ui.label(str(path)).classes("text-xs hw-text-muted truncate flex-1")
```

### 8.2 `hui.info_bar(label, badge=None, suffix=None)`

A contextual metadata bar (e.g. showing the open file name + language + size).

**Visual rules:**

- Height: `min-height: 28px`
- Padding: `px-3 py-1`
- Background: `var(--hw-bg-surface)`
- Bottom border: `1px solid var(--hw-border)`
- `flex-shrink-0`
- Label: `text-xs font-medium hw-text-body`
- Badge (optional): Quasar badge with `color=blue-grey rounded outline text-xs`
- Suffix (optional): `text-xs hw-text-dim ml-auto`

```python
hui.info_bar("main.py", badge="python", suffix="12,480 B")
```

### 8.3 `hui.empty_state(message, icon="folder_open", hint=None)`

Centered placeholder for panels with no content.

**Visual rules:**

- Centred vertically and horizontally
- Vertical padding: `60–80px` top (pushes into upper-centre)
- Icon: `36–48px`, `hw-text-dim`
- Primary message: `text-sm hw-text-muted`
- Hint (optional): `text-xs hw-text-dim` or `hw-text-muted`
- Gap between icon and text: `gap-3`

```python
hui.empty_state(
    "Select a file from the Files panel",
    icon="folder_open",
)
```

### 8.4 `hui.list_item(label, sublabel=None, dot_color=None, is_active=False, on_click=None)`

An interactive row for browsers and selection lists.

**Visual rules:**

- Padding: `px-2 py-1.5`
- Full width, `rounded` (4px)
- Hover: `var(--hw-bg-hover)` background (not `bg-white/10`)
- Active (`is_active=True`): `var(--hw-bg-active)` background; hover suppressed
- Cursor: `pointer`
- Gap: `gap-2`
- Status dot (optional): `w-2 h-2 rounded-full`, Quasar named colour
- Label: `text-sm font-medium truncate`; `hw-text-body` when active, `hw-text-muted` otherwise
- Sublabel: `text-xs hw-text-dim`
- Parent text column: `flex-1 gap-0 min-w-0`

**Rule:** Never use `bg-blue-900/40` or other hardcoded colours for active rows.
Always pass `is_active=True` and let the token do the work.

```python
hui.list_item(
    "Visiongraph",
    sublabel="v0.0.1",
    dot_color="green",
    is_active=entry is active_entry,
    on_click=lambda: self._select(lib),
)
```

### 8.5a `hui.label(text)`

A body-tier text label.

**Visual rules:**

- Text: `text-sm hw-text-body`

```python
hui.label("No settings available.")
```

### 8.5b `hui.section_label(text)`

An uppercase tracking label that separates groups within a list or panel.

**Visual rules:**

- Class: `.hw-section-label` — `text-xs`, bold, tracking, uppercase, `hw-text-dim`
- Padding: `0.5rem var(--hw-inset) 0.25rem` (§4.6); none in a row beside an icon
- The text is uppercased by CSS — pass sentence case

```python
hui.section_label("Required")
```

### 8.5c `hui.heading(text)`, `hui.subject(text, mono=False, tone=None)`, `hui.hint(text)`

The heading, subject and hint roles of §3.6. `subject(mono=True)` is for
identifiers; `tone="--hw-positive"` recolours it. Chain `.classes()` on a hint
for `font-mono`, `truncate` or `whitespace-pre-line`.

```python
hui.heading("Save changes before closing?")
hui.subject("haybale_core", mono=True, tone="--hw-warning")
hui.hint("Nothing is written until you apply.")
```

### 8.5d `hui.indented(gap="gap-0.5")` and `hui.box(gap="gap-2")`

The indentation column and the bordered group of §4.6. Both return a
`ui.column` to use as a context manager.

```python
with hui.box():
    hui.section_label("Version")
    hui.hint("Every library publishes at the same version.")
    with hui.indented():
        ui.label("haybale-core: 0.4.1").classes("text-xs font-mono")
```

### 8.6 `hui.info_row(label, value, copy_value=None)`

A key-value metadata row with optional copy button.

**Visual rules:**

- Row: `w-full items-center gap-1 py-0.5`
- Copy button (if `copy_value` provided): `hui.icon_action("content_copy")`
- Label: `text-xs hw-text-dim`, fixed width `w-16 flex-shrink-0`
- Value: `text-xs font-mono truncate flex-1 hw-text-body`

```python
hui.info_row("Key", "visiongraph:node:WebcamFrameEvent", copy_value=full_key)
```

### 8.7 `hui.code_snippet(code, label=None, copyable=True)`

A read-only code snippet with optional label and copy button.

**Visual rules:**

- Outer column: `w-full gap-0.5 py-1`
- Label (optional): `text-xs hw-text-dim`
- Code container: `var(--hw-bg-surface)` background, `rounded` (4px), `px-2 py-1`,
  `1px solid var(--hw-border)`
- Code text: `text-xs font-mono hw-text-body`
- Copy button inline

```python
hui.code_snippet(
    "from haybale_visiongraph import WebcamFrameEventNode",
    label="Import",
)
```

### 8.8 `hui.icon_action(icon, tooltip=None, on_click=None, size="xs", command=None)`

A minimal icon-only button for inline actions.

**Visual rules:**

- Props: `flat round dense size={size}`
- Colour: inherited (theme-aware), no Quasar `color=` prop
- Tooltip applied if provided

```python
hui.icon_action("refresh", tooltip="Refresh tree", on_click=self._refresh)
```

### 8.8a `hui.button(label, icon=None, tooltip=None, on_click=None, disabled=False)`

A flat labelled action button for use inside panels. Distinct from `hui.icon_action`
(icon-only), `hui.dialog_actions` (confirm/cancel pair) and `hui.menu_row` (§8.8b —
a command in a menu). Use when a visible text label is needed, optionally with a
leading icon.

**Not for menus.** A `QBtn` carries Quasar's own look — `text-primary` from
NiceGUI's default `color='primary'`, `text-transform: uppercase` from `.q-btn` —
which no `--hw-*` token reaches. Use `hui.menu_row` on any menu surface.

**Visual rules:**

- Props: `flat dense align=left no-wrap`
- Classes: `text-sm w-full flex`
- Colour: inherited — never use Quasar `color=` prop
- Disabled: `opacity: 0.5; pointer-events: none`

`flex` is load-bearing. A `QBtn` is `display: inline-flex`, so stacked buttons are
inline-level boxes sharing one line box, and `w-full` drops out of intrinsic
sizing — inside a shrink-to-fit container (a flyout `QMenu`, any content-sized
popup) the container's max-content becomes the *sum* of the labels and the menu
stretches to the viewport edge. `display: flex` makes each button block-level;
Quasar's own `flex-direction: column; align-items: stretch` still applies, so the
button looks identical. Never "fix" that symptom with a width on the menu.

```python
hui.button("Delete Node", icon="delete", on_click=self._delete)
hui.button("Refresh", icon="refresh", on_click=self._refresh)
```

### 8.8b `hui.menu_row(label, icon=None, on_click=None, enabled=True, tooltip=None, command=None, closes=True)`

One command in a menu — the leaf counterpart of `hui.submenu_row`, which *is* one
(plus a chevron), so a command and the submenu row beside it cannot drift.

**Visual rules:** none are set on the element. Every property comes from the single
`.hw-menu-row` CSS block in `app/shell.py`, and every value in it reads a
`--hw-menu-row-*` token (§2.8a). Change a menu's look there or in a theme — never
per call site.

The block is keyed on the row's own marker class, never on an ancestor. A flyout
`QMenu` portals to `<body>`, so an ancestor-scoped rule (`.hw-panel .q-icon`, for
one) styles a row inside a popup and misses the identical row inside a flyout —
which is how one menu ends up with three different colours.

- Disabled: `enabled=False` → `opacity: 0.4; cursor: default`, the menu
  convention (an inapplicable command greys rather than disappearing). This is
  what `draw_disabled()` renders.
- A disabled row **keeps its pointer events**, so `tooltip=` still works on
  one — a greyed command is where the user most wants to know *why*. The
  hover background opts out via `.hw-menu-row:not(.hw-disabled):hover` rather
  than by blinding the row. Don't reintroduce `pointer-events: none` here: it
  silently swallows the tooltip, and nothing else needs it (`on_click` is
  never wired when disabled).
- The submenu anchor greyed by an empty flyout is the **exception** — it keeps
  `pointer-events: none` (inline, from `flyout._DISABLED_STYLE`, so it wins
  over the class rule) because there it is what stops an empty flyout opening
  on hover.

```python
hui.menu_row("Delete Node", icon=hui.icon.delete, on_click=self._delete)
hui.menu_row("Delete", icon=hui.icon.delete, enabled=False)   # draw_disabled()
hui.menu_row(                                                 # say why it's greyed
    "Detach", icon=hui.icon.delete, enabled=False,
    tooltip="Only a promoted pin can be detached",
)
hui.menu_row("Copy", icon=hui.icon.copy, on_click=self._copy, command=Copy)  # ⌘C / Ctrl+C suffix
```

`command=` names the `EditorCommand` the row performs, only to draw its first
default shortcut as the suffix (`hui.key_hint`, §8.23); `on_click` still does the
work. `hui.icon_action(..., tooltip="Copy", command=Copy)` appends the shortcut to
the tooltip instead (`Copy (Ctrl+C)`, in the non-macOS spelling on every
platform, since a tooltip is plain text); without a `tooltip` there is nothing to
append to.

**Closing.** Whether a click closes a menu is decided by `closes=`, on the
container and on the control, never by the action it calls: a host's verbs
(`self.actions.*`) never close anything.

On a container, `closes` says whether a command inside closes it — whether
picking something there ends the interaction. A **menu** (pick and done)
closes: a context-menu `Popup` (via `open_flyout_group(dismiss=popup.close)`),
a `hui.flyout`, a `hui.submenu_row`, and a `hui.dropdown(..., closes=True)` such
as the selection toolbar's ⋯. A **panel** (stay and work) does not:
`hui.dropdown` by default, `hui.submenu_row(closes=False)`. Nothing inside a
panel closes it, neither a field nor a button beside it, whatever the control
says. Either kind still closes on click-away. A toolbar is neither and stays
up. A menu inside a menu defers to the outer one, so a command closes all of it.

On a control, `closes` is its own say inside a menu, which closes after its
`on_click` runs:

- `hui.menu_row` and `hui.icon_action` both close by default. Pass
  `closes=False` for a command whose result the menu shows — a toggle that
  relabels its own row (Collapse, edge Propagation, Developer mode).
- Anything else clickable — a list, a tree, a custom widget — takes
  `dismiss = hui.menu_dismiss()` while drawing and calls `dismiss()` when it is
  done. `CreateNodeMenuPanel` does this for its node list.

```python
hui.menu_row("Copy", icon=hui.icon.copy, on_click=self.actions.copy_selection)  # closes
hui.menu_row("Collapse", icon=hui.icon.node_collapse, on_click=_toggle, closes=False)
hui.icon_action(hui.icon.paste, tooltip="Paste", on_click=self.actions.paste_at_click)  # closes

dismiss = hui.menu_dismiss()   # in draw(): for a control that isn't a row
def _on_node_selected(info):
    self.actions.create_node_at_click(info.identity.registry_key)
    dismiss()
```

### 8.8c `hui.flyout(icon, tooltip=…)` vs `hui.dropdown(icon, tooltip=…, align="left", direction="down", closes=False)`

Two icon anchors that open a hosted surface. Same sibling group (one open path
at a time), same cascade-close, same retroactive greying of an empty body. Pick
by **what hangs off them**, never by where you want it on screen:

| | `hui.flyout` | `hui.dropdown` |
| --- | --- | --- |
| Holds | commands (`hui.menu_row`) | fields, widgets, a mini panel |
| Opens | beside the anchor (`anchor="top end"`) | below or above it, placed by `align=` + `direction=` |
| Trigger | hover, after a ~120 ms debounce | click |
| `auto-close` | yes — a command dismisses its menu | **no** |
| Nested popups | left alone | lifted above the dropdown |

**Rule:** never give a dropdown `auto-close`. Quasar's `auto-close` dismisses the
menu on *any* click inside it, so the first click into a field closes the panel
you just opened. Conversely, never drop `auto-close` from a command flyout — a
menu that survives its own command reads as broken. A dropdown that holds
commands anyway (the selection toolbar's ⋯) says so with `closes=True`: it
still has no `auto-close`, but its commands close it (§8.8b).

Both anchors' menus carry `hw-menu-card`, styled in `app/shell.py` to the
context-menu `Popup`'s frame (radius, shadow, padding), so the same rows look
the same in a popup, a flyout or a dropdown.

The two remaining rows are consequences of holding content: a select's option
list or a colour picker is a Quasar portal of its own at z-6000, *behind* the
dropdown that spawned it, and it teleports to `<body>` where no CSS rule can
reach it — so `hui.dropdown` stamps the lift on everything in its body (contrast
`hui.select_field(in_popup=True)`, which is opt-in precisely because a panel's
own select must *not* float above popups).

A body must still be built from panels: the emptiness rule counts what
`render_panel` drew, so fields rendered straight into the body leave the counter
at zero and the anchor greys itself. Host a surface (ADR-0029) and put the
fields in a panel on it.

**Placement — two independent axes.** A Quasar anchor point is two words,
vertical then horizontal, and those are two separate questions, so they are two
parameters rather than six compound names. Both are named the way `text-align`
is: they say where the *panel* sits, not which way it travels. An unknown value
on either raises at construction.

`align` — the horizontal edges:

| `align` | Edges that meet | Grows | Use for |
| --- | --- | --- | --- |
| `"left"` (default) | panel's left ↔ icon's left | rightward | an icon at the left of its row |
| `"center"` | midpoints | both ways | an icon in the middle of a toolbar |
| `"right"` | panel's right ↔ icon's right | leftward | the last icon before a screen edge |

`direction` — the vertical side:

| `direction` | Edges that meet | Use for |
| --- | --- | --- |
| `"down"` (default) | panel's top ↔ icon's bottom | almost everything |
| `"up"` | panel's bottom ↔ icon's top | a toolbar along a bottom edge, a status-bar control |

**Reach for `direction="up"` only when up is what you want while down would still
fit.** When down does not fit, Quasar already flips on its own — measured: the
same three dropdowns on a toolbar pinned to the bottom of the window all opened
upward, alignment intact, with no `direction=` anywhere. Which is also why
neither parameter is a promise: never lay content out assuming the panel is
exactly where you asked.

```python
with hui.dropdown(hui.icon.theme, tooltip="Appearance"):
    self.render_surface(NodeAppearance, ctx)      # content, below the toolbar

with hui.dropdown("tune", tooltip="Filters", align="right"):
    self.render_surface(FilterPanel, ctx)         # last icon: grow leftward

with hui.dropdown("palette", align="center", direction="up"):
    self.render_surface(Swatches, ctx)            # toolbar on a bottom edge

with hui.flyout("more_horiz", tooltip="More actions"):
    self.render_surface(SelectionMenu, ctx)       # commands, beside the icon
```

### 8.9 `hui.toolbar_button(icon, is_active=False, tooltip=None, on_click=None)`

An icon button for the activity bar or context bar.

**Visual rules:**

- Size: `w-10 h-10` (40×40px)
- Classes: `hw-shell-toolbar-btn`, plus `hw-shell-toolbar-btn-active` if active
- Props: `flat round`
- States: rest → muted, hover → elevated bg + body colour,
  active → elevated bg + accent colour + inset ring

```python
hui.toolbar_button("folder", is_active=True, tooltip="Files", on_click=switch)
```

### 8.10 `hui.surface_button(icon, is_active=False, available=True, tooltip=None, on_click=None)`

A square button for the properties editor's SurfaceToolbar.

**Visual rules:**

- Size: `36×36px`
- Border-radius: `0` — tiles vertically; any radius creates visual gaps
- Active: `var(--hw-accent)` background, `#ffffff` text
- Unavailable: `opacity: 0.3`, `pointer-events: none`
- Transition: `background 0.15s`

```python
hui.surface_button("settings", is_active=True, tooltip="Node Properties")
```

### 8.11 `hui.expansion_section(label, icon=None, default_open=True, context=None, panel_key=None)`

A collapsible section for grouped content in property panels.

**Visual rules:**

- Bottom border: `1px solid var(--hw-border)`
- Header label colour: `--hw-text-expansion` (special-purpose token — set per theme)
- Header label size/weight: Quasar's default expansion header — `text-sm font-medium`
- Persists expansion state to `context.metadata` under the given `panel_key`

**Rule:** Do not use `ui.expansion()` directly in property panels. Header styling
(font size, colour token, border) is only guaranteed correct via this wrapper.
For settings category groups, use `hui.category_group()` instead (§8.21).

```python
with hui.expansion_section("Node", icon="settings", context=ctx, panel_key="node"):
    # Panel content
```

### 8.12 `hui.error_label(text)`

An error message label.

**Visual rules:**

- Text: `text-sm` with `color: var(--hw-danger)`
- Padding: `p-4`
- Never use `text-red-400`

```python
hui.error_label(f"File not found: {path}")
```

### 8.13 `hui.warning_label(text)`

A warning message label.

**Visual rules:**

- Text: `text-sm` with `color: var(--hw-warning)`
- Never use `text-yellow-400`

### 8.14 `hui.tag(text, color="grey")`

A small metadata tag / badge.

**Visual rules:**

- Quasar badge: `outline` prop, `.text-xs`
- Named colour via Quasar `color=` prop (acceptable exception to the no-hardcoded rule)

```python
hui.tag("vision")
hui.tag("editable", color="green")
```

### 8.14a `hui.count_badge(count, tone, floating=False)`

A count filled with a status colour: unseen errors on a tab, a node's diagnostics.

**Visual rules:**

- Fill `var(--hw-<tone>)`, text `var(--hw-bg-page)`: legible in every theme. Never a
  Quasar `color=` name, whose white text vanishes on a light status colour.
- `tone` is one of `danger`, `warning`, `info`, `success`.
- `.text-xs`; `floating=True` pins it to its parent's top-right corner.

```python
hui.count_badge(len(unseen), tone="warning")
with ui.button(icon=hui.icon.warning):
    hui.count_badge(3, tone="danger", floating=True)
```

### 8.15 `hui.input_field(label=None, **props)`

A standard text input, pre-configured for panel use.

**Visual rules:**

- Props: `dense outlined`
- Classes: `w-full`
- Background: `var(--hw-bg-input)` (automatic via global CSS)
- Border: `var(--hw-border)` rest, `var(--hw-border-strong)` hover/focus
- Focus ring: `2px solid var(--hw-accent)` via `:focus-visible` — keyboard-only,
  not shown on mouse click (use `:focus-visible`, not `:focus`)
- Floating label (`label=`): `var(--hw-text-muted)` at rest, `var(--hw-accent)`
  on focus — applied globally so an empty field's label never reads like an
  entered value. Do not override per-field.
- Disabled: pass Quasar `:disable="True"` — renders `opacity: 0.5` automatically
- Validation error: pass Quasar `:rules=` and `lazy-rules="ondemand"` — error
  text appears below the field using `var(--hw-danger)`; never use a separate
  `hui.error_label()` to annotate a field inline

```python
hui.input_field(placeholder="Search libraries…", clearable=True)
hui.input_field(label="Port", rules=[lambda v: v.isdigit() or "Must be a number"])
```

### 8.16 `hui.tabs(*tab_defs, dense=True)`

A tab bar, pre-configured with `hw-slot-bar-tabs` styling.

**Visual rules:**

- Classes: `w-full hw-slot-bar-tabs`
- Props: `dense no-caps`
- Tab label font: 12px (`text-xs`)
- Active indicator: `2px solid var(--hw-accent)` (bottom bar)
- Active tab label: `--hw-text-body`
- Inactive tab label: `--hw-text-muted`
- Tab bar bottom border: `1px solid var(--hw-border)`
- Tab hover: `--hw-bg-hover` background
- Overflow: tabs scroll horizontally (`QTabs` default) — do not truncate or wrap

```python
with hui.tabs(("Graph", "account_tree"), ("Library", "widgets")) as tabs:
    ...
```

### 8.17 `hui.number_field(label=None, value=0, **props)`

A standard number input, pre-configured for panel use.

**Visual rules:** Same as `hui.input_field` — `dense outlined`, `w-full`.

```python
hui.number_field(label="posX", value=0)
```

### 8.18 `hui.select_field(options, value=None, label=None, **props)`

A standard dropdown select, pre-configured for panel use.

**Visual rules:**

- Props: `dense outlined`
- Classes: `text-sm`
- `min-width: 160px` by default (override via `min_width=`)
- `options` accepts a list (value == label) or a dict (value → label)

```python
hui.select_field(options=["A", "B"], value="A", label="Mode")
hui.select_field(options={"a": "Option A"}, value="a", label="Mode")
```

### 8.19 `hui.section_divider(text=None)`

A visual break between sections. If `text` is provided, renders a
`hui.section_label`. Otherwise renders a plain `ui.separator` with top margin.

```python
hui.section_divider("ADVANCED")  # labelled divider
hui.section_divider()            # plain separator
```

### 8.19b `hui.separator()`

A plain themed horizontal rule (`ui.separator`), coloured by `--hw-separator`. Use when you need a divider
without a label and without the top margin added by `hui.section_divider()`.
Prefer `hui.section_divider()` in most contexts; use `hui.separator()` only
where the extra margin would break a tight layout.

```python
hui.separator()
```

### 8.20 `hui.success_label(text)` / `hui.info_label(text)`

Status message labels for non-error states.

**Visual rules:**

- `success_label`: `text-sm` with `color: var(--hw-success)`, `p-4`
- `info_label`: `text-sm` with `color: var(--hw-info)`, `p-4`

```python
hui.success_label("Library installed successfully.")
hui.info_label("No changes detected.")
```

### 8.21 `hui.category_group(label)` — settings expansion header

A foldable expansion used to group settings fields by category inside a
`compact-fields` container. This is distinct from `hui.expansion_section`
(which is for property panel scopes with state persistence).

**Visual rules:**

- Props: `dense dense-toggle`
- Header class: `hw-section-label py-0 min-h-[24px]` — the section label of §3.4
- Default open: `True`
- No state persistence (categories always reset to open)

```python
with hui.category_group("Rendering"):
    # field rows rendered here
```

**Rule:** Use `hui.category_group` inside `compact-fields` columns only.
Use `hui.expansion_section` for collapsible panels in the properties editor.

### 8.22 Loading & Async States

**Spinner (content pending):** Use `ui.spinner(size="24px")` centred inside
the panel's scroll area. Apply `hw-text-dim` colour. No custom spinner variants.

**Skeleton rows:** Not a standard pattern — use the spinner instead. Keep it
simple.

**Button loading state:** Pass Quasar `:loading="True"` to any `QBtn` that
triggers an async action. Do not disable the button manually; `:loading`
handles both the spinner overlay and implicit `pointer-events: none`.

**Rule:** Never leave a panel blank while loading. Always show either the
spinner or `hui.empty_state()` with a loading hint as a fallback.

### 8.23 Popup / Dialog Chrome

Floating popups (context menus, connection info, node add menus) follow these
rules. There is no single `hui` wrapper for full popups — they vary too much
in structure — but the chrome rules are fixed.

**Visual rules:**

- Background: `var(--hw-bg-elevated)`
- Border: `1px solid var(--hw-border-strong)`
- Border radius: `md` (8px)
- Shadow: `var(--hw-popup-shadow)` — a workbench-flavoured theme token, distinct
  from `--hw-node-shadow` (nodes are canvas objects; popups are shell objects)
- Backdrop (modal overlays only): `var(--hw-bg-overlay)` — never `rgba(0,0,0,0.5)`

**Rule:** Never hardcode `box-shadow` values on popups. Use `--hw-popup-shadow`.

**Context menu items** are `hui.menu_row` / `hui.submenu_row` (§8.8b) — do not
build them out of `hui.button` or a hand-rolled row. Their look lives entirely in
the `.hw-menu-row` block and its `--hw-menu-row-*` tokens (§2.8a):

- Padding: `0.25rem 0.5rem`, `rounded` (4px), never wrapping
- Text / icon / hover: `--hw-menu-row-*`, falling back to `--hw-text-body`,
  `--hw-text-dim`, `--hw-bg-hover`
- Disabled: `opacity: 0.4; pointer-events: none`
- Keyboard shortcut suffix: `text-xs hw-text-dim ml-auto font-mono`, drawn by
  `hui.menu_row(..., command=Copy)` or, outside a menu row, `hui.key_hint(Copy)` /
  `hui.combo_hint("Mod+Shift+Z")` — never hand-rolled. The helpers draw the
  macOS (`⌘C`) and other (`Ctrl+C`) spellings and the shell CSS shows the one
  matching `html[data-hw-platform]`; a hand-written suffix shows one platform's
  spelling everywhere and drifts from the command's keys.
- Divider between groups: `hui.separator()`

### 8.24 `hui.dialog_card(width=None)`, `hui.dialog_actions(...)`, `hui.action_row()`, `hui.confirm_button(label)`

Two helpers that enforce §8.23 chrome rules on modal dialogs.

**`hui.dialog_card(width)`** — a context manager replacing `ui.card()` in the
NiceGUI dialog idiom. Applies elevated background, strong border, 8px radius,
and popup shadow via `--hw-*` tokens.

```python
with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
    ui.textarea(...).classes("w-full text-xs hw-text-body").props("dense autogrow")
    hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
```

**`hui.dialog_actions(on_confirm, on_cancel, *, confirm_label="OK", cancel_label="Cancel")`** —
a right-aligned action row. Cancel is flat/unstyled; the confirm button uses
`color: var(--hw-positive)` for affirming emphasis.

**`hui.action_row()`** — the right-aligned button row that ends any dialog,
popup or flow step, and **`hui.confirm_button(label, on_click=None)`** — the
`flat dense` button in `var(--hw-positive)` that carries out its intent.
`dialog_actions` is built from the two.

```python
with hui.action_row():
    ui.button("Close", on_click=popup.close).props("flat dense")
    hui.confirm_button("Apply", on_click=apply)
```

**Rule:** Never use raw `ui.card()` inside `ui.dialog()`. Always use
`hui.dialog_card()`.

**Rule:** Confirm button colour comes from `var(--hw-positive)` via
`.style()`, not from Quasar `color=positive` (which is not theme-mapped).

### 8.25 Field Focus Style (unified)

All editable fields — Quasar inputs/textareas and NumberDrag — share a unified
focus treatment enforced by shell CSS and the NumberDrag Vue component:

| State | Underline                                    | Background         |
| ----- | -------------------------------------------- | ------------------ |
| Rest  | `1px var(--hw-border)`                       | `--hw-bg-input`    |
| Hover | `1px var(--hw-border-strong)`                | `--hw-bg-input`    |
| Focus | `2px var(--hw-accent)`, center-out animation | `--hw-bg-elevated` |

The focus underline animates from the centre outwards using
`transform: scaleX(0→1)` with `cubic-bezier(0.4, 0, 0.2, 1)` — the
same easing Quasar uses on filled fields.

**Rule:** Use the 2D `scaleX`, never `scale3d`/`translateZ`/`translate3d`, on
anything that can appear once per widget, per pin or per node. A 3D transform
gives the element its own transform node in Blink's paint property tree and
blocks the paint-chunk merging `PaintArtifactCompositor::Update` ("Layerize")
depends on. This is not a micro-optimisation: 3300 of these pseudo-elements
(300 nodes × 11 number widgets) cost ~500 ms per Layerize while panning in
Chrome — 6 fps, 86% of the main thread, and a compositor too starved to raster
tiles, so cards drew half-finished and the app shell went unpainted. The 2D
form animates identically and measured 87 fps. Evidence and the harness that
produced it: `.scratch/pan-perf/`.

**Rule:** Do not add `outlined` or `filled` props to standard panel input
fields — the unified focus style is applied to the default (`standard`) Quasar
variant via shell CSS overrides. Using `outlined` or `filled` bypasses these
rules.

**Rule:** Do not add custom `border` or `box-shadow` to NumberDrag to indicate
focus. The `--editing` and `--dragging` CSS classes handle this consistently.

---

## 9. Layout Anatomy

### 9.1 Shell Structure

```
┌───────────────────────────────────────────────────────────────┐
│  TopBar  (48px)                 bg-surface, border-bottom     │
├──────┬──────┬─────────────────────────┬──────┬────────────────┤
│ Act. │ACTION│      EDIT Slot          │CNTXT │  Ctx.  │
│ Bar  │ Slot │  ┌───────────────────┐  │ Slot │  Bar   │
│      │ area │  │ MainTabBar (36px) │  │ area │        │
│ 48px │ 150+ │  ├───────────────────┤  │ 150+ │  48px  │
│      │  px  │  │                   │  │  px  │        │
│      │      │  │  Editor Content   │  │      │        │
│      │      │  │     (flex: 1)     │  │      │        │
│      │      │  │                   │  │      │        │
│      │      │  ├┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┤  │      │        │
│      │      │  │ BottomTabBar ▾    │  │      │        │ ← always-visible when INFO slot has tabs
│      │      │  ├───────────────────┤  │      │        │
│      │      │  │  INFO Slot area   │  │      │        │ ← collapsible via chevron or drag
│      │      │  │   (optional)      │  │      │        │
│      │      │  └───────────────────┘  │      │        │
├──────┴──────┴─────────────────────────┴──────┴────────────────┤
│  StatusBar  (24px)             statusbar-bg, border-top       │
└───────────────────────────────────────────────────────────────┘
```

Every slot = a **bar** (control strip) + an **area** (content panel). The ACTION
and CONTEXT slots (left and right edges) have vertical icon bars (ActivityBar /
ContextBar) classed with `hw-slot-bar hw-slot-bar-icons`; the EDIT and INFO slots
(centre and bottom) have horizontal tab bars (MainTabBar / BottomTabBar) classed
with `hw-slot-bar hw-slot-bar-tabs`. See §9.7 for the INFO-slot retraction rules.

### 9.2 Editor Container

Every editor is wrapped in a `.hw-panel` container by the shell. This container
provides the global text colour cascade and icon dim rules. Editors do not need
to set their own base text colour.

```python
# This is done by AppShell — editors receive `container` with these already applied
container_div = (
    ui.element("div")
    .classes("hw-panel")
    .style("width: 100%; height: 100%; background: var(--hw-bg-page);")
)
```

### 9.3 Standard Editor Template

Every editor should follow this vertical structure:

```python
def render(self, container, context):
    with container:
        with ui.column().classes("w-full h-full gap-0"):
            # 1. Header (flex-shrink-0)
            with hui.panel_header("My Editor", icon="tune"):
                hui.icon_action("refresh", on_click=self._refresh)

            # 2. Scrollable content (flex-1)
            with ui.scroll_area().classes("flex-1 w-full"):
                self._content = ui.column().classes("w-full p-2 gap-1")
                self._render_content(context)
```

### 9.4 Scrollbar Style

Quasar's `QScrollArea` renders a custom scrollbar. Style it via the
`thumb-style` and `bar-style` props — do not use `::-webkit-scrollbar` CSS.

```python
ui.scroll_area().props(
    'thumb-style="background: var(--hw-border-strong); border-radius: 4px; width: 4px;"'
    ' bar-style="background: transparent; width: 4px;"'
)
```

**Rule:** Scrollbars are 4px wide, use `--hw-border-strong` for the thumb, and
transparent for the track. This applies to all `ui.scroll_area()` instances.

### 9.5 Resizable Panel Handles

Left/right area panels are resizable. The drag handle is a thin strip between
the panel and the adjacent column.

**Visual rules:**

- Width: `4px`
- Background at rest: transparent
- Background on hover/drag: `var(--hw-accent)` at 50% opacity
- Cursor: `col-resize`
- Transition: `background 0.15s`

**Rule:** The handle must not have a visible border or shadow at rest. It
should only become visible when the user hovers over it.

### 9.6 Node Skin Design Space

Node skins (`BaseSkin` subclasses) render inside the graph canvas and operate
outside the `.hw-panel` cascade. They have a separate, more permissive set of
design rules.

**What skins may do:**

- Use any `--hw-node-*` and `--hw-canvas-*` token directly in inline styles
- Apply `--hw-danger-bg`, `--hw-ghost-pin`, and other canvas-specific tokens
- Use `box-shadow` via `var(--hw-node-shadow)` or an additional error-state
  shadow — canvas objects are the only place where multiple shadows are allowed
- Use `backdrop-filter` for frosted-glass node effects — via
  `var(--hw-node-backdrop-blur, none)`, never hardcoded, and only on a
  translucent card. It is the single most expensive thing a card can carry
  (measured 1.90x on zoomed-out pan across 200 nodes) and is invisible behind
  an opaque `node_bg`. See theme-canon
- Apply canvas-tier transition durations (`0.2s`–`0.3s`)

**Typography inside skins:**

Canvas text is outside the `.hw-panel` cascade. Use these rules explicitly:

| Purpose         | Classes / token                                |
| --------------- | ---------------------------------------------- |
| Node title      | `text-xs font-medium`, `--hw-node-header-text` |
| Port label      | `text-xs`, `--hw-text-muted`                   |
| Error / warning | `text-xs`, `--hw-danger` / `--hw-warning`      |
| Monospace value | `text-xs font-mono`, `--hw-text-body`          |

**Rule:** Do not use `text-sm` or larger inside node skins — canvas nodes
are visually small and larger text breaks the density contract.

**What skins must not do:**

- Hardcode `#hex` or `rgb()` values — all colours must be tokens
- Use `--hw-bg-*`, `--hw-text-*`, or `--hw-border` panel tokens directly
  (they belong to the shell layer)
- Use `text-gray-*`, `text-red-*`, or any Tailwind colour class — use tokens
  or Quasar `color=` props with `.hw-use-props-color`
- Apply `hui.*` panel wrappers inside a skin — use raw `ui.*` elements

**Error state skins** (e.g. `ErrorSkin`) may introduce a second visual identity
for the node (red gradient, danger border) provided all colour values reference
tokens (`--hw-danger`, `--hw-danger-bg`). Hardcoded hex values like `#ef4444`
or `#fef2f2` must be replaced.

### 9.7 Bottom Area Retraction

The bottom area mirrors the middle-area tab structure: its own tab bar row plus
a collapsible content panel. Retraction is governed by three rules so the
region always presents one consistent entry point to the user.

**Rule 1 — The tab bar is always visible when tabs exist.** When the bottom
registry contains at least one editor, the bottom tab bar row stays on screen
in both expanded and retracted states. Users never lose sight of which bottom
editors exist. If the registry has no bottom editors, the whole region (tab
bar and content) is hidden.

**Rule 2 — Retraction is chevron-only from a click path.** The rightmost
control in the bottom tab bar row is a single chevron button: `expand_less`
when expanded, `expand_more` when retracted. Clicking it toggles only the
content panel and the divider above it — not the tab bar row itself. There
must be no secondary close buttons or tab-level close affordances.

**Rule 3 — Drag auto-expands from retracted.** The horizontal drag divider
above the bottom tab bar is always hit-testable. Starting a drag while the
panel is retracted auto-expands it; releasing a drag below a small snap
threshold (~40px) retracts it again. Both paths flow through the same
visibility-sync helper as the chevron click so Python state and DOM state
never drift.

**Visual rules:**

- The horizontal drag divider above the bottom tab bar uses the same visual
  rules as §9.5 handles (`4px`, transparent at rest, `--hw-accent` 50% on
  hover/drag, `row-resize` cursor).
- The BottomTabBar shares the `hw-slot-bar-tabs` styling with the MainTabBar
  — same `36px` height, same active/hover behaviour, same label truncation
  rules.
- The chevron uses standard `hui.icon_action` sizing (`xs`) and flips its
  icon between `expand_less` and `expand_more`. It must not animate its
  rotation; the icon swap is the state signal.
- When retracted, the content panel's `display: none` — it does not
  contribute to flex layout — so the divider sits directly against the top
  edge of the tab bar row.

**Persistence:** Only the INFO slot snapshot's `visible`, `size`, and
`active_key` survive save/load cycles. The tab roster itself is re-derived from
the editor registry on every load so newly-installed INFO-slot editors appear
automatically without requiring users to reset their workspace.

---

## 10. Naming Conventions

### 10.1 Terminology

Every workspace slot (**left**, **right**, **main**, **bottom**) is composed of
a **bar** (its control strip) and an **area** (its content panel). The shell
also has two chrome bars (TopBar / StatusBar) and one editor-internal bar
(SurfaceToolbar). Use these names consistently in code and comments:

| Name           | Slot                      | Bar kind | Content                                      |
| -------------- | ------------------------- | -------- | --------------------------------------------- |
| TopBar         | —                         | chrome   | App name, workspace switcher, global actions  |
| StatusBar      | —                         | chrome   | Session info, status messages                |
| ActivityBar    | ACTION slot (left edge)   | icons    | ACTION slot editor switcher icons            |
| ContextBar     | CONTEXT slot (right edge) | icons    | CONTEXT slot editor switcher icons           |
| MainTabBar     | EDIT slot (centre)        | tabs     | EDIT slot tab switcher (horizontal tabs)     |
| BottomTabBar   | INFO slot (bottom)        | tabs     | INFO slot tab switcher + retract chevron     |
| SurfaceToolbar | (inside PropertiesEditor) | icons    | Surface switcher icons (36px buttons)        |

**Rule:** The ACTION slot (left edge) hosts activity-minded editors (library
browser, file browser, graph manager); the CONTEXT slot (right edge) hosts
context-minded editors that react to selection (properties, component detail).
ActivityBar and ContextBar are the bars of the ACTION and CONTEXT slots
respectively.

**Rule:** "Sidebar" in CSS tokens (`--hw-bg-sidebar`) refers to the narrow icon
bars (ActivityBar / ContextBar), not the ACTION/CONTEXT slot content areas.

### 10.2 CSS Class Naming

| Prefix              | Purpose                                              |
| ------------------- | ---------------------------------------------------- |
| `hw-`               | Haywire design system (tokens, global utilities)     |
| `hw-shell-`         | Shell-specific structural classes                    |
| `hw-text-`          | Semantic text colour utilities                       |
| `hw-panel`          | Editor container marker (enables text cascade)       |
| `hw-slot-bar`       | Base class applied to every slot bar (icons or tabs) |
| `hw-slot-bar-tabs`  | Tabbed slot bar modifier (MainTabBar, BottomTabBar)  |
| `hw-slot-bar-icons` | Icon slot bar modifier (ActivityBar, ContextBar)     |
| `hw-cm-isolate`     | CodeMirror isolation wrapper (see rule below)        |
| `hw-heading`, `hw-section-label`, `hw-subject`, `hw-hint` | Label roles (§3.6)  |
| `hw-indented`, `hw-box` | Indentation column and bordered group (§4.6)     |
| `compact-fields`    | Dense field rendering mode                           |
| `sf-label`          | Settings field label (responsive layout)             |
| `sf-widget`         | Settings field widget (responsive layout)            |

**Rule: `hw-cm-isolate`** must be applied to the direct wrapper `div` around
any CodeMirror editor instance. Without it, Quasar and Haywire global CSS rules
(particularly `--hw-text-body` colour cascade and `.hw-panel` font overrides)
bleed into CodeMirror's internal DOM and corrupt its syntax highlighting. The
class creates a CSS isolation boundary. Do not apply it to any element that is
not a CodeMirror host.

---

## 11. Accessibility (Minimum Requirements)

### 11.1 Keyboard Navigation

- All interactive elements must be focusable via Tab
- Focus rings: `outline: 2px solid var(--hw-accent); outline-offset: 2px`
- Use `:focus-visible`, not `:focus` — focus rings must not appear on mouse click
- Expansion panels are togglable via Enter/Space
- `hui.input_field` and Quasar form components handle focus rings automatically
  via global CSS; do not override them per-component

### 11.2 Contrast

- `--hw-text-body` on `--hw-bg-page` must meet WCAG AA (4.5:1 minimum)
- `--hw-text-muted` on `--hw-bg-page` must meet 3:1 minimum
- `--hw-text-dim` is decorative and exempt, but should aim for 2:1

### 11.3 Interactive Targets

- Minimum touch/click target: 36×36px (scope buttons are at this minimum)
- Toolbar buttons are 40×40px

---

## 12. Anti-Patterns (Do Not Do)

| Anti-pattern                                                      | Why it's wrong                                              | Correct approach                                                  |
| ----------------------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------- |
| `text-gray-400`, `text-gray-500`, `text-gray-600`                 | Not theme-aware                                             | `.hw-text-muted` or `.hw-text-dim`                                |
| `text-red-400` for errors                                         | Not theme-aware                                             | `hui.error_label()` or `color: var(--hw-danger)`                  |
| `text-yellow-400` for warnings                                    | Not theme-aware                                             | `hui.warning_label()` or `color: var(--hw-warning)`               |
| `text-blue-400` on links/icons                                    | Not theme-aware                                             | `color: var(--hw-accent)` or `var(--hw-info)`                     |
| `text-purple-500` on icons                                        | Not theme-aware                                             | Quasar `color=` prop with `.hw-use-props-color`                   |
| `text-amber-400` for unsaved/warning state                        | Not theme-aware                                             | `color: var(--hw-warning)`                                        |
| `hover:bg-white/10`                                               | Breaks on light themes                                      | `hui.list_item()` or class `hw-list-item-hover`                   |
| `bg-blue-900/40` for active rows                                  | Hardcoded, dark-only                                        | `hui.list_item(is_active=True)` → `var(--hw-bg-active)`           |
| `bg-green-500`, `bg-purple-500` as dots                           | Acceptable only via Quasar `bg-{color}-500` for status dots | Use Quasar named colours; document in `hui.list_item(dot_color=)` |
| Hardcoded `#hex` in `.style()`                                    | Not theme-aware                                             | Use `var(--hw-*)` token                                           |
| `rgba(0,0,0,0.5)` as modal backdrop                               | Dark-only                                                   | `var(--hw-bg-overlay)`                                            |
| `rgba(128,128,128,…)` for ghost pins                              | Not theme-aware                                             | `var(--hw-ghost-pin)`                                             |
| `#ef4444`, `#fef2f2` in error skins                               | Not theme-aware                                             | `var(--hw-danger)`, `var(--hw-danger-bg)`                         |
| `box-shadow` on panels                                            | Reserved for canvas nodes                                   | Use elevation colours                                             |
| `box-shadow` hardcoded on popups                                  | Not theme-aware                                             | Use `var(--hw-node-shadow)` or add `--hw-popup-shadow`            |
| `transition: all`                                                 | Transitions unspecified properties                          | Name the specific property                                        |
| `0.2s`/`0.3s` transitions in shell/panel code                     | Inconsistent with shell tier                                | `0.15s` for shell; `0.2–0.3s` only in canvas/skin code            |
| `color=grey` on icon buttons                                      | Overrides theme cascade                                     | Remove; buttons inherit colour from `.hw-panel`                   |
| `color=positive` on buttons                                       | Not theme-mapped — uses Quasar hardcoded green              | Use `.style("color: var(--hw-positive)")`                         |
| `color=primary` on buttons                                        | Not mapped to Haywire theme                                 | Style via `--hw-accent`                                           |
| `ui.card()` inside `ui.dialog()`                                  | Missing themed chrome (bg, border, shadow)                  | Use `hui.dialog_card()`                                           |
| `ui.expansion()` directly in settings panels                      | Inconsistent header styling                                 | Use `hui.category_group()`                                        |
| `ui.input()` / `ui.number()` with `dense outlined`                | Duplicates hui config                                       | Use `hui.input_field()` / `hui.number_field()`                    |
| Re-implementing panel_header from scratch                         | Drift and inconsistency                                     | Use `hui.panel_header()`                                          |
| `min-height: 28px` vs `min-height: 32px` for similar bars         | Inconsistent                                                | Use `hui.info_bar()` (standardizes to 28px)                       |
| Inline `padding: 80px 0` vs `padding: 60px 0` for empty states    | Inconsistent                                                | Use `hui.empty_state()` (standardizes to 72px)                    |
| `--hw-node-*` tokens used in panel/shell code                     | Wrong layer                                                 | Canvas tokens are for skins only; use `--hw-bg-*` in panels       |
| `from haywire.ui import elements as hui` inside a method/function | Repeated import cost, inconsistent with codebase convention | Import once at module level                                       |
| Raw Material icon string (`icon="refresh"`)                       | No semantic registry, drifts from `AppIcon`                 | `hui.icon.<name>`                                                 |
| `.truncate` on a `ui.button` label                                | Class can't reach Quasar's inner `<span>`                   | `no-wrap` Quasar prop (`hui.button` already applies it)           |
| `ui.label(...).classes("text-base font-bold")` in a dialog or flow | A heading style per author                                  | `hui.heading()` (§3.6)                                            |
| Hand-written `uppercase tracking-wide` labels                     | Drifts from `hui.section_label`                             | `hui.section_label()` (§3.4)                                      |
| A flow panel repeating its popup or step title                    | Two headings of one tier                                    | The stepper draws the step title; the panel draws none            |
| `ml-1` / `ml-2` / `pl-*` columns under a label                    | Mixed indents, misaligned with the label                    | `hui.indented()` (§4.6)                                           |
| `ui.row().classes("w-full justify-end gap-2")` + positive button  | Copied in every flow                                        | `hui.action_row()` + `hui.confirm_button()`                       |
