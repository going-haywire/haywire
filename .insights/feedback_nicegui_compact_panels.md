---
name: NiceGUI/Quasar compact field styling
description: The compact-fields CSS utility class — what it does, where it's defined, how to use it, and the underlying Quasar spacing issues it fixes
type: feedback
---

Haywire provides a shared **`compact-fields`** CSS utility class for tightening NiceGUI/Quasar field rendering. It is injected once by `AppShell` in `_static_css` (no per-component `ui.add_css()` needed).

## How to use

Add the `compact-fields` class to any container whose children need compact Quasar fields:

```python
with ui.column().classes('w-full gap-0 compact-fields'):
    ui.number(value=42).props('dense')
```

## Where it's defined

- **CSS**: `packages/haywire-core/src/haywire/ui/app/shell.py` → `_static_css` string
- **CSS custom properties** (in `:root`, overridable by themes):
  - `--hw-compact-gap: 0.25rem` — row gap
  - `--hw-compact-field-h: 26px` — input field height
  - `--hw-compact-row-min-h: 28px` — minimum row height

## Where it's applied

- **Settings panels** (`_settings_panel_base.py`) — `render_reactive`, `render_schema`, `render_sub_holder` wrap output in `ui.column().classes('w-full gap-0 compact-fields')`
- **Node skins** (`node_skin.py`) — port content columns (inlet, outlet, config) use `.classes('compact-fields')` so inline widgets render compactly

## What causes the spacing bloat (reference)

1. **`--nicegui-default-gap: 1rem`** — NiceGUI's CSS variable controls gap between rows. Single biggest space waster.
2. **`.q-field` has `items-start`** — lets `.q-field__inner` (with `self-stretch`) expand vertically.
3. **`.q-field__bottom`** — Hidden space reserved for validation/hint text.
4. **`.q-field__control::before/::after`** — Quasar underline decoration.
5. **`.q-toggle` / `.q-switch`** — Default margin/padding even when `dense`.

## DOM structure reference

```
.nicegui-row.row          (our row — has label + widget)
  div                     (label)
  label.q-field           (Quasar field wrapper — items-start is the problem)
    .q-field__inner       (self-stretch + col — expands to row height)
      .q-field__control   (the actual input container)
        .q-field__native  (the <input> element)
      .q-field__bottom    (hidden validation space)
```

## Quasar expansion headers (for foldable categories)

Essential props: `dense`, `dense-toggle`, `py-0`, `px-2`.
Styling props: `text-xs font-bold text-gray-500 uppercase tracking-wide`.

**Why:** NiceGUI/Quasar's `q-field` flexbox model (`items-start` + `self-stretch`) silently inflates row heights. Tailwind arbitrary selectors with `__` escaping don't work for Quasar class names. A shared CSS class injected by AppShell is the reliable approach.

**How to apply:** Add `compact-fields` to any container that needs compact field rendering. No `ui.add_css()` call needed — the CSS is global. Theme authors can override `--hw-compact-*` custom properties.
