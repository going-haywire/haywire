# Haywire Design System — Migration Guide

Instructions for systematically migrating the Haywire codebase to the design
system defined in `docs/documentation/design/haywire-ui-design-guide.md` and
the `hui` module (`haywire.ui.elements`).

This document is written for a coding agent.  Work through it top-down.
Each section describes a class of violations, how to detect them, and how to
fix them.  Fixes are ordered from highest-impact (global search-replace) to
lowest-impact (structural refactors).

---

## Prerequisites

1. The `hui` module is available at `haywire.ui.elements`.
2. The global CSS additions from `hui._ensure_css()` are being injected
   (this happens automatically on first use of any `hui` function).
3. All editors are inside `.hw-panel` containers (the shell already does this).

---

## Phase 1 — Hardcoded Colour Purge

These are the highest-priority fixes.  Every one of these is a theme-breaking
bug on non-dark themes.

### 1.1  Tailwind grey text classes

**Detect:** Search all `.py` files under
`barn/haybale-studio/haybale_studio/editors/`,
`barn/haybale-studio/haybale_studio/panels/`,
`barn/haybale-core/haybale_core/`,
`packages/haywire-core/src/haywire/ui/`,
and any file that imports from `nicegui` for these patterns:

```
text-gray-300
text-gray-400
text-gray-500
text-gray-600
```

**Fix:** Replace according to this mapping:

| Found                    | Replace with       | Notes                        |
| ------------------------ | ------------------ | ---------------------------- |
| `text-gray-300`          | `hw-text-muted`    | e.g. statusbar session label |
| `text-gray-400`          | `hw-text-muted`    |                              |
| `text-gray-500`          | `hw-text-muted`    | e.g. "No editor" placeholder |
| `text-gray-600`          | `hw-text-dim`      | e.g. fallback menu icon      |

**Example transform:**
```python
# Before
ui.label(f"Session: {sid}").classes("text-xs text-gray-300")

# After
ui.label(f"Session: {sid}").classes("text-xs hw-text-muted")
```

### 1.2  Hardcoded red for errors

**Detect:** Search for:
```
text-red-400
text-red-500
color: red
color: #ff
```

Pay attention to context — these appear in error messages, "file not found"
labels, and validation feedback.

**Fix:** Replace with `hui.error_label()` where the element is a standalone
error message.  Where the red class is part of a larger element, replace the
class with `hw-text-danger`.

**Example transform:**
```python
# Before
ui.label(f"File not found: {path}").classes("text-red-400 text-sm p-4")

# After
hui.error_label(f"File not found: {path}")
```

### 1.3  Hardcoded yellow for warnings

**Detect:** Search for:
```
text-yellow-400
text-yellow-500
```

**Fix:** Replace with `hui.warning_label()` or `.hw-text-warning`.

**Example transform:**
```python
# Before
ui.label(f"File too large ({size} KB)").classes("text-yellow-400 text-sm p-4")

# After
hui.warning_label(f"File too large ({size} KB)")
```

### 1.4  Hardcoded blue on links and icons

**Detect:** Search for:
```
text-blue-400
text-blue-300
text-blue-500
```

These appear on external links (`ui.link`), "open in new" icons, and some
badge-adjacent labels.

**Fix:**

For links: style with `color: var(--hw-accent)` via inline style, or add
an `hw-text-accent` class (injected by `hui`).

For icons next to links: use `.hw-text-dim` or `hw-text-accent`.

**Example transform:**
```python
# Before
ui.link(author, url, new_tab=True).classes("text-xs text-blue-400")

# After
ui.link(author, url, new_tab=True).classes("text-xs hw-text-accent")
```

### 1.5  Hardcoded purple on icons

**Detect:** Search for:
```
text-purple-500
text-purple-400
```

**Fix:** Use Quasar's `color=` prop with `.hw-use-props-color`:

```python
# Before
ui.icon(icon).classes("text-purple-500 text-xl")

# After
ui.icon(icon).classes("text-xl hw-use-props-color").props("color=purple")
```

### 1.6  Hardcoded hover backgrounds

**Detect:** Search for:
```
hover:bg-white/10
hover:bg-white/5
hover:bg-black
```

These appear on list items and component rows.

**Fix:** Replace with the `hw-list-item-hover` class (from `hui`), or better,
replace the entire row construction with `hui.list_item()`.

```python
# Before
ui.row().classes("w-full px-2 py-1.5 cursor-pointer hover:bg-white/10 ...")

# After
hui.list_item(label, sublabel=sublabel, dot_color="green", on_click=handler)
```

If `hui.list_item` doesn't fit the exact layout, at minimum replace the hover
class:

```python
# Before
.classes("... hover:bg-white/10 ...")

# After
.classes(f"... {hui._LIST_HOVER_CLASS} ...")
```

Or use the CSS class directly: `hw-list-item-hover`.

### 1.7  Inline hex colours in .style()

**Detect:** Search `.style(` calls for patterns like:
```
#[0-9a-fA-F]{3,8}
rgb(
rgba(
```

Exclude values that are already inside `var(--hw-*)` expressions.

**Fix:** Replace with the appropriate `var(--hw-*)` token.  Common examples:

| Hardcoded value                   | Token                   |
| --------------------------------- | ----------------------- |
| Background hex on a panel         | `var(--hw-bg-page)`     |
| Background hex on a bar           | `var(--hw-bg-surface)`  |
| Border colour hex                 | `var(--hw-border)`      |
| Text colour hex                   | `var(--hw-text-body)`   |
| Error node bg (`#fef2f2`, etc.)   | `var(--hw-danger-bg)`   |
| Ghost pin (`rgba(128,128,128,…)`) | `var(--hw-ghost-pin)`   |
| Modal backdrop (`rgba(0,0,0,…)`)  | `var(--hw-bg-overlay)`  |

### 1.8  Hardcoded active / selection backgrounds

**Detect:** Search for:
```
bg-blue-900
bg-blue-800
hover:bg-blue-
```

These appear on active-state rows (e.g. the currently open graph in
`graph_manager_editor.py`).

**Fix:** Replace with `hui.list_item(is_active=True)` which applies
`var(--hw-bg-active)` automatically:

```python
# Before
row_classes = "... bg-blue-900/40 " if is_active else "... hover:bg-white/10 "

# After
hui.list_item(label, sublabel=subtitle, is_active=is_active, on_click=handler)
```

### 1.9  Hardcoded amber / warning colours

**Detect:** Search for:
```
text-amber-400
text-amber-500
amber-400/
```

These appear on unsaved-state indicators and warning text.

**Fix:** Replace with `var(--hw-warning)`:

```python
# Before
ui.label("not saved").classes("text-xs text-amber-400/70")

# After
ui.label("not saved").classes("text-xs").style("color: var(--hw-warning); opacity: 0.7;")
```

Or, if a dedicated unsaved-state token is added (`--hw-warning-dim`):

```python
ui.label("not saved").classes("text-xs").style("color: var(--hw-warning-dim);")
```

---

## Phase 2 — Structural Component Migration

Replace hand-built component patterns with `hui` wrappers.

### 2.1  Panel headers

**Detect:** Look for this pattern in `render()` methods:

```python
with ui.row().classes("w-full items-center px-* py-* border-b ..."):
    ui.icon(*, size="1*px").classes("hw-text-dim")
    ui.label(*).classes("text-sm font-medium ... truncate ...")
    # action buttons
```

Variations include different `px-` / `py-` values, different icon sizes,
and `flex-shrink-0` sometimes present, sometimes missing.

**Fix:** Replace with `hui.panel_header()`:

```python
with hui.panel_header("Files", icon="folder"):
    hui.icon_action("refresh", tooltip="Refresh", on_click=self._refresh)
```

### 2.2  Empty states

**Detect:** Look for:

```python
with ui.column().classes("w-full h-full items-center justify-center ..."):
    ui.icon(*, size="*px").classes("hw-text-dim")
    ui.label(*).classes("text-sm hw-text-muted")
```

Often preceded by `.style("padding: *px 0;")` with varying values
(60px, 80px, etc.).

**Fix:** Replace with `hui.empty_state()`:

```python
hui.empty_state("Select a file from the Files panel", icon="folder_open")
```

### 2.3  List items / interactive rows

**Detect:** Look for row elements with this combination:

```python
ui.row().classes("... cursor-pointer hover:bg-white/10 ... rounded")
    .on("click", ...)
```

Containing a label + optional sublabel, often with a status dot.

**Fix:** Replace with `hui.list_item()`:

```python
hui.list_item(
    label,
    sublabel=f"v{version}",
    dot_color=dot_color,
    on_click=lambda entry=lib: self._select_library(entry, ctx),
)
```

### 2.4  Section group labels

**Detect:** Look for:

```python
ui.label("SOMETHING").classes("text-xs font-bold hw-text-dim px-2 pt-2 pb-1 tracking-wider")
```

Sometimes `uppercase` is explicit, sometimes the string is already uppercase.
The class string may vary slightly (extra or missing `mt-*`, etc.).

**Fix:** Replace with `hui.section_label()`:

```python
hui.section_label("REQUIRED")
```

### 2.5  Info rows (key-value with copy)

**Detect:** Look for the `_info_row` static/class method pattern, or inline
versions with:

```python
with ui.row().classes("w-full items-center gap-* py-0.5"):
    # copy button
    ui.label(key).classes("text-xs hw-text-dim w-16 ...")
    ui.label(value).classes("text-xs font-mono ...")
```

**Fix:** Replace with `hui.info_row()`:

```python
hui.info_row("Key", registry_key, copy_value=full_key)
```

### 2.6  Code snippet rows

**Detect:** Look for the `_code_row` pattern, or inline versions with a
monospace label inside a surface-coloured container.

**Fix:** Replace with `hui.code_block()`:

```python
hui.code_block("from my_lib import MyNode", label="Import")
```

### 2.7  Section labels / dividers

**Detect:** Look for:

```python
ui.label("TEXT").classes("text-xs font-bold hw-text-dim uppercase tracking-wider mt-3 mb-1")
```

**Fix:** Replace with `hui.section_divider("TEXT")` or `hui.section_label("TEXT")`.

### 2.8  Error labels

**Detect:** Look for any `ui.label` whose classes contain `text-red-*` and
that represents an error message (not a status badge).

**Fix:** Replace with `hui.error_label(msg)`.

### 2.9  Copy buttons

**Detect:** Look for `_copy_btn` static methods or inline constructions of:

```python
ui.button(icon="content_copy", ...).props("flat round dense size=xs color=grey")
```

**Fix:** If the copy button is part of an `info_row` or `code_block`, the
migration to `hui.info_row()` / `hui.code_block()` handles it.  Otherwise,
leave standalone copy buttons as-is (they follow the correct pattern already,
but remove `color=grey` as it should inherit).

### 2.10  Toolbar buttons

**Detect:** In `app_shell.py`, look for:

```python
ui.button(icon=icon).classes(self._toolbar_button_classes(is_active)).props("flat round")
```

**Fix:** Replace with `hui.toolbar_button()`:

```python
hui.toolbar_button(icon, is_active=is_active, tooltip=label, on_click=handler)
```

### 2.11  Scope buttons (properties editor)

**Detect:** In `properties_editor.py`, look for the inline style construction
that builds scope buttons with `width: 36px; height: 36px; ...`.

**Fix:** Replace with `hui.scope_button()`:

```python
hui.scope_button(
    scope.icon,
    is_active=is_active,
    available=available,
    tooltip=scope.label,
    on_click=lambda sid=scope_id: self._set_active_scope(sid, context),
)
```

### 2.12  Tags / badges

**Detect:** Look for:

```python
ui.badge(*).props("outline color=*").classes("text-xs")
```

**Fix:** Replace with `hui.tag()`:

```python
hui.tag("vision")
hui.tag("editable", color="green")
```

### 2.13  Input fields

**Detect:** Look for:

```python
ui.input(*).classes("w-full").props("dense outlined ...")
```

**Fix:** Replace with `hui.input_field()`:

```python
hui.input_field(placeholder="Search libraries…", clearable=True)
```

### 2.14  Number and select fields

**Detect:** Look for:

```python
ui.number(*).classes("w-full").props("dense outlined ...")
ui.select(*).props("dense outlined ...")
```

**Fix:** Replace with `hui.number_field()` / `hui.select_field()`:

```python
# Before
ui.number(label="posX", value=0).classes("w-full").props("dense outlined")

# After
hui.number_field(label="posX", value=0)
```

```python
# Before
ui.select(options=opts, value=v).props("dense outlined").classes("text-sm")

# After
hui.select_field(options=opts, value=v, label="Mode")
```

### 2.15  Settings category expansion headers

**Detect:** Look for `ui.expansion()` used directly in settings/properties
panels with inline header-class strings:

```python
ui.expansion(label, value=True)
.props('dense dense-toggle header-class="text-xs font-bold hw-text-muted uppercase ..."')
```

This pattern appears in `render_utils.py` (`_render_category_group`) and
`node_settings.py`.

**Fix:** Replace with `hui.category_group()`:

```python
# Before
ui.expansion(label, value=True).classes("w-full").props(
    'dense dense-toggle header-class="text-xs font-bold hw-text-muted uppercase'
    ' tracking-wide px-2 py-0 min-h-[24px]"'
)

# After
with hui.category_group(label):
    # field rows
```

Note: `hui.category_group` is distinct from `hui.expansion_section`. Use
`category_group` for settings field categories; use `expansion_section` for
collapsible property panel scopes.

---

## Phase 3 — Border and Divider Consistency

### 3.1  Inline border styles

**Detect:** Search for `.style(` containing:

```
border-bottom: 1px solid
border-right: 1px solid
border-left: 1px solid
border-top: 1px solid
border: 1px solid
```

Check that the colour value is `var(--hw-border)` or `var(--hw-border-strong)`.

**Fix:** Replace any hardcoded border colours:

```python
# Before
.style("border-bottom: 1px solid #2a2a3a;")

# After
.style("border-bottom: 1px solid var(--hw-border);")
```

### 3.2  Tailwind border-colour classes

**Detect:** Search for Tailwind border colour classes:

```
border-gray-*
border-white/*
border-black/*
```

**Fix:** Replace with inline style using `var(--hw-border)`.

---

## Phase 4 — Spacing Normalisation

These are lower priority but improve visual consistency.

### 4.1  Empty state padding

**Detect:** Look for `padding: *px 0` inside empty state constructions.

**Fix:** After migrating to `hui.empty_state()`, this is handled automatically
(standardised to `72px`).  For any remaining manual empty states, use `72px`.

### 4.2  Panel content padding

**Detect:** Compare `p-*` values across editors for similar panel regions.

**Fix:** Standardise:
- Panel header: `px-2 py-1.5`
- Scrollable content area: `p-2` (compact panels) or `p-4` (detail views)
- Detail page content: `px-6 pt-6`

### 4.3  Gap values

**Detect:** Compare `gap-*` values in similar contexts across editors.

**Fix:** Standardise per the spacing system:
- Column of list items: `gap-0`
- Compact field stack: `gap-1`
- Icon + label pair: `gap-2`
- Between sections: `gap-3`

---

## Phase 5 — Quasar Prop Cleanup

### 5.1  `color=grey` on icon buttons

**Detect:** Search for `.props("... color=grey ...")` on action buttons.

**Fix:** Remove `color=grey`.  Icon buttons should inherit their colour from
the parent container (which cascades `--hw-text-body` via `.hw-panel`).
The `color=grey` overrides the theme cascade.

```python
# Before
.props("flat round dense size=xs color=grey")

# After
.props("flat round dense size=xs")
```

### 5.2  `color=primary` on buttons

**Detect:** Search for `color=primary` in `.props()`.

**Fix:** Replace with `color=positive` for confirm/save actions, or remove
entirely and style via `--hw-accent`.  Quasar's `primary` colour is not
mapped to the Haywire theme.

---

## Phase 6 — Structural Patterns

### 6.1  Remove duplicate _info_row, _code_row, _section, _copy_btn statics

**Detect:** Multiple editor classes define their own `_info_row()`,
`_code_row()`, `_section()`, `_copy_btn()` static methods with near-identical
implementations.

**Fix:** Delete these methods.  Replace all call sites with:
- `_info_row(label, value)` → `hui.info_row(label, value, copy_value=v)`
- `_code_row(code, label)` → `hui.code_block(code, label=label)`
- `_section(text)` → `hui.section_label(text)` or `hui.section_divider(text)`
- `_copy_btn(value)` → handled internally by `hui.info_row` / `hui.code_block`

### 6.2  Standardise editor render() skeleton

**Detect:** Every editor's `render()` method constructs its own
`ui.column().classes("w-full h-full gap-0")` → header → scroll area pattern
with slight variations.

**Fix:** Ensure every editor follows the canonical pattern:

```python
def render(self, container, context):
    with container:
        with ui.column().classes("w-full h-full gap-0"):
            # Header (flex-shrink-0) — use hui.panel_header
            with hui.panel_header("Title", icon="icon"):
                pass  # actions

            # Scrollable content (flex-1)
            with ui.scroll_area().classes("flex-1 w-full"):
                self._content = ui.column().classes("w-full p-2 gap-1")
```

### 6.3  Migrate skin hardcoded colours to canvas tokens

**Scope:** `barn/haybale-core/haybale_core/skins/` — specifically
`error_skin.py` and `node_skin.py`.

**Detect:** Search for hardcoded hex or rgba values in skin files:

```bash
grep -rn '#[0-9a-fA-F]\|rgba\?' --include="*.py" barn/haybale-core/haybale_core/skins/
```

**Fix table:**

| File            | Hardcoded value           | Replace with                                                                   |
| --------------- | ------------------------- | ------------------------------------------------------------------------------ |
| `error_skin.py` | `#ef4444`, `#dc2626`      | `var(--hw-danger)`                                                             |
| `error_skin.py` | `#fef2f2`, `#fee2e2`      | `var(--hw-danger-bg)`                                                          |
| `node_skin.py`  | `rgba(128,128,128,0.15)`  | `var(--hw-ghost-pin)`                                                          |
| `node_skin.py`  | `rgba(128,128,128,0.3)`   | `var(--hw-ghost-pin)`                                                          |
| `node_skin.py`  | `rgba(128,128,128,0.4)`   | `color-mix(in srgb, var(--hw-ghost-pin) 133%, transparent)` or a second token  |

**Note:** Also fix non-standard transition durations in `error_skin.py`:
`0.2s` → keep as canvas-tier (permitted); `0.3s` → keep as canvas-tier
(permitted). `transition: all` → replace with named property.

### 6.4  Migrate popup chrome to tokens

**Scope:** `packages/haywire-core/src/haywire/ui/graph_canvas/popup.py` and
`connection_info_popup.py`.

**Detect:** Search for hardcoded shadow and backdrop values:

```bash
grep -rn 'rgba\|box-shadow\|bg-gray\|bg-red\|text-gray' --include="*.py" \
  packages/haywire-core/src/haywire/ui/graph_canvas/
```

**Fix:**

- `rgba(0,0,0,0.5)` backdrop → `var(--hw-bg-overlay)`
- `box-shadow: 0 20px 40px rgba(...)` → `var(--hw-node-shadow)` or add
  `--hw-popup-shadow` to `WorkbenchTheme`
- `bg-gray-*`, `text-gray-*` → appropriate `--hw-*` tokens
- `bg-red-*`, `text-red-*` → `var(--hw-danger)` / `var(--hw-danger-bg)`

---

## Verification Checklist

After completing all phases, run these checks from the repo root:

1. **Grep for Tailwind colour classes** in all editor/panel `.py` files:
   ```bash
   grep -rn "text-gray-\|text-red-\|text-yellow-\|text-blue-\|text-purple-\|text-green-\|text-orange-\|text-amber-" \
     --include="*.py" \
     barn/haybale-studio/haybale_studio/ \
     barn/haybale-core/haybale_core/ \
     packages/haywire-core/src/haywire/ui/
   ```
   Expected: zero hits (except inside Quasar `bg-{color}-500` for status dots).

2. **Grep for hardcoded hex in styles**:
   ```bash
   grep -rn '\.style.*#[0-9a-fA-F]' --include="*.py" \
     barn/haybale-studio/haybale_studio/ \
     barn/haybale-core/haybale_core/ \
     packages/haywire-core/src/haywire/ui/
   ```
   Expected: zero hits (all replaced with `var(--hw-*)`).

3. **Grep for hardcoded rgba/rgb in styles** (excluding theme definition files):
   ```bash
   grep -rn 'rgba\?\s*(' --include="*.py" \
     barn/haybale-studio/haybale_studio/editors/ \
     barn/haybale-studio/haybale_studio/panels/ \
     barn/haybale-core/haybale_core/ \
     packages/haywire-core/src/haywire/ui/
   ```
   Expected: zero hits (theme files `barn/haybale-studio/haybale_studio/themes/` are exempt).

4. **Grep for hover:bg-white and active hardcodes**:
   ```bash
   grep -rn 'hover:bg-white\|bg-blue-900\|hover:bg-black' --include="*.py" \
     barn/haybale-studio/haybale_studio/ \
     barn/haybale-core/haybale_core/
   ```
   Expected: zero hits.

5. **Grep for removed statics**:
   ```bash
   grep -rn '_info_row\|_code_row\|_section\|_copy_btn' --include="*.py" \
     barn/haybale-studio/haybale_studio/editors/
   ```
   Expected: zero hits (all replaced with `hui.*` calls).

6. **Grep for color=grey on buttons**:
   ```bash
   grep -rn 'color=grey' --include="*.py" \
     barn/haybale-studio/haybale_studio/ \
     packages/haywire-core/src/haywire/ui/
   ```
   Expected: zero hits.

7. **Visual test:** Switch between the dark and light workbench themes.
   Every piece of text, every border, every background should respond correctly.
   No white-on-white or black-on-black text. No hardcoded colours standing out
   against the theme. Pay special attention to: node error skins, popup/context
   menus, graph manager active rows, connection info popups.
