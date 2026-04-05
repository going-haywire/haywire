# Haywire Design System

A prescriptive design reference for developers building editors, panels, and
components in the Haywire workbench. This document defines the rules — not just
what exists today, but what every new (and eventually every existing) piece of
UI should follow.

Where the `hui` module is referenced, it means `haywire.ui.elements` — the
thin wrapper library that encodes these rules into reusable Python functions.
Prefer `hui.*` over raw NiceGUI/Quasar calls for any pattern that appears here.

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

| Token                | Tier | Use for                                       |
| -------------------- | ---- | --------------------------------------------- |
| `--hw-text-body`     | 1    | Primary content. Headings, labels, body copy.  |
| `--hw-text-muted`    | 2    | Supporting text. Descriptions, tab labels.      |
| `--hw-text-dim`      | 3    | Decorative text. Placeholders, captions, icons. |
| `--hw-text-expansion`| —    | Expansion panel header labels (special-purpose).|
| `--hw-text-on-accent`| —    | Text rendered on accent-coloured backgrounds.   |

**Utility classes:** `.hw-text-body`, `.hw-text-muted`, `.hw-text-dim` are
globally available inside `.hw-panel` containers.

**Rule:** Never use Tailwind's `text-gray-*` classes for UI text. They are
theme-unaware and will break on non-dark themes.

### 2.4 Border Tokens

| Token               | Use for                                         |
| -------------------- | ----------------------------------------------- |
| `--hw-border`        | Subtle structural dividers. Felt, not seen.      |
| `--hw-border-strong` | Visible separators. Section breaks, panel edges. |

**Rule:** Every `border-b`, `border-r`, `border-l`, `border-t` in the shell
and editor UI must use `var(--hw-border)` via inline style or an appropriate
`hui` wrapper. Never use Tailwind border-colour utilities.

### 2.5 Accent & Interactive Tokens

| Token               | State                              |
| -------------------- | ---------------------------------- |
| `--hw-accent`        | Rest. Focus rings, active markers. |
| `--hw-accent-hover`  | Hover.                             |
| `--hw-accent-active` | Pressed / active.                  |

### 2.6 Status Tokens

| Token          | Semantic                                 |
| -------------- | ---------------------------------------- |
| `--hw-danger`  | Error, destructive, failure.             |
| `--hw-warning` | Caution, attention.                      |
| `--hw-success` | Confirmation, positive.                  |
| `--hw-info`    | Informational, neutral attention.        |

**Rule:** Error text uses `var(--hw-danger)`, not `text-red-400`. Warning text
uses `var(--hw-warning)`, not `text-yellow-400`. This applies everywhere —
inline messages, error labels, validation hints.

### 2.7 Canvas & Node Tokens

These tokens are defined on `WorkbenchTheme` and used exclusively by the graph
canvas, node skins, and edge renderers. Panel and shell code must not reference
them.

| Token                   | Use for                                                        |
| ----------------------- | -------------------------------------------------------------- |
| `--hw-node-bg`          | Default node card background                                   |
| `--hw-node-border`      | Default node card border                                       |
| `--hw-node-header-bg`   | Node header strip background                                   |
| `--hw-node-header-text` | Node header text colour                                        |
| `--hw-node-selected`    | Node border/glow when selected                                 |
| `--hw-node-shadow`      | Node card drop shadow (only permitted `box-shadow` in the app) |
| `--hw-edge-default`     | Default edge stroke colour                                     |
| `--hw-edge-selected`    | Selected edge stroke colour                                    |
| `--hw-canvas-bg`        | Canvas background fill                                         |
| `--hw-canvas-grid`      | Canvas grid dot/line colour                                    |
| `--hw-ghost-pin`        | Ghost/unconnected pin indicator colour (rgba, low opacity)     |
| `--hw-danger-bg`        | Error node background fill (used by error skin)                |

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
| `--hw-popup-shadow`        | Drop shadow for floating popups and menus   |

### 2.9 Z-Index Scale

Haywire uses a fixed z-index scale. Do not use arbitrary values.

| Layer              | Value | Use for                                           |
| ------------------ | ----- | ------------------------------------------------- |
| `--hw-z-panel`     | 10    | Floating panels, resizable handles                |
| `--hw-z-dropdown`  | 100   | Dropdown menus, autocomplete popups               |
| `--hw-z-tooltip`   | 200   | Tooltips                                          |
| `--hw-z-modal`     | 300   | Modal dialogs and their backdrops                 |
| `--hw-z-notify`    | 400   | Toast notifications (above everything)            |

**Rule:** Never use a bare `z-index: 9999` or arbitrary integer. If a new stacking context is needed, add a token here.

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

| Element              | Style                               |
| -------------------- | ----------------------------------- |
| Input, select        | `opacity: 0.5; pointer-events: none`|
| Icon action button   | `opacity: 0.4; pointer-events: none`|
| Scope button         | `opacity: 0.3; pointer-events: none`|

**Rule:** Always set both `opacity` and `pointer-events: none` together.
Never use a grey fill or border change to indicate disabled state — opacity
is the single, consistent signal.

**Rule:** Quasar's `:disable` prop handles both correctly for `QBtn` and
`QInput`. Prefer it over manual class application where available.

### 2.12 Drag-and-Drop Tokens

These tokens are used when items are dragged within or between panels.

| Token              | Use for                                    |
| ------------------ | ------------------------------------------ |
| `--hw-drag-over`   | Drop-target highlight (border or bg tint)  |
| `--hw-drag-ghost`  | Dragged item ghost opacity (typically 0.5) |

**Rule:** Drag-over state is indicated by a `2px solid var(--hw-drag-over)`
border, not a background fill. The border is added/removed via a CSS class
(e.g. `hw-drop-target`) toggled in JS drag event handlers.

---

## 3. Typography

### 3.1 Type Scale

Haywire uses four deliberately chosen size tiers. The system font stack is
inherited from Quasar (Roboto / system sans-serif).

| Tier     | Tailwind class   | Line-height | Use for                               |
| -------- | ---------------- | ----------- | ------------------------------------- |
| Display  | `text-2xl`       | default     | Library name in detail view. Rare.    |
| Heading  | `text-base`      | default     | Component label, panel title.         |
| Body     | `text-sm`        | default     | Descriptions, list items, body copy.  |
| Caption  | `text-xs`        | default     | Metadata, versions, registry keys.    |

**Rule:** `text-lg` is not a design tier. It is only used for the application
wordmark ("Haywire" in the topbar). Do not use it elsewhere.

**Rule:** `text-2xl` is only for the library detail display title. Do not use
it elsewhere.

### 3.2 Weight

| Weight              | Tailwind class  | Use for                                    |
| ------------------- | --------------- | ------------------------------------------ |
| Regular (400)       | (default)       | Body text, descriptions                    |
| Medium (500)        | `font-medium`   | List item names, panel header labels       |
| Bold (700)          | `font-bold`     | Headings, section group labels, emphasis   |

### 3.3 Monospace

Use `.font-mono` for: file paths, registry keys, code snippets, module paths,
import statements, and any machine-readable identifier.

Always pair `.font-mono` with `.text-xs` — monospace text at `text-sm` feels
too large relative to proportional text at the same size.

### 3.4 Tracking Labels

Section group headers (REQUIRED, ENABLED, IDENTIFIERS, etc.) follow a fixed
formula:

```
.text-xs .font-bold .tracking-wider .uppercase .hw-text-dim
```

These labels are structural markers, not content — they should be the dimmest
text in the panel.

### 3.5 Truncation

**Rule:** Any text that can overflow its container must include `.truncate`.
The parent flex container must include `.min-w-0` to allow truncation to work
inside flex layouts.

For values that are programmatically too long, truncate in Python and provide
the full value via `.tooltip()`:

```python
short = (value[:48] + "…") if len(value) > 50 else value
hui.info_row("Module", short, copy_value=full_value)
```

---

## 4. Spacing System

### 4.1 The Scale

Haywire uses a constrained subset of Tailwind's spacing scale. Using values
outside this set requires justification.

| Token  | Value | Name       | Primary use                              |
| ------ | ----- | ---------- | ---------------------------------------- |
| `0`    | 0px   | None       | Between tightly coupled elements         |
| `0.5`  | 2px   | Hairline   | Between toggle buttons, icon groups      |
| `1`    | 4px   | Tight      | Between port rows, compact field stacks  |
| `1.5`  | 6px   | Snug       | Vertical padding on list items           |
| `2`    | 8px   | Base       | Section padding, search bar, icon+label  |
| `3`    | 12px  | Loose      | Between major sections, topbar padding   |
| `4`    | 16px  | Spacious   | Content area padding (docs, detail)      |
| `6`    | 24px  | Page       | Page-level padding (library detail)      |

### 4.2 Panel Padding Rules

| Panel region            | Horizontal | Vertical  |
| ----------------------- | ---------- | --------- |
| Panel header            | `px-2`     | `py-1.5`  |
| Info bar                | `px-3`     | `py-1`    |
| List item               | `px-2`     | `py-1.5`  |
| Section group label     | `px-2`     | `pt-2 pb-1` |
| Content area (scroll)   | `p-4`      | —         |
| Detail page content     | `px-6 pt-6`| —         |

### 4.3 Gap Rules

| Context                       | Gap    |
| ----------------------------- | ------ |
| Column of list items          | `gap-0`|
| Compact field stack           | `gap-1`|
| Icon + label in a row         | `gap-2`|
| Sections within a panel       | `gap-3`|
| Empty state icon + message    | `gap-3`|

### 4.4 Height Fixtures

Certain UI elements have fixed heights. These are not negotiable — they ensure
the shell geometry is predictable.

| Element              | Height  | Set via                    |
| -------------------- | ------- | -------------------------- |
| TopBar               | 48px    | inline style               |
| StatusBar            | 24px    | inline style               |
| ActivityBar width    | 48px    | inline style               |
| ContextBar width     | 48px    | inline style               |
| Middle tab bar       | 36px    | `min-height` inline style  |
| Scope toolbar button | 36×36px | inline style               |
| Compact field input  | 26px    | `--hw-compact-field-h`     |

### 4.5 Compact-Fields System

Settings panels use a container-query–based responsive layout system that
compresses label/widget rows for dense display. This is distinct from ordinary
`gap-1` padding — it activates a CSS container context and responsive classes.

**How to use:**

```python
with ui.column().classes("w-full gap-0 compact-fields").style(
    "container-type: inline-size; container-name: settings-panel;"
):
    # Each row uses _ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
    with ui.row().classes("w-full items-center justify-between gap-0 px-2"):
        ui.label("My Field").classes("text-xs truncate sf-label")
        my_widget.classes("sf-widget")
```

**CSS classes in this system:**

| Class            | Purpose                                                         |
| ---------------- | --------------------------------------------------------------- |
| `compact-fields` | Applied to the outer column. Activates container context.       |
| `sf-label`       | Label cell. Responsive width — shrinks at narrow container.     |
| `sf-widget`      | Widget cell. Takes remaining space; right-aligned.              |

**CSS tokens for this system:**

| Token                   | Default | Purpose                                 |
| ----------------------- | ------- | --------------------------------------- |
| `--hw-compact-field-h`  | 26px    | Fixed input height for compact widgets. |
| `--hw-compact-gap`      | 1px     | Vertical gap between compact rows.      |
| `--hw-compact-row-min-h`| 28px    | Minimum row height in compact mode.     |

**Rule:** Only use `compact-fields` for settings/property panels. Regular
editor content uses the standard gap/padding system (§4.1–4.3).

**Rule:** Never apply `compact-fields` and `p-4` to the same container. Compact
panels use `p-0` or `p-1` on their outer column.

---

## 5. Border Radius

### 5.1 The Scale

| Token    | Value | Use for                                    |
| -------- | ----- | ------------------------------------------ |
| `none`   | 0     | Scope toolbar buttons, tab indicators      |
| `sm`     | 4px   | Inputs, list items, code blocks, badges    |
| `md`     | 8px   | Cards, dialogs, expansion panels           |
| `lg`     | 10px  | Toolbar icon buttons                       |
| `full`   | 9999  | Status dots, circular icon buttons         |

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

| Context               | Size      | Implementation            |
| --------------------- | --------- | ------------------------- |
| Toolbar button        | 24px      | Quasar default (no prop)  |
| Panel header inline   | 16px      | `size="16px"`             |
| Info bar inline       | 14px      | `size="14px"`             |
| Empty state           | 36–48px   | `size="40px"` typical     |
| Inline text indicator | 10–14px   | `size="10px"` / `"14px"`  |

### 6.3 Colour Rules

| Context                  | Colour                                |
| ------------------------ | ------------------------------------- |
| Decorative / structural  | `.hw-text-dim`                        |
| Interactive (rest)       | Inherited (`--hw-text-muted`)         |
| Interactive (hover)      | Inherited (`--hw-text-body`)          |
| Interactive (active)     | Inherited (`--hw-accent`)             |
| Quasar `color=` prop     | Add `.hw-use-props-color` to opt out of the global dim override |

**Rule:** Never use `text-purple-500`, `text-blue-400`, or any Tailwind colour
class on an icon. If an icon needs a semantic colour, use Quasar's `color=`
prop with `.hw-use-props-color`, or style it with a `--hw-*` token.

### 6.4 Standard Icon Vocabulary

| Concept         | Icon            | Concept         | Icon              |
| --------------- | --------------- | --------------- | ----------------- |
| Files           | `folder`        | Libraries       | `widgets`         |
| Graph / nodes   | `account_tree`  | Settings        | `tune`            |
| Code / source   | `code`          | Documentation   | `description`     |
| Refresh         | `refresh`       | Close           | `close`           |
| Save            | `save`          | Search          | `search`          |
| Error           | `error`         | Warning         | `warning`         |
| Copy            | `content_copy`  | Types           | `category`        |
| Adapters        | `swap_horiz`    | Skins           | `brush`           |
| Themes          | `palette`       | Panels          | `view_sidebar`    |
| Editors         | `tab`           | Expand/collapse | `expand_more/less`|

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

### 8.5 `hui.section_label(text)`

An uppercase tracking label that separates groups within a list or panel.

**Visual rules:**
- Text: `text-xs font-bold tracking-wider uppercase hw-text-dim`
- Padding: `px-2 pt-2 pb-1`

```python
hui.section_label("REQUIRED")
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

### 8.7 `hui.code_block(code, label=None, copyable=True)`

A read-only code snippet with optional label and copy button.

**Visual rules:**
- Outer column: `w-full gap-0.5 py-1`
- Label (optional): `text-xs hw-text-dim`
- Code container: `var(--hw-bg-surface)` background, `rounded` (4px), `px-2 py-1`,
  `1px solid var(--hw-border)`
- Code text: `text-xs font-mono hw-text-body`
- Copy button inline

```python
hui.code_block(
    "from haybale_visiongraph import WebcamFrameEventNode",
    label="Import",
)
```

### 8.8 `hui.icon_action(icon, tooltip=None, on_click=None, size="xs")`

A minimal icon-only button for inline actions.

**Visual rules:**
- Props: `flat round dense size={size}`
- Colour: inherited (theme-aware), no Quasar `color=` prop
- Tooltip applied if provided

```python
hui.icon_action("refresh", tooltip="Refresh tree", on_click=self._refresh)
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

### 8.10 `hui.scope_button(icon, is_active=False, available=True, tooltip=None, on_click=None)`

A square button for the properties scope toolbar.

**Visual rules:**
- Size: `36×36px`
- Border-radius: `0`
- Active: `var(--hw-accent)` background, `#ffffff` text
- Unavailable: `opacity: 0.3`, `pointer-events: none`
- Transition: `background 0.15s`

```python
hui.scope_button("settings", is_active=True, tooltip="Node Properties")
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

### 8.15 `hui.input_field(label=None, **props)`

A standard text input, pre-configured for panel use.

**Visual rules:**
- Props: `dense outlined`
- Classes: `w-full`
- Background: `var(--hw-bg-input)` (automatic via global CSS)
- Border: `var(--hw-border)` rest, `var(--hw-border-strong)` hover/focus
- Focus ring: `2px solid var(--hw-accent)` via `:focus-visible` — keyboard-only,
  not shown on mouse click (use `:focus-visible`, not `:focus`)
- Disabled: pass Quasar `:disable="True"` — renders `opacity: 0.5` automatically
- Validation error: pass Quasar `:rules=` and `lazy-rules="ondemand"` — error
  text appears below the field using `var(--hw-danger)`; never use a separate
  `hui.error_label()` to annotate a field inline

```python
hui.input_field(placeholder="Search libraries…", clearable=True)
hui.input_field(label="Port", rules=[lambda v: v.isdigit() or "Must be a number"])
```

### 8.16 `hui.tabs(*tab_defs, dense=True)`

A tab bar, pre-configured with `hw-tabs` styling.

**Visual rules:**
- Classes: `w-full hw-tabs`
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

```python
hui.select_field(options=["A", "B"], value="A", label="Mode")
```

### 8.19 `hui.section_divider(text=None)`

A visual break between sections. If `text` is provided, renders a
`hui.section_label`. Otherwise renders a plain `ui.separator` with top margin.

```python
hui.section_divider("ADVANCED")  # labelled divider
hui.section_divider()            # plain separator
```

### 8.19b `hui.separator()`

A plain themed horizontal rule (`ui.separator`). Use when you need a divider
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
- Header class: `text-xs font-bold hw-text-muted uppercase tracking-wide px-2 py-0 min-h-[24px]`
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
- Shadow: `var(--hw-popup-shadow)` — defined on `WorkbenchTheme`, distinct from
  `--hw-node-shadow` (nodes are canvas objects; popups are shell objects)
- Backdrop (modal overlays only): `var(--hw-bg-overlay)` — never `rgba(0,0,0,0.5)`

**Rule:** Never hardcode `box-shadow` values on popups. Use `--hw-popup-shadow`.

**Context menu items** follow the same rules as `hui.list_item` rows:

- Padding: `px-2 py-1.5`
- Hover: `var(--hw-bg-hover)`
- Disabled: `opacity: 0.4; pointer-events: none`
- Keyboard shortcut suffix: `text-xs hw-text-dim ml-auto font-mono`
- Divider between groups: `hui.separator()`
- Leading icon (optional): 16px, `hw-text-dim`

---

## 9. Layout Anatomy

### 9.1 Shell Structure

```
┌───────────────────────────────────────────────────────────────┐
│  TopBar  (48px)                 bg-surface, border-bottom     │
├──────┬──────┬─────────────────────────┬──────┬────────────────┤
│ Act. │ Left │      Middle Area        │Right │  Ctx.  │
│ Bar  │ Area │  ┌───────────────────┐  │ Area │  Bar   │
│      │      │  │  Tab Bar (36px)   │  │      │        │
│ 48px │ 150+ │  ├───────────────────┤  │ 150+ │  48px  │
│      │  px  │  │                   │  │  px  │        │
│      │      │  │  Editor Content   │  │      │        │
│      │      │  │     (flex: 1)     │  │      │        │
│      │      │  │                   │  │      │        │
│      │      │  ├───────────────────┤  │      │        │
│      │      │  │ Bottom (optional) │  │      │        │
│      │      │  └───────────────────┘  │      │        │
├──────┴──────┴─────────────────────────┴──────┴────────────────┤
│  StatusBar  (24px)             statusbar-bg, border-top       │
└───────────────────────────────────────────────────────────────┘
```

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
- Use `backdrop-filter` for frosted-glass node effects (use sparingly)
- Apply canvas-tier transition durations (`0.2s`–`0.3s`)

**Typography inside skins:**

Canvas text is outside the `.hw-panel` cascade. Use these rules explicitly:

| Purpose         | Classes / token                                  |
| --------------- | ------------------------------------------------ |
| Node title      | `text-xs font-medium`, `--hw-node-header-text`   |
| Port label      | `text-xs`, `--hw-text-muted`                     |
| Error / warning | `text-xs`, `--hw-danger` / `--hw-warning`        |
| Monospace value | `text-xs font-mono`, `--hw-text-body`            |

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

---

## 10. Naming Conventions

### 10.1 Terminology

The shell has five distinct toolbar/bar concepts. Use these names consistently
in code and comments:

| Name             | Location              | Content                    |
| ---------------- | --------------------- | -------------------------- |
| TopBar           | Top edge              | App name, workspace switcher, global actions |
| StatusBar        | Bottom edge           | Session info, status messages |
| ActivityBar      | Left narrow strip     | Left-area editor switcher icons |
| ContextBar       | Right narrow strip    | Right-area editor switcher icons |
| ScopeToolbar     | Inside PropertiesEditor | Scope switcher icons (36px buttons) |

**Rule:** "Sidebar" in CSS tokens (`--hw-bg-sidebar`) refers to the narrow bars
(ActivityBar / ContextBar), not the left/right panel areas.

### 10.2 CSS Class Naming

| Prefix          | Purpose                                          |
| --------------- | ------------------------------------------------ |
| `hw-`           | Haywire design system (tokens, global utilities) |
| `hw-shell-`     | Shell-specific structural classes                |
| `hw-text-`      | Semantic text colour utilities                   |
| `hw-panel`      | Editor container marker (enables text cascade)   |
| `hw-tabs`       | Middle-area tab bar styling                      |
| `hw-cm-isolate` | CodeMirror isolation wrapper (see rule below)    |
| `compact-fields`| Dense field rendering mode                       |
| `sf-label`      | Settings field label (responsive layout)         |
| `sf-widget`     | Settings field widget (responsive layout)        |

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

| Anti-pattern | Why it's wrong | Correct approach |
|---|---|---|
| `text-gray-400`, `text-gray-500`, `text-gray-600` | Not theme-aware | `.hw-text-muted` or `.hw-text-dim` |
| `text-red-400` for errors | Not theme-aware | `hui.error_label()` or `color: var(--hw-danger)` |
| `text-yellow-400` for warnings | Not theme-aware | `hui.warning_label()` or `color: var(--hw-warning)` |
| `text-blue-400` on links/icons | Not theme-aware | `color: var(--hw-accent)` or `var(--hw-info)` |
| `text-purple-500` on icons | Not theme-aware | Quasar `color=` prop with `.hw-use-props-color` |
| `text-amber-400` for unsaved/warning state | Not theme-aware | `color: var(--hw-warning)` |
| `hover:bg-white/10` | Breaks on light themes | `hui.list_item()` or class `hw-list-item-hover` |
| `bg-blue-900/40` for active rows | Hardcoded, dark-only | `hui.list_item(is_active=True)` → `var(--hw-bg-active)` |
| `bg-green-500`, `bg-purple-500` as dots | Acceptable only via Quasar `bg-{color}-500` for status dots | Use Quasar named colours; document in `hui.list_item(dot_color=)` |
| Hardcoded `#hex` in `.style()` | Not theme-aware | Use `var(--hw-*)` token |
| `rgba(0,0,0,0.5)` as modal backdrop | Dark-only | `var(--hw-bg-overlay)` |
| `rgba(128,128,128,…)` for ghost pins | Not theme-aware | `var(--hw-ghost-pin)` |
| `#ef4444`, `#fef2f2` in error skins | Not theme-aware | `var(--hw-danger)`, `var(--hw-danger-bg)` |
| `box-shadow` on panels | Reserved for canvas nodes | Use elevation colours |
| `box-shadow` hardcoded on popups | Not theme-aware | Use `var(--hw-node-shadow)` or add `--hw-popup-shadow` |
| `transition: all` | Transitions unspecified properties | Name the specific property |
| `0.2s`/`0.3s` transitions in shell/panel code | Inconsistent with shell tier | `0.15s` for shell; `0.2–0.3s` only in canvas/skin code |
| `color=grey` on icon buttons | Overrides theme cascade | Remove; buttons inherit colour from `.hw-panel` |
| `color=primary` on buttons | Not mapped to Haywire theme | Use `color=positive` or style via `--hw-accent` |
| `ui.expansion()` directly in settings panels | Inconsistent header styling | Use `hui.category_group()` |
| `ui.input()` / `ui.number()` with `dense outlined` | Duplicates hui config | Use `hui.input_field()` / `hui.number_field()` |
| Re-implementing panel_header from scratch | Drift and inconsistency | Use `hui.panel_header()` |
| `min-height: 28px` vs `min-height: 32px` for similar bars | Inconsistent | Use `hui.info_bar()` (standardizes to 28px) |
| Inline `padding: 80px 0` vs `padding: 60px 0` for empty states | Inconsistent | Use `hui.empty_state()` (standardizes to 72px) |
| `--hw-node-*` tokens used in panel/shell code | Wrong layer | Canvas tokens are for skins only; use `--hw-bg-*` in panels |
