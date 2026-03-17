# haybale_studio/panels/_settings_panel_base.py
"""
Shared renderer for GlobalSettings / LibrarySettings schema classes.

Not a panel itself — imported by the concrete settings panels.

Usage inside a panel's draw():

    def draw(self, context, layout):
        registry = context.app.library_service.get_settings_registry()
        with layout.column():
            render_schema(MySettingsClass, registry)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.core.settings.enums import SettingMode

if TYPE_CHECKING:
    from haywire.core.settings.registry import GlobalSettingsRegistry
    from haywire.core.settings.holder import SubHolder
    from haywire.core.settings.descriptors import SettingDescriptor


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_schema(schema_cls: type, registry: 'GlobalSettingsRegistry') -> None:
    """
    Render all fields of *schema_cls* as labelled form rows into the current
    NiceGUI slot context.  Call this from inside a ``with layout.column():``
    block (or any other NiceGUI container).
    """
    defns = registry.definitions_for_schema(schema_cls)
    if not defns:
        ui.label('No settings defined.').classes('text-xs text-gray-400 px-2 py-1')
        return

    sorted_defns = sorted(defns.values(), key=lambda d: (d._order, d._field_key))
    for defn in sorted_defns:
        _render_field(defn, registry)


# ---------------------------------------------------------------------------
# SubHolder renderer (node instance settings)
# ---------------------------------------------------------------------------

def render_sub_holder(sub_holder: 'SubHolder') -> None:
    """
    Render all fields of *sub_holder* as labelled form rows.

    Reads current values from the SubHolder and writes changes back via
    ``sub_holder.set(attr_name, value)``.  Call from inside a
    ``with layout.column():`` block.
    """
    from haywire.core.settings.holder import _collect_fields

    schema_cls = object.__getattribute__(sub_holder, '_schema')
    fields = _collect_fields(schema_cls)
    if not fields:
        ui.label('No settings defined.').classes('text-xs text-gray-400 px-2 py-1')
        return

    sorted_fields = sorted(fields.items(), key=lambda item: (item[1]._order, item[0]))
    for attr_name, defn in sorted_fields:
        _render_sub_holder_field(attr_name, defn, sub_holder)


def _render_sub_holder_field(
    attr_name: str, defn: 'SettingDescriptor', sub_holder: 'SubHolder'
) -> None:
    try:
        value = getattr(sub_holder, attr_name)
    except Exception:
        return

    label_text = defn._label or attr_name

    with ui.row().classes('w-full items-center justify-between gap-0 px-2 py-0'):
        lbl = ui.label(label_text).classes('text-sm flex-1 min-w-0 truncate')
        if defn._description:
            lbl.tooltip(defn._description)
        _render_sub_holder_widget(attr_name, defn, value, sub_holder)


def _render_sub_holder_widget(
    attr_name: str, defn: 'SettingDescriptor', value: Any, sub_holder: 'SubHolder'
) -> None:
    def make_setter(coerce):
        def handler(e):
            try:
                sub_holder.set(attr_name, coerce(e.value))
            except Exception:
                pass
        return handler

    _render_widget_impl(defn, value, make_setter)


# ---------------------------------------------------------------------------
# Per-field renderer (global registry)
# ---------------------------------------------------------------------------

def _render_field(defn: 'SettingDescriptor', registry: 'GlobalSettingsRegistry') -> None:
    key = defn._field_key
    try:
        value, _ = registry.resolve(key)
    except KeyError:
        return

    label_text = defn._label or defn._attr_name or key.split('.')[-1]

    with ui.row().classes('w-full items-center justify-between gap-0 px-2 py-0'):
        lbl = ui.label(label_text).classes('text-sm flex-1 min-w-0 truncate')
        if defn._description:
            lbl.tooltip(defn._description)
        _render_widget(defn, value, registry)


def _render_widget(defn: 'SettingDescriptor', value: Any, registry: 'GlobalSettingsRegistry') -> None:
    """Dispatch to the appropriate NiceGUI widget for *defn*."""
    key = defn._field_key
    _render_widget_impl(defn, value, lambda coerce: _make_setter(registry, key, coerce))


def _render_widget_impl(defn: 'SettingDescriptor', value: Any, make_setter) -> None:
    """Shared widget dispatch. make_setter(coerce) → on_change handler."""

    # ── Explicit color hint ──────────────────────────────────────────────────
    if defn._widget == 'color':
        ui.color_input(value=value or '#ffffff') \
            .classes('flex-1 min-w-0') \
            .on('change', make_setter(str))
        return

    # ── Choices → select ─────────────────────────────────────────────────────
    resolved_choices = defn.choices
    if resolved_choices is not None:
        ui.select(
            options=resolved_choices,
            value=value,
            on_change=make_setter(lambda v: v),
        ).classes('flex-1 min-w-0 text-sm').props('dense')
        return

    # ── Bool → switch ────────────────────────────────────────────────────────
    if defn._type is bool:
        ui.switch(
            value=bool(value),
            on_change=make_setter(bool),
        )
        return

    # ── Numeric → number input ───────────────────────────────────────────────
    if defn._type in (int, float):
        kwargs: dict = {}
        if defn._min is not None:
            kwargs['min'] = defn._min
        if defn._max is not None:
            kwargs['max'] = defn._max
        if defn._type is int:
            kwargs['step'] = 1
            kwargs['format'] = '%.0f'
        ui.number(
            value=value,
            on_change=make_setter(defn._type),
            **kwargs,
        ).classes('flex-1 min-w-0 text-sm').props('dense hide-bottom-space input-style="appearance:none;-moz-appearance:textfield;" input-class="text-center"')
        return

    # ── String fallback → input ──────────────────────────────────────────────
    ui.input(
        value=str(value) if value is not None else '',
        on_change=make_setter(str),
    ).classes('flex-1 min-w-0 text-sm').props('dense')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_setter(registry: 'GlobalSettingsRegistry', key: str, coerce):
    """Return an on_change handler that writes *key* to the registry workspace tier."""
    def handler(e):
        try:
            val = coerce(e.value)
            if val is None:
                return
            registry.set_global(key, val, SettingMode.SET)
            _try_save(registry)
        except Exception:
            pass
    return handler


def _try_save(registry: 'GlobalSettingsRegistry') -> None:
    """Persist workspace tier to TOML; silently ignored if no path is configured."""
    try:
        registry.save_to_toml()
    except (ValueError, Exception):
        pass
