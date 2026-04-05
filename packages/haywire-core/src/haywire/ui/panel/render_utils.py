# haybale_studio/panels/_settings_panel_base.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Any

from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.settings.enums import FieldMode
from haywire.core.settings.types import get_vec_meta
from haywire.ui.components.number.drag import NumberDrag

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings import Settings, FieldDescriptor

_ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
_LABEL_CLASSES = "text-xs min-w-0 truncate sf-label"
_WIDGET_CLASSES = "sf-widget"
_COLUMN_STYLE = "container-type: inline-size; container-name: settings-panel;"


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def render_settings(obj: "Settings") -> None:
    """Render all ``field()`` fields of a ``Settings`` instance as labelled form rows.

    - Fields with ``read_only=True`` are skipped (not rendered).
    - Fields with ``mirrors=`` that are locally overridden show a reset-to-global button.
    """

    fields = type(obj)._property_fields()
    # Exclude read-only fields from rendering
    visible_fields = {name: defn for name, defn in fields.items() if not defn._read_only}
    if not visible_fields:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    sorted_fields = sorted(
        visible_fields.items(),
        key=lambda item: (
            "" if item[1]._category.lower() == "root" else item[1]._category,
            item[1]._order,
            item[0],
        ),
    )
    with ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE):
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with hui.category_group(category):
                for attr_name, defn in group:
                    _render_reactive_field_row(obj, attr_name, defn)


def render_schema(schema_cls: type, registry: "SettingsRegistry") -> None:
    """Render only the fields declared on *schema_cls* as labelled form rows.

    Uses the schema's own _property_fields() so that keys registered under the
    same namespace prefix by other code (e.g. dynamic library keys) are not
    accidentally included.
    """
    prop_fields = schema_cls._property_fields()
    defns = {
        defn._field_key: defn
        for defn in prop_fields.values()
        if defn._field_key and registry.has_definition(defn._field_key)
    }
    if not defns:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    sorted_defns = sorted(
        defns.values(),
        key=lambda d: ("" if d._category.lower() == "root" else d._category, d._order, d._field_key),
    )
    _render_definitions(sorted_defns, registry)


def render_keys(prefix: str, registry: "SettingsRegistry") -> None:
    """Render all registry keys whose full key starts with *prefix*.

    Intended for dynamically registered keys (e.g. per-library log levels)
    that are not declared on any schema class. The category label is derived
    from the key structure via _render_category_group.
    """
    match_prefix = prefix + "."
    defns = {key: defn for key, defn in registry.all_definitions().items() if key.startswith(match_prefix)}
    if not defns:
        ui.label(f"No fields found under: {prefix}.*").classes("text-xs hw-text-muted px-2 py-1")
        return

    sorted_defns = sorted(
        defns.values(),
        key=lambda d: ("" if d._category.lower() == "root" else d._category, d._order, d._field_key),
    )
    _render_definitions(sorted_defns, registry)


def _render_definitions(sorted_defns: list, registry: "SettingsRegistry") -> None:
    """Render a pre-sorted list of field descriptors grouped by category."""
    with ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE):
        for category, group in _group_by_category(sorted_defns):
            with hui.category_group(category):
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


def _group_by_category(items: list, key=lambda x: x._category) -> list[tuple[str, list]]:
    """Group a pre-sorted list of descriptors by category, preserving order."""
    return [(cat, list(grp)) for cat, grp in groupby(items, key=key)]


def _render_field_row(label_text: str, description: str, defn, value, make_setter, attr_name: str = ""):
    """Render a single label + widget row."""
    vec_meta = get_vec_meta(defn._type)
    if vec_meta is not None:
        _render_vec_field_rows(label_text, description, vec_meta, value, make_setter, attr_name)
        return
    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else ""):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        _render_widget_impl(defn, value, make_setter)


def _render_reactive_field_row(obj: "Settings", attr_name: str, defn: "FieldDescriptor") -> None:
    """Render a single reactive field row, with optional reset button for mirrored fields."""

    @ui.refreshable
    def row_content():
        is_mirrored = bool(defn._mirror_key)
        is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)
        label_text = defn._label or attr_name
        if is_locally_overridden:
            label_text = f"• {label_text}"

        def _render_label():
            with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
                lbl = ui.label(label_text).classes("text-xs truncate")
                if defn._description:
                    lbl.tooltip(defn._description)
                if is_locally_overridden:
                    ui.button(icon=hui.icon.reset).props("flat dense size=xs").tooltip(
                        "Reset to global default"
                    ).on("click", lambda _o=obj, _n=attr_name: (_o.reset(_n), row_content.refresh()))

        vec_meta = get_vec_meta(defn._type)
        if vec_meta is not None:
            make_setter = _make_reactive_setter(obj, attr_name, on_change_callback=row_content.refresh)
            _render_vec_field_rows(
                label_text,
                defn._description,
                vec_meta,
                getattr(obj, attr_name),
                make_setter,
                attr_name,
                render_label=_render_label,
            )
            return

        # String fields use ui.input(validation=) for inline error display;
        # int/float/bool use the manual error_container (NumberDrag/switch have no validation= API).
        needs_manual_error = defn._type in (int, float) or defn._type is bool
        error_container = ui.element("div").classes("w-full") if needs_manual_error else None

        with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
            _render_label()
            _render_widget_impl(
                defn,
                getattr(obj, attr_name),
                _make_reactive_setter(
                    obj, attr_name, error_container, on_change_callback=row_content.refresh
                ),
            )

    row_content()


# ---------------------------------------------------------------------------
# Widget dispatch
# ---------------------------------------------------------------------------


def _render_vec_field_rows(
    label_text: str,
    description: str,
    vec_meta,
    value: Any,
    make_setter,
    attr_name: str = "",
    render_label=None,
) -> None:
    """Render a vector field as a tight column of rows aligned to the panel grid.

    Layout per row:  [field label / spacer]  [X/Y/Z]  [NumberDrag]

    render_label: optional callable that renders the label cell on row 0 (used by
    reactive rows to inject the reset button inline after the label text).
    """
    current = list(value) if value is not None else [0] * vec_meta.length
    while len(current) < vec_meta.length:
        current.append(0)
    current = current[: vec_meta.length]

    step = 1 if vec_meta.element_type is int else None
    precision = 0 if vec_meta.element_type is int else None
    coerce = vec_meta.element_type

    class _E:
        __slots__ = ("value",)

    def _make_component_setter(idx, _cv=current, _ms=make_setter, _c=coerce):
        handler = _ms(lambda v: v)

        def _on_change(e, _i=idx, _h=handler, _cv=_cv, _c=_c):
            _cv[_i] = _c(e.args)
            ev = _E()
            ev.value = list(_cv)
            _h(ev)

        return _on_change

    nd_kwargs: dict = {}
    if step is not None:
        nd_kwargs["step"] = step
        nd_kwargs["precision"] = precision

    prop = f'data-field="{attr_name}"' if attr_name else ""

    # Outer row: label left, component column right.
    # items-start keeps the label aligned to the first component row, not centred across all.
    with ui.row().classes(_ROW_CLASSES.replace("items-center", "items-start") + " py-1").props(prop):
        if render_label is not None:
            render_label()
        else:
            lbl = ui.label(label_text).classes(_LABEL_CLASSES)
            if description:
                lbl.tooltip(description)
        # Component rows: gap-0, tighter row height than standard compact-fields rows
        with ui.column().classes("gap-0 flex-1 pb-1").style("--hw-compact-row-min-h: 22px;"):
            for i, component_label in enumerate(vec_meta.labels):
                with ui.row().classes("w-full items-center gap-1"):
                    ui.label(component_label).classes("text-xs w-4 text-right hw-text-muted shrink-0")
                    NumberDrag(
                        value=coerce(current[i]),
                        on_change=_make_component_setter(i),
                        **nd_kwargs,
                    ).classes("flex-1")


def _float_step_from_default(default: Any) -> float:
    """Derive a drag step from the decimal places of a float default value.

    0 decimals (e.g. 1.0 or 1) → 0.1, 1 decimal (e.g. 0.3) → 0.01, etc.
    """
    if not isinstance(default, (int, float)):
        return 0.1
    s = str(float(default))
    dot = s.find(".")
    if dot < 0:
        decimals = 0
    else:
        decimals = len(s.rstrip("0")) - dot - 1
    return 10 ** -(decimals + 1)


def _render_widget_impl(defn: "FieldDescriptor", value: Any, make_setter) -> None:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler."""
    # Escape for safe embedding in props strings (newlines etc. break ast.literal_eval)
    str_value = (str(value) if value is not None else "").encode("unicode_escape").decode()

    if defn._widget == "label":
        ui.label(str_value).classes(f"text-xs text-right truncate hw-text-muted {_WIDGET_CLASSES}").props(
            f'data-value="{str_value}"'
        )
        return

    if defn._widget == "color":
        wrapper = ui.element("div").classes(_WIDGET_CLASSES).props(f'data-value="{str_value}"')
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
        wrapper = (
            ui.element("div")
            .classes(f"{_WIDGET_CLASSES} overflow-hidden")
            .props(f'data-value="{str_value}"')
        )
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
            ).classes("w-full text-xs").props("dense hide-bottom-space").on_value_change(_select_handler)
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
        elif defn._type is float:
            kwargs["step"] = _float_step_from_default(defn._default)
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
            .classes(_WIDGET_CLASSES)
            .props(f'data-value="{str_value}"')
        )
        nd_ref[0] = nd
        return

    # str fallback — inline input + expand-to-modal button
    wrapper = (
        ui.element("div")
        .classes(f"flex items-center gap-1 {_WIDGET_CLASSES}")
        .props(f'data-value="{str_value}"')
    )
    with wrapper:
        current_value = [str(value) if value is not None else ""]

        def _str_handler(e, _w=wrapper, _s=make_setter(str), _cv=current_value):
            _cv[0] = str(e.value)
            _s(e)
            _w.props(f'data-value="{str(e.value).encode("unicode_escape").decode()}"')

        def _str_validation(v, _defn=defn):
            return None if _defn.validate(str(v) if v is not None else "") else "Invalid value"

        ui.input(
            value=current_value[0],
            on_change=_str_handler,
            validation=_str_validation,
        ).classes("flex-1 text-xs").props("dense debounce=500")

        def _open_modal(_cv=current_value, _s=make_setter(str), _w=wrapper):
            with ui.dialog() as dlg, ui.card().classes("w-[480px]"):
                ta = ui.textarea(value=_cv[0]).classes("w-full text-xs").props("dense autogrow")

                def _confirm():
                    v = ta.value
                    _cv[0] = v

                    class _Ev:
                        value = v

                    _s(_Ev())
                    _w.props(f'data-value="{v.encode("unicode_escape").decode()}"')
                    dlg.close()

                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Cancel", on_click=dlg.close).props("flat dense")
                    ui.button("OK", on_click=_confirm).props("flat dense")
            dlg.open()

        ui.button(icon="open_in_full", on_click=_open_modal).props("flat dense size=xs").tooltip(
            "Edit in full"
        )


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
                        ui.label(str(exc)).classes("text-xs hw-text-danger px-2").props('data-error="true"')
                return

            # Check validator before setting — descriptors silently reject invalid values
            descriptor = type(obj)._property_fields().get(attr_name)
            if descriptor is not None and not descriptor.validate(coerced):
                if error_container is not None:
                    error_container.clear()
                    with error_container:
                        ui.label(f"Invalid value: {coerced!r}").classes("text-xs hw-text-danger px-2").props(
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
            registry.set_global(key, val, FieldMode.EXPLICIT)
            registry.save_to_toml_debounced()
        except Exception:
            pass

    return handler
