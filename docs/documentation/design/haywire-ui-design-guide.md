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

| Token               | Layer | Use for                                    |
| -------------------- | ----- | ------------------------------------------ |
| `--hw-bg-page`       | 0     | Area containers, editor backgrounds        |
| `--hw-bg-surface`    | 1     | Topbar, info bars, panel header backgrounds|
| `--hw-bg-sidebar`    | 0–1   | Activity bar, context bar                  |
| `--hw-bg-elevated`   | 2     | Dropdown menus, tooltips, toolbar hover    |
| `--hw-bg-overlay`    | 3     | Modal backdrops                            |
| `--hw-bg-input`      | —     | Input field backgrounds (special-purpose)  |

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

### 2.7 Hover and Selection

Interactive list items and rows use a **theme-derived translucent overlay** for
hover, not a hardcoded white-alpha value.

**Prescribed value:** `var(--hw-bg-elevated)` as background on hover, or if
that is too heavy, a dedicated token `--hw-bg-hover` should be added. Until
that token exists, use `var(--hw-bg-surface)` for hover on Layer 0 containers,
and `var(--hw-bg-elevated)` for hover on Layer 1 containers.

**Rationale:** `hover:bg-white/10` only works on dark themes. On a light theme
it creates a washed-out flash.

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

### 7.1 Standard Transition

All interactive state changes use a single timing function:

```
transition: <property> 0.15s ease;
```

### 7.2 Animated Properties

Only these properties may be transitioned:

| Property           | Context                                      |
| ------------------ | -------------------------------------------- |
| `background-color` | Toolbar buttons, list item hover, dividers   |
| `color`            | Icon and text colour on hover                |
| `box-shadow`       | Active toolbar button ring                   |
| `opacity`          | Disabled / available scope buttons           |
| `border-color`     | Input focus                                  |

### 7.3 Not Animated

Layout changes (panel show/hide, content rebuilds, scroll) are instant. No
`transition` on `width`, `height`, `flex`, `padding`, `margin`, `transform`,
or `display`.

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

### 8.4 `hui.list_item(label, sublabel=None, dot_color=None, on_click=None)`

An interactive row for browsers and selection lists.

**Visual rules:**
- Padding: `px-2 py-1.5`
- Full width, `rounded` (4px)
- Hover: `var(--hw-bg-surface)` background (not `bg-white/10`)
- Cursor: `pointer`
- Gap: `gap-2`
- Status dot (optional): `w-2 h-2 rounded-full`, Quasar named colour
- Label: `text-sm font-medium truncate`
- Sublabel: `text-xs hw-text-dim`
- Parent text column: `flex-1 gap-0 min-w-0`

```python
hui.list_item(
    "Visiongraph",
    sublabel="v0.0.1",
    dot_color="green",
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
- Header text: `--hw-text-expansion`
- Persists expansion state to `context.metadata` under the given `panel_key`

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
- Border: `var(--hw-border)` rest, `var(--hw-border-strong)` hover

```python
hui.input_field(placeholder="Search libraries…", clearable=True)
```

### 8.16 `hui.tabs(*tab_defs, dense=True)`

A tab bar, pre-configured with `hw-tabs` styling.

**Visual rules:**
- Classes: `w-full hw-tabs`
- Props: `dense no-caps`
- Tab label font: 12px
- Active indicator: `var(--hw-accent)`

```python
with hui.tabs(("Graph", "account_tree"), ("Library", "widgets")) as tabs:
    ...
```

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
| `hw-cm-isolate` | CodeMirror isolation wrapper                     |
| `compact-fields`| Dense field rendering mode                       |
| `sf-label`      | Settings field label (responsive layout)         |
| `sf-widget`     | Settings field widget (responsive layout)        |

---

## 11. Accessibility (Minimum Requirements)

### 11.1 Keyboard Navigation

- All interactive elements must be focusable via Tab
- Focus rings use `var(--hw-accent)` with `2px` outline offset
- Expansion panels are togglable via Enter/Space

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
| `hover:bg-white/10` | Breaks on light themes | `hui.list_item()` or `var(--hw-bg-surface)` hover |
| `bg-green-500`, `bg-purple-500` as dots | Acceptable only via Quasar `bg-{color}-500` for status dots | Keep, but document in hui |
| Hardcoded `#hex` in `.style()` | Not theme-aware | Use `var(--hw-*)` token |
| `box-shadow` on panels | Reserved for canvas nodes | Use elevation colours |
| Re-implementing panel_header from scratch | Drift and inconsistency | Use `hui.panel_header()` |
| `min-height: 28px` vs `min-height: 32px` for similar bars | Inconsistent | Use `hui.info_bar()` (standardizes to 28px) |
| Inline `padding: 80px 0` vs `padding: 60px 0` for empty states | Inconsistent | Use `hui.empty_state()` (standardizes to 72px) |
