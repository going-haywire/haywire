# haybale_studio/panels/_settings_panel_base.py
"""
Shared renderer for FrameworkSettings / LibrarySettings / Reactive schema classes.

Not a panel itself — imported by the concrete settings panels.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.core.settings.enums import SettingMode
from haywire.ui.components.number_drag import NumberDrag

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings import Settings, FieldDescriptor

_ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
_LABEL_CLASSES = "text-xs flex-1 min-w-0 truncate"


def _group_by_category(items: list, key=lambda x: x._category) -> list[tuple[str, list]]:
    """Group a pre-sorted list of descriptors by category, preserving order."""
    return [(cat, list(grp)) for cat, grp in groupby(items, key=key)]


def _render_category_group(category: str) -> ui.expansion:
    """Return a foldable expansion for a category group (use as context manager)."""
    label = category.replace("_", " ").replace(".", " / ").title()
    return (
        ui.expansion(label, value=True)
        .classes("w-full")
        .props(
            "dense dense-toggle"
            ' header-class="text-xs font-bold hw-text-muted uppercase tracking-wide'
            ' px-2 py-0 min-h-[24px]"'
        )
    )


def _render_field_row(label_text: str, description: str, defn, value, make_setter, attr_name: str = ""):
    """Render a single label + widget row."""
    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else ""):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        _render_widget_impl(defn, value, make_setter)


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def render_reactive(obj: "Settings") -> None:
    """Render all ``setting()`` fields of a ``Settings`` instance as labelled form rows.

    - Fields with ``read_only=True`` are skipped (not rendered).
    - Fields with ``mirrors=`` that are locally overridden show a reset-to-global button.
    """

    fields = type(obj)._prop_fields()
    # Exclude read-only fields from rendering
    visible_fields = {name: defn for name, defn in fields.items() if not defn._read_only}
    if not visible_fields:
        ui.label("No props defined.").classes("text-xs text-gray-400 px-2 py-1")
        return

    sorted_fields = sorted(
        visible_fields.items(), key=lambda item: (item[1]._category, item[1]._order, item[0])
    )
    with ui.column().classes("w-full gap-0 compact-fields"):
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with _render_category_group(category):
                for attr_name, defn in group:
                    _render_reactive_field_row(obj, attr_name, defn)


def _render_reactive_field_row(obj: "Settings", attr_name: str, defn: "FieldDescriptor") -> None:
    """Render a single reactive field row, with optional reset button for mirrored fields."""

    @ui.refreshable
    def row_content():
        is_mirrored = bool(defn._mirror_key)
        is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)

        label_text = defn._label or attr_name
        if is_locally_overridden:
            label_text = f"• {label_text}"

        # String fields use ui.input(validation=) for inline error display;
        # int/float/bool use the manual error_container (NumberDrag/switch have no validation= API).
        needs_manual_error = defn._type in (int, float) or defn._type is bool
        error_container = ui.element("div").classes("w-full") if needs_manual_error else None

        with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
            lbl = ui.label(label_text).classes(_LABEL_CLASSES)
            if defn._description:
                lbl.tooltip(defn._description)
            if is_locally_overridden:
                ui.button(icon="restart_alt").props("flat dense size=xs").tooltip(
                    "Reset to global default"
                ).on("click", lambda _o=obj, _n=attr_name: (_o.reset(_n), row_content.refresh()))
            _render_widget_impl(
                defn,
                getattr(obj, attr_name),
                _make_reactive_setter(
                    obj, attr_name, error_container, on_change_callback=row_content.refresh
                ),
            )

    row_content()


def render_schema(schema_cls: type, registry: "SettingsRegistry") -> None:
    """Render all fields of *schema_cls* as labelled form rows."""

    defns = registry.definitions_for_schema(schema_cls)
    if not defns:
        ui.label("No settings defined.").classes("text-xs text-gray-400 px-2 py-1")
        return

    sorted_defns = sorted(defns.values(), key=lambda d: (d._category, d._order, d._field_key))
    with ui.column().classes("w-full gap-0 compact-fields"):
        for category, group in _group_by_category(sorted_defns):
            with _render_category_group(category):
                for defn in group:
                    key = defn._field_key
                    try:
                        value, _ = registry.resolve(key)
                    except KeyError:
                        continue
                    attr_name = defn._attr_name or key.split(".")[-1]
                    _render_field_row(
                        defn._label or attr_name,
                        defn._description,
                        defn,
                        value,
                        lambda coerce, k=key: _make_setter(registry, k, coerce),
                        attr_name=attr_name,
                    )


# ---------------------------------------------------------------------------
# Widget dispatch
# ---------------------------------------------------------------------------


def _render_widget_impl(defn: "FieldDescriptor", value: Any, make_setter) -> None:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler."""
    str_value = str(value) if value is not None else ""

    if defn._widget == "color":
        wrapper = ui.element("div").classes("w-32 shrink-0").props(f'data-value="{str_value}"')
        with wrapper:

            def _color_handler(e, _w=wrapper, _s=make_setter(str)):
                _w.props(f'data-value="{e.value}"')
                _s(e)

            ui.color_input(value=value or "#ffffff").classes("w-full").props(
                "dense hide-bottom-space"
            ).on_value_change(_color_handler)
        return

    resolved_choices = defn.choices
    if resolved_choices is not None:
        wrapper = ui.element("div").classes("w-32 shrink-0").props(f'data-value="{str_value}"')
        with wrapper:

            def _select_handler(e, _w=wrapper, _s=make_setter(lambda v: v)):
                _s(e)
                _w.props(f'data-value="{str(e.value)}"')

            options_keys = (
                resolved_choices if isinstance(resolved_choices, list) else list(resolved_choices.keys())
            )
            ui.select(
                options=resolved_choices,
                value=value if value in options_keys else None,
            ).classes("w-full text-xs").props("dense").on_value_change(_select_handler)
        return

    if defn._type is bool:
        wrapper = ui.element("div").props(f'data-value="{str(bool(value)).lower()}"')
        with wrapper:

            def _bool_handler(e, _w=wrapper, _s=make_setter(bool)):
                _s(e)
                _w.props(f'data-value="{str(bool(e.value)).lower()}"')

            ui.switch(value=bool(value)).props("dense").on_value_change(_bool_handler)
        return

    if defn._type in (int, float):
        kwargs: dict = {}
        if defn._min is not None:
            kwargs["min"] = defn._min
        if defn._max is not None:
            kwargs["max"] = defn._max
        if defn._type is int:
            kwargs["step"] = 1
            kwargs["precision"] = 0
        coerce = defn._type
        handler = make_setter(coerce)

        class _E:
            __slots__ = ("value",)

        nd_ref = [None]

        def _on_number_change(e, _h=handler, _c=coerce):
            ev = _E()
            ev.value = _c(e.args)
            _h(ev)
            if nd_ref[0] is not None:
                nd_ref[0].props(f'data-value="{str(ev.value)}"')

        nd = (
            NumberDrag(value=value if value is not None else 0, on_change=_on_number_change, **kwargs)
            .classes("w-32 shrink-0")
            .props(f'data-value="{str_value}"')
        )
        nd_ref[0] = nd
        return

    wrapper = ui.element("div").classes("w-32 shrink-0").props(f'data-value="{str_value}"')
    with wrapper:

        def _str_handler(e, _w=wrapper, _s=make_setter(str)):
            _s(e)
            _w.props(f'data-value="{str(e.value)}"')

        def _str_validation(v, _defn=defn):
            return None if _defn.validate(str(v) if v is not None else "") else "Invalid value"

        ui.input(
            value=str(value) if value is not None else "",
            on_change=_str_handler,
            validation=_str_validation,
        ).classes("w-full text-xs").props("dense debounce=500")


# ---------------------------------------------------------------------------
# Setter factories
# ---------------------------------------------------------------------------


def _make_reactive_setter(obj: "Settings", attr_name: str, error_container=None, on_change_callback=None):
    """Return a make_setter(coerce) factory that writes to a Settings instance."""

    def make_setter(coerce):
        def handler(e):
            try:
                coerced = coerce(e.value)
            except Exception as exc:
                if error_container is not None:
                    error_container.clear()
                    with error_container:
                        ui.label(str(exc)).classes("text-xs text-red-400 px-2").props('data-error="true"')
                return

            # Check validator before setting — descriptors silently reject invalid values
            descriptor = type(obj)._prop_fields().get(attr_name)
            if descriptor is not None and not descriptor.validate(coerced):
                if error_container is not None:
                    error_container.clear()
                    with error_container:
                        ui.label(f"Invalid value: {coerced!r}").classes("text-xs text-red-400 px-2").props(
                            'data-error="true"'
                        )
                return

            # Only rebuild the row when mirror override state changes (avoids destroying
            # focused input elements on every keystroke for plain value changes)
            was_locally_set = (
                obj.is_locally_set(attr_name) if descriptor and descriptor._mirror_key else None
            )
            setattr(obj, attr_name, coerced)
            is_locally_set = obj.is_locally_set(attr_name) if descriptor and descriptor._mirror_key else None

            if error_container is not None:
                error_container.clear()
            if on_change_callback is not None and was_locally_set != is_locally_set:
                ui.timer(0, on_change_callback, once=True)

        return handler

    return make_setter


def _make_setter(registry: "SettingsRegistry", key: str, coerce):
    """Return an on_change handler that writes *key* to the registry workspace tier."""

    def handler(e):
        try:
            val = coerce(e.value)
            if val is None:
                return
            registry.set_global(key, val, SettingMode.SET)
            registry.save_to_toml_debounced()
        except Exception:
            pass

    return handler
