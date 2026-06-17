# haybale_studio/panels/_settings_panel_base.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.settings.enums import SettingMode
from haywire.core.settings.types import get_vec_meta
from haywire.ui.components.number.drag import NumberDrag
from haywire.ui.utils import anchor_cleanup_to_element

if TYPE_CHECKING:
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings import Settings, setting

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
    - Subscribes to *obj* so external changes (another tab / worker / mirror
      propagation) update the rendered widgets in place. The subscription is
      removed when the rendered column leaves the DOM.
    """

    fields = type(obj)._property_settings()
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

    updaters: dict[str, Callable[[], None]] = {}

    column = ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE)
    with column:
        for category, group in _group_by_category(sorted_fields, key=lambda item: item[1]._category):
            with hui.category_group(category):
                for attr_name, defn in group:
                    _render_reactive_field_row(obj, attr_name, defn, updaters)

    def _on_model_change(name: str, value: Any, old: Any) -> None:
        # Dispatch by field name to that row's in-place updater. Only Case-3
        # mutations happen inside, so this is safe even when fired from another
        # session's asyncio task (cross-tab write).
        updater = updaters.get(name)
        if updater is not None:
            updater()

    obj.subscribe(_on_model_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path. Mirrors
    # BaseWidget.render() calling on_model_changed() once after wiring dispatch.
    for _updater in updaters.values():
        _updater()

    # Tear down the subscription when the column leaves the DOM (redraw via
    # content.clear() or page close).
    anchor_cleanup_to_element(column, lambda: obj.unsubscribe(_on_model_change))


def render_schema(schema_cls: type["Settings"], registry: "SettingsRegistry") -> None:
    """Render only the fields declared on *schema_cls* as labelled form rows.

    Uses the schema's own _property_settings() so that keys registered under the
    same namespace prefix by other code (e.g. dynamic library keys) are not
    accidentally included.
    """
    prop_fields = schema_cls._property_settings()
    defns = {
        defn._setting_key: defn
        for defn in prop_fields.values()
        if defn._setting_key and registry.has_definition(defn._setting_key)
    }
    if not defns:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    sorted_defns = sorted(
        defns.values(),
        key=lambda d: ("" if d._category.lower() == "root" else d._category, d._order, d._setting_key),
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
        key=lambda d: ("" if d._category.lower() == "root" else d._category, d._order, d._setting_key),
    )
    _render_definitions(sorted_defns, registry)


def _render_definitions(sorted_defns: list, registry: "SettingsRegistry") -> None:
    """Render a pre-sorted list of field descriptors grouped by category."""
    with ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE):
        for category, group in _group_by_category(sorted_defns):
            with hui.category_group(category):
                for defn in group:
                    key = defn._setting_key
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


def _render_reactive_field_row(
    obj: "Settings",
    attr_name: str,
    defn: "setting",
    updaters: dict[str, Callable[[], None]],
) -> None:
    """Render a single reactive field row.

    Registers an entry in *updaters* keyed by ``attr_name``: a zero-arg callback
    that re-reads the current model value and applies it to the rendered widget
    and override chrome IN PLACE (no element rebuild), so external changes to the
    model (other tab / worker / mirror) are reflected.
    """

    is_mirrored = bool(defn._mirror_key)

    def _label_text(locally_set: bool) -> str:
        base = defn._label or attr_name
        return f"• {base}" if (is_mirrored and locally_set) else base

    is_locally_overridden = is_mirrored and obj.is_locally_set(attr_name)

    label: Any = None
    reset_btn: Any = None
    value_apply: Callable[[Any], None] | None = None

    def _render_label():
        nonlocal label, reset_btn

        def _on_reset_click():
            obj.reset(attr_name)
            # reset() fires _on_property_change -> the subscription updater
            # refreshes value + chrome in place; nothing else to do here.

        with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
            label = ui.label(_label_text(is_locally_overridden)).classes("text-xs truncate")
            if defn._description:
                label.tooltip(defn._description)
            reset_btn = (
                ui.button(icon=hui.icon.reset)
                .props("flat dense size=xs")
                .tooltip("Reset to global default")
                .on("click", _on_reset_click)
            )
            reset_btn.set_visibility(is_mirrored and is_locally_overridden)

    vec_meta = get_vec_meta(defn._type)
    if vec_meta is not None:
        # _render_vec_field_rows returns an apply(value) updater for in-place
        # external sync of each component NumberDrag.
        value_apply = _render_vec_field_rows(
            defn._label or attr_name,
            defn._description,
            vec_meta,
            getattr(obj, attr_name),
            _make_reactive_setter(obj, attr_name),
            attr_name,
            render_label=_render_label,
        )
    else:
        needs_manual_error = defn._type in (int, float) or defn._type is bool
        error_container = ui.element("div").classes("w-full") if needs_manual_error else None

        with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"'):
            _render_label()
            value_apply = _render_widget_impl(
                defn,
                getattr(obj, attr_name),
                _make_reactive_setter(obj, attr_name, error_container),
            )

    def _apply_external():
        if value_apply is not None:
            value_apply(getattr(obj, attr_name))
        if is_mirrored:
            locally_set = obj.is_locally_set(attr_name)
            if label is not None:
                label.set_text(_label_text(locally_set))
            if reset_btn is not None:
                reset_btn.set_visibility(locally_set)

    updaters[attr_name] = _apply_external


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
) -> Callable[[Any], None]:
    """Render a vector field as a tight column of rows aligned to the panel grid.

    Layout per row:  [field label / spacer]  [X/Y/Z]  [NumberDrag]

    render_label: optional callable that renders the label cell on row 0 (used by
    reactive rows to inject the reset button inline after the label text).

    Returns an ``apply(value)`` callback that updates each component NumberDrag in
    place when the model changes externally.
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
        value: list

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
    component_nds: list[NumberDrag] = []

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
                    nd = NumberDrag(
                        value=coerce(current[i]),
                        on_change=_make_component_setter(i),
                        **nd_kwargs,
                    ).classes("flex-1")
                    component_nds.append(nd)

    def _apply_vec(v, _nds=component_nds, _c=coerce, _len=vec_meta.length, _cur=current):
        seq = list(v) if v is not None else [0] * _len
        while len(seq) < _len:
            seq.append(0)
        for i, nd in enumerate(_nds):
            coerced = _c(seq[i])
            _cur[i] = coerced
            nd.value = coerced
            nd.props(f'data-value="{str(coerced)}"')

    return _apply_vec


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


def _escape(v: Any) -> str:
    """Format a value for safe embedding in a ``data-value`` props string."""
    return (str(v) if v is not None else "").encode("unicode_escape").decode()


def _bind_apply(
    el,
    wrapper,
    *,
    to_widget: "Callable[[Any], Any]" = lambda v: v,
    to_data: "Callable[[Any], str]" = str,
) -> "tuple[Callable[[Any], None], Callable[[Any], str]]":
    """Build a widget's external-sync ``apply()`` plus its ``data-value`` formatter.

    Both directions of sync (the user-driven ``on_change`` handler and the
    model-driven ``apply``) write the same ``data-value`` string, so they share
    one *to_data* per widget and can't drift. ``apply`` assigns ``el.value`` in
    place — NiceGUI "Case 3", safe from any asyncio task; setting a value the
    element already holds is a no-op, so no echo guard is needed.

    Returns ``(apply, to_data)``; the caller passes *to_data* to its on_change
    handler so the encoding lives in exactly one place.
    """

    def apply(v: Any) -> None:
        el.value = to_widget(v)
        wrapper.props(f'data-value="{to_data(v)}"')

    return apply, to_data


def _render_widget_impl(defn: "setting", value: Any, make_setter) -> Callable[[Any], None]:
    """Shared widget dispatch. make_setter(coerce) -> on_change handler.

    Returns an ``apply(value)`` callback that updates the rendered widget IN
    PLACE (NiceGUI "Case 3" — safe from any asyncio task) when the model value
    changes externally. Setting an existing element's ``.value`` to a value it
    already holds is a no-op (BindableProperty / NumberDrag short-circuit), so
    no echo guard is needed.
    """
    # Escape for safe embedding in props strings (newlines etc. break ast.literal_eval)
    str_value = _escape(value)

    if defn._widget == "label":
        # label has no .value (set_text, not BindableProperty), so it can't go
        # through _bind_apply.
        lbl = (
            ui.label(str_value)
            .classes(f"text-xs text-right truncate hw-text-muted {_WIDGET_CLASSES}")
            .props(f'data-value="{str_value}"')
        )

        def _apply_label(v, _lbl=lbl):
            s = _escape(v)
            _lbl.set_text(s)
            _lbl.props(f'data-value="{s}"')

        return _apply_label

    if defn._widget == "color":
        wrapper = ui.element("div").classes(_WIDGET_CLASSES).props(f'data-value="{str_value}"')

        def _color(v):
            return v or "#ffffff"

        with wrapper:

            def _color_handler(e, _w=wrapper, _s=make_setter(str)):
                _w.props(f'data-value="{e.value}"')
                _s(e)

            color_el = (
                ui.color_input(value=value or "#ffffff")
                .classes("w-full")
                .props("dense hide-bottom-space")
                .on_value_change(_color_handler)
            )

        apply, _ = _bind_apply(color_el, wrapper, to_widget=_color, to_data=_color)
        return apply

    resolved_choices = defn.choices
    if resolved_choices is not None:
        wrapper = (
            ui.element("div")
            .classes(f"{_WIDGET_CLASSES} overflow-hidden")
            .props(f'data-value="{str_value}"')
        )
        options_keys = (
            resolved_choices if isinstance(resolved_choices, list) else list(resolved_choices.keys())
        )

        def _select_widget(v, _keys=options_keys):
            return v if v in _keys else None

        with wrapper:

            def _select_handler(e, _w=wrapper, _s=make_setter(lambda v: v)):
                _s(e)
                _w.props(f'data-value="{str(e.value)}"')

            select_el = (
                ui.select(
                    options=resolved_choices,
                    value=_select_widget(value),
                )
                .classes("w-full text-xs")
                .props("dense hide-bottom-space")
                .on_value_change(_select_handler)
            )

        apply, _ = _bind_apply(select_el, wrapper, to_widget=_select_widget)
        return apply

    if defn._type is bool:
        wrapper = ui.element("div").props(f'data-value="{str(bool(value)).lower()}"')

        def _bool_data(v):
            return str(bool(v)).lower()

        with wrapper:

            def _bool_handler(e, _w=wrapper, _s=make_setter(bool), _fmt=_bool_data):
                _s(e)
                _w.props(f'data-value="{_fmt(e.value)}"')

            switch_el = ui.switch(value=bool(value)).props("dense").on_value_change(_bool_handler)

        apply, _ = _bind_apply(switch_el, wrapper, to_widget=bool, to_data=_bool_data)
        return apply

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

        def _number_widget(v, _c=coerce):
            return _c(v) if v is not None else 0

        class _E:
            __slots__ = ("value",)
            value: Any

        nd_ref: list[NumberDrag | None] = [None]

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

        # NumberDrag carries its own div, so apply targets the element itself.
        apply, _ = _bind_apply(nd, nd, to_widget=_number_widget, to_data=lambda v: str(_number_widget(v)))
        return apply

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
            _w.props(f'data-value="{_escape(e.value)}"')

        def _str_validation(v, _defn=defn):
            return None if _defn.validate(str(v) if v is not None else "") else "Invalid value"

        input_el = (
            ui.input(
                value=current_value[0],
                on_change=_str_handler,
                validation=_str_validation,
            )
            .classes("flex-1 text-xs")
            .props("dense debounce=500")
        )

        def _open_modal(_cv=current_value, _s=make_setter(str), _w=wrapper):
            with ui.dialog() as dlg, hui.dialog_card("w-[480px]"):
                ta = ui.textarea(value=_cv[0]).classes("w-full text-xs").props("dense autogrow")

                def _confirm():
                    v = ta.value
                    _cv[0] = v

                    class _Ev:
                        value = v

                    _s(_Ev())
                    _w.props(f'data-value="{_escape(v)}"')
                    dlg.close()

                hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
            dlg.open()

        ui.button(icon=hui.icon.expand_full, on_click=_open_modal).props("flat dense size=xs").tooltip(
            "Edit in full"
        )

    # str carries an extra mirror-cell (the modal reads current_value[0]), so its
    # apply updates that too — otherwise it's the same in-place sync as the rest.
    def _apply_str(v, _w=wrapper, _el=input_el, _cv=current_value):
        s = str(v) if v is not None else ""
        _cv[0] = s
        _el.value = s
        _w.props(f'data-value="{_escape(s)}"')

    return _apply_str


# ---------------------------------------------------------------------------
# Setter factories
# ---------------------------------------------------------------------------


def _make_reactive_setter(obj: "Settings", attr_name: str, error_container=None):
    """Return a make_setter(coerce) factory that writes to a Settings instance.

    Mirror override state (• prefix / reset button) and value display are kept in
    sync by the model subscription wired in ``render_settings`` (which calls each
    row's in-place updater), so the setter no longer rebuilds the row itself.

    No echo guard here: ``setting.__set__`` short-circuits a write equal to the
    field's resolved value (no callback, no phantom override), so the cross-tab
    apply() → widget.value → on_change → setattr loop terminates at the model.
    """

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
            descriptor = type(obj)._property_settings().get(attr_name)
            if descriptor is not None and not descriptor.validate(coerced):
                if error_container is not None:
                    error_container.clear()
                    with error_container:
                        ui.label(f"Invalid value: {coerced!r}").classes("text-xs hw-text-danger px-2").props(
                            'data-error="true"'
                        )
                return

            setattr(obj, attr_name, coerced)

            if error_container is not None:
                error_container.clear()

        return handler

    return make_setter


def _make_setter(registry: "SettingsRegistry", key: str, coerce):
    """Return an on_change handler that writes *key* to the registry workspace tier."""

    def handler(e):
        try:
            val = coerce(e.value)
            if val is None:
                return
            registry.set_global(key, val, SettingMode.EXPLICIT)
            registry.save_to_toml_debounced()
        except Exception:
            pass

    return handler
