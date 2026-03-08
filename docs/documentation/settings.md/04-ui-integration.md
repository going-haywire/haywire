# UI Integration Guide

This guide covers how to build settings panels using NiceGUI, including widget selection, inheritance indicators, and the override affordance.

---

## Overview

The settings system exposes rich metadata for UI rendering via `SettingInfo` (returned by `holder.get_info(attr_name)`) and `SettingDefinition` (stored on descriptors and in the global registry). Key fields:

- `info.value` — resolved value
- `info.source` — `'global_override'`, `'local'`, `'global'`, or `'default'`
- `info.is_overridden` — `True` when `OVERRIDE` mode is active in the global registry
- `info.is_inherited` — `True` when using global or default (not locally set)
- `info.definition` — `SettingDefinition` with `label`, `description`, `_min`, `_max`, `_choices`, `_widget`

---

## Node Settings Panel

```python
from nicegui import ui
from haywire.core.settings import SettingMode


def render_node_settings_panel(node):
    """Render settings panel for a specific node."""

    with ui.card().classes('w-full p-4'):
        with ui.row().classes('items-center justify-between mb-4'):
            ui.label(f'Settings: {node.identity.label}').classes('text-xl font-bold')
            ui.button('Reset All', icon='refresh',
                      on_click=lambda: _reset_all(node)).props('flat dense')

        schema = type(node)._settings_schema
        # Group schema fields by category
        by_cat: dict[str, list[str]] = {}
        for attr_name, d in schema._fields.items():
            if not d._panel_visible:
                continue
            cat = d._category or 'general'
            by_cat.setdefault(cat, []).append(attr_name)

        for cat, names in sorted(by_cat.items()):
            with ui.expansion(cat.replace('.', ' > ').replace('_', ' ').title(),
                               value=True).classes('w-full mb-2'):
                sorted_names = sorted(names, key=lambda n: schema._fields[n]._order)
                for attr_name in sorted_names:
                    _render_node_setting_row(node, attr_name)


def _render_node_setting_row(node, attr_name: str):
    """Render one setting row."""
    info = node.settings.get_info(attr_name)
    d    = info.definition

    with ui.row().classes('w-full items-center gap-2 py-1'):
        _render_status_icon(info)

        with ui.element('div').classes('w-44'):
            ui.label(d.label or attr_name).classes('font-medium')
            if d.description:
                ui.icon('help_outline', size='xs').classes('ml-1 opacity-50').tooltip(d.description)

        with ui.element('div').classes('flex-grow'):
            if info.is_overridden:
                ui.label(str(info.value)).classes('text-gray-500 italic')
            else:
                _create_setting_widget(node, attr_name, info)

        # Reset button — only for locally-set shadow/setting fields
        if info.local_mode == SettingMode.SET and not info.is_overridden:
            ui.button(icon='refresh',
                      on_click=lambda n=attr_name: _reset_one(node, n)
                      ).props('flat dense round').tooltip('Reset to inherited')
        else:
            ui.element('div').classes('w-8')


def _render_status_icon(info):
    if info.is_overridden:
        ui.icon('lock', color='orange').tooltip('Forced by global settings')
    elif info.source == 'local':
        ui.icon('edit', color='green').tooltip('Per-node override')
    elif info.source == 'global':
        ui.icon('language', color='blue').tooltip('Using global value')
    else:
        ui.icon('auto_fix_high', color='grey').tooltip('Using default')


def _create_setting_widget(node, attr_name: str, info):
    def on_change(v):
        node.settings.set(attr_name, v)

    _build_widget(info.definition, info.value, on_change)


def _reset_one(node, attr_name: str):
    node.settings.reset(attr_name)
    ui.notify(f'Reset: {attr_name}')


def _reset_all(node):
    node.settings.reset_all()
    ui.notify('All settings reset')
```

---

## Global Settings Panel

```python
from nicegui import ui
from haywire.core.settings import SettingMode


def render_global_settings_panel(registry):
    """Render the global settings panel."""

    with ui.card().classes('w-full max-w-2xl p-4'):
        ui.label('Global Settings').classes('text-2xl font-bold mb-4')

        by_cat = registry.definitions_by_category()
        for cat_name in sorted(by_cat.keys()):
            defs = sorted(by_cat[cat_name], key=lambda d: d.ui_order)
            with ui.expansion(cat_name.replace('.', ' > ').title(),
                               value=True).classes('w-full mb-2'):
                for defn in defs:
                    _render_global_setting_row(registry, defn)

        ui.separator().classes('my-4')
        with ui.row().classes('justify-end'):
            ui.button('Save', icon='save',
                      on_click=lambda: _save(registry)).props('color=primary')


def _render_global_setting_row(registry, defn):
    sv = registry.get_global(defn.name)
    current = sv.value if sv.mode != SettingMode.AUTO else defn.default
    is_override = sv.mode == SettingMode.OVERRIDE

    with ui.row().classes('w-full items-center gap-2 py-1'):
        # Override lock button
        lock = ui.button(icon='lock' if is_override else 'lock_open',
                         color='orange' if is_override else 'grey'
                         ).props('flat dense round')
        lock.on('click', lambda d=defn: _toggle_override(registry, d))

        with ui.element('div').classes('w-48'):
            ui.label(defn.label).classes('font-medium')
            if defn.description:
                ui.icon('help_outline', size='xs').classes('ml-1 opacity-50').tooltip(defn.description)

        with ui.element('div').classes('flex-grow'):
            def on_change(v, n=defn.name):
                mode = registry.get_global(n).mode
                registry.set_global(n, v, mode if mode != SettingMode.AUTO else SettingMode.SET)

            _build_widget(defn, current, on_change)


def _toggle_override(registry, defn):
    sv = registry.get_global(defn.name)
    current = sv.value if sv.mode != SettingMode.AUTO else defn.default
    new_mode = SettingMode.SET if sv.mode == SettingMode.OVERRIDE else SettingMode.OVERRIDE
    registry.set_global(defn.name, current, new_mode)
    ui.notify(f'{defn.label}: override {"enabled" if new_mode == SettingMode.OVERRIDE else "disabled"}')


def _save(registry):
    registry.save_to_toml()
    ui.notify('Settings saved', type='positive')
```

---

## Widget Factory

```python
def _build_widget(defn, value, on_change):
    """Create an appropriate NiceGUI widget based on descriptor metadata."""

    widget_hint = getattr(defn, '_widget', None) or getattr(defn, 'ui_widget', None)
    choices     = getattr(defn, '_choices', None) or getattr(defn, 'choices', None)
    min_val     = getattr(defn, '_min', None)     or getattr(defn, 'min_value', None)
    max_val     = getattr(defn, '_max', None)     or getattr(defn, 'max_value', None)
    default     = getattr(defn, '_default', None) or getattr(defn, 'default', None)

    if widget_hint == 'color' or (isinstance(default, str) and str(default).startswith('#')):
        inp = ui.color_input(value=value).classes('w-32')
        inp.on('change', lambda e: on_change(e.value))

    elif choices:
        sel = ui.select(options=choices, value=value).classes('w-48')
        sel.on('change', lambda e: on_change(e.value))

    elif isinstance(default, bool) or isinstance(value, bool):
        sw = ui.switch(value=bool(value))
        sw.on('change', lambda e: on_change(e.value))

    elif isinstance(default, (int, float)) and min_val is not None and max_val is not None:
        step = 0.01 if isinstance(default, float) else 1
        with ui.row().classes('items-center gap-2 flex-grow'):
            slider = ui.slider(min=min_val, max=max_val, step=step, value=value).classes('flex-grow')
            lbl    = ui.label(str(value)).classes('w-12 text-right')
            def _upd(e):
                on_change(e.value)
                lbl.text = f'{e.value:.2f}' if isinstance(default, float) else str(int(e.value))
            slider.on('change', _upd)

    elif isinstance(default, int):
        inp = ui.number(value=value, min=min_val, max=max_val, step=1, format='%d').classes('w-32')
        inp.on('change', lambda e: on_change(int(e.value)))

    elif isinstance(default, float):
        inp = ui.number(value=value, min=min_val, max=max_val, step=0.01).classes('w-32')
        inp.on('change', lambda e: on_change(float(e.value)))

    else:
        inp = ui.input(value=str(value)).classes('w-full')
        inp.on('change', lambda e: on_change(e.value))
```

---

## Widget Mapping Reference

| Condition | Widget |
|-----------|--------|
| `_widget='color'` or default starts with `#` | Color picker |
| `_choices` set | Dropdown |
| type is `bool` | Toggle switch |
| numeric type with `_min`/`_max` | Slider |
| numeric type without range | Number input |
| otherwise | Text input |

---

## Live Updates

Subscribe to change callbacks to refresh the panel when settings change:

```python
def render_live_panel(node):
    container = ui.element('div')

    def refresh():
        container.clear()
        with container:
            render_node_settings_panel(node)

    refresh()
    node.settings.on_change(lambda name, value, source: refresh())
```

---

## Next Steps

- **[API Reference](05-reference.md)** — Complete descriptor and registry API
- **[Testing Guide](06-testing.md)** — Testing settings-dependent code
