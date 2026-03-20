# haybale_studio/panels/_settings_panel_base.py
"""
Shared renderer for GlobalSettings / LibrarySettings / Reactive schema classes.

Not a panel itself — imported by the concrete settings panels.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.core.settings.enums import SettingMode

if TYPE_CHECKING:
    from haywire.core.settings.registry import GlobalSettingsRegistry
    from haywire.core.settings.holder import SubHolder
    from haywire.core.property import Bag, FieldDescriptor

_ROW_CLASSES = 'w-full items-center justify-between gap-0 px-2'
_LABEL_CLASSES = 'text-xs flex-1 min-w-0 truncate'


def _group_by_category(items: list, key=lambda x: x._category) -> list[tuple[str, list]]:
    """Group a pre-sorted list of descriptors by category, preserving order."""
    return [(cat, list(grp)) for cat, grp in groupby(items, key=key)]


def _render_category_group(category: str) -> ui.expansion:
    """Return a foldable expansion for a category group (use as context manager)."""
    label = category.replace('_', ' ').replace('.', ' / ').title()
    return ui.expansion(label, value=True).classes('w-full').props(
        'dense dense-toggle'
        ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
        ' px-2 py-0 min-h-[24px]"'
    )


def _render_field_row(label_text: str, description: str, defn, value, make_setter):
    """Render a single label + widget row."""
    with ui.row().classes(_ROW_CLASSES):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        _render_widget_impl(defn, value, make_setter)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def render_reactive(obj: 'Bag') -> None:
    """Render all ``prop()`` fields of a ``Reactive`` instance as labelled form rows."""

    fields = type(obj)._prop_fields()
    if not fields:
        ui.label('No props defined.').classes('text-xs text-gray-400 px-2 py-1')
        return

    sorted_fields = sorted(fields.items(), key=lambda item: (item[1]._category, item[1]._order, item[0]))
    with ui.column().classes('w-full gap-0 compact-fields'):
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with _render_category_group(category):
                for attr_name, defn in group:
                    _render_field_row(
                        defn._label or attr_name, defn._description,
                        defn, getattr(obj, attr_name), _make_reactive_setter(obj, attr_name),
                    )


def render_schema(schema_cls: type, registry: 'GlobalSettingsRegistry') -> None:
    """Render all fields of *schema_cls* as labelled form rows."""

    defns = registry.definitions_for_schema(schema_cls)
    if not defns:
        ui.label('No settings defined.').classes('text-xs text-gray-400 px-2 py-1')
        return

    sorted_defns = sorted(defns.values(), key=lambda d: (d._category, d._order, d._field_key))
    with ui.column().classes('w-full gap-0 compact-fields'):
        for category, group in _group_by_category(sorted_defns):
            with _render_category_group(category):
                for defn in group:
                    key = defn._field_key
                    try:
                        value, _ = registry.resolve(key)
                    except KeyError:
                        continue
                    _render_field_row(
                        defn._label or defn._attr_name or key.split('.')[-1],
                        defn._description, defn, value,
                        lambda coerce, k=key: _make_setter(registry, k, coerce),
                    )


def render_sub_holder(sub_holder: 'SubHolder') -> None:
    """Render all fields of *sub_holder* as labelled form rows."""

    from haywire.core.settings.holder import _collect_fields

    schema_cls = object.__getattribute__(sub_holder, '_schema')
    fields = _collect_fields(schema_cls)
    if not fields:
        ui.label('No settings defined.').classes('text-xs text-gray-400 px-2 py-1')
        return

    sorted_fields = sorted(fields.items(), key=lambda item: (item[1]._category, item[1]._order, item[0]))
    with ui.column().classes('w-full gap-0 compact-fields'):
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with _render_category_group(category):
                for attr_name, defn in group:
                    try:
                        value = getattr(sub_holder, attr_name)
                    except Exception:
                        continue
                    _render_field_row(
                        defn._label or attr_name, defn._description,
                        defn, value, _make_sub_holder_setter(sub_holder, attr_name),
                    )


# ---------------------------------------------------------------------------
# Widget dispatch
# ---------------------------------------------------------------------------

def _render_widget_impl(defn: 'FieldDescriptor', value: Any, make_setter) -> None:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler."""
    if defn._widget == 'color':
        ui.color_input(value=value or '#ffffff') \
            .classes('flex-1 min-w-0') \
            .on('change', make_setter(str))
        return

    resolved_choices = defn.choices
    if resolved_choices is not None:
        ui.select(
            options=resolved_choices, value=value,
            on_change=make_setter(lambda v: v),
        ).classes('flex-1 min-w-0 text-xs').props('dense')
        return

    if defn._type is bool:
        ui.switch(value=bool(value), on_change=make_setter(bool)).props('dense')
        return

    if defn._type in (int, float):
        kwargs: dict = {}
        if defn._min is not None:
            kwargs['min'] = defn._min
        if defn._max is not None:
            kwargs['max'] = defn._max
        if defn._type is int:
            kwargs['step'] = 1
            kwargs['format'] = '%.0f'
        ui.number(value=value, on_change=make_setter(defn._type), **kwargs) \
            .classes('flex-1 min-w-0 text-xs').props(
                'dense hide-bottom-space'
                ' input-style="appearance:none;-moz-appearance:textfield;"'
                ' input-class="text-center"'
            )
        return

    ui.input(
        value=str(value) if value is not None else '',
        on_change=make_setter(str),
    ).classes('flex-1 min-w-0 text-xs').props('dense')


# ---------------------------------------------------------------------------
# Setter factories
# ---------------------------------------------------------------------------

def _make_reactive_setter(obj: 'Bag', attr_name: str):
    """Return a make_setter(coerce) factory that writes to a Reactive prop."""
    def make_setter(coerce):
        def handler(e):
            try:
                setattr(obj, attr_name, coerce(e.value))
            except Exception:
                pass
        return handler
    return make_setter


def _make_sub_holder_setter(sub_holder: 'SubHolder', attr_name: str):
    """Return a make_setter(coerce) factory that writes to a SubHolder field."""
    def make_setter(coerce):
        def handler(e):
            try:
                sub_holder.set(attr_name, coerce(e.value))
            except Exception:
                pass
        return handler
    return make_setter


def _make_setter(registry: 'GlobalSettingsRegistry', key: str, coerce):
    """Return an on_change handler that writes *key* to the registry workspace tier."""
    def handler(e):
        try:
            val = coerce(e.value)
            if val is None:
                return
            registry.set_global(key, val, SettingMode.SET)
            registry.save_to_toml()
        except Exception:
            pass
    return handler
