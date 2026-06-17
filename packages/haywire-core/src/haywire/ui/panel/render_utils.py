# haywire/ui/panel/render_utils.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.

The module reads top-to-bottom as a waterfall:

    1. Entry points     render_settings / render_schema / render_keys
    2. Collect & group  sort fields, group by category, lay out the column
    3. Row rendering     one label + widget row (reactive instance / registry)
    4. Choose+draw+link  _build_field_widget: pick the widget, build it, wire
                         its on_change, return an apply(value) sync hook
    5. Widget catalog    _WidgetSpec + the per-widget build specs/hooks
    6. Setters           make-setter factories (instance vs. registry tier)

Every field flows through the same four stages. Stage 4 always returns an
``apply(value)`` callback that mutates the existing widget in place (NiceGUI
"Case 3"); the reactive path stores it for external-change sync, the registry
path discards it.
"""

from __future__ import annotations

from dataclasses import dataclass
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


# ===========================================================================
# 1. Entry points
# ===========================================================================


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
        key=lambda item: _category_sort_key(item[1]._category, item[1]._order, item[0]),
    )

    # attr_name -> zero-arg updater that re-reads the model and applies it to the
    # widget + override chrome in place. Populated by _render_reactive_field_row.
    updaters: dict[str, Callable[[], None]] = {}

    column = _render_grouped(
        sorted_fields,
        category_of=lambda item: item[1]._category,
        render_one=lambda item: _render_reactive_field_row(obj, item[0], item[1], updaters),
    )

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

    _render_definitions(_sort_definitions(defns.values()), registry)


def render_keys(prefix: str, registry: "SettingsRegistry") -> None:
    """Render all registry keys whose full key starts with *prefix*.

    Intended for dynamically registered keys (e.g. per-library log levels)
    that are not declared on any schema class. The category label is derived
    from the key structure via the category group.
    """
    match_prefix = prefix + "."
    defns = {key: defn for key, defn in registry.all_definitions().items() if key.startswith(match_prefix)}
    if not defns:
        ui.label(f"No fields found under: {prefix}.*").classes("text-xs hw-text-muted px-2 py-1")
        return

    _render_definitions(_sort_definitions(defns.values()), registry)


# ===========================================================================
# 2. Collect & group
# ===========================================================================


def _category_sort_key(category: str, order: int, tiebreak: str) -> tuple[str, int, str]:
    """Shared (category, order, name) sort key. ``root`` sorts before all others."""
    return ("" if category.lower() == "root" else category, order, tiebreak)


def _sort_definitions(defns) -> list:
    """Sort a collection of field descriptors by (category, order, setting_key)."""
    return sorted(
        defns,
        key=lambda d: _category_sort_key(d._category, d._order, d._setting_key),
    )


def _group_by_category(items: list, key=lambda x: x._category) -> list[tuple[str, list]]:
    """Group a pre-sorted list of descriptors by category, preserving order."""
    return [(cat, list(grp)) for cat, grp in groupby(items, key=key)]


def _render_grouped(sorted_items, category_of, render_one) -> Any:
    """Lay out *sorted_items* as a settings column, grouped into category sections.

    Returns the outer ``ui.column`` so callers can anchor teardown to it.
    *render_one* is called once per item, inside its category group.
    """
    column = ui.column().classes("w-full gap-0 compact-fields").style(_COLUMN_STYLE)
    with column:
        for category, group in _group_by_category(sorted_items, key=category_of):
            with hui.category_group(category):
                for item in group:
                    render_one(item)
    return column


def _render_definitions(sorted_defns: list, registry: "SettingsRegistry") -> None:
    """Render a pre-sorted list of registry-backed field descriptors.

    Subscribes to the registry so that external changes (TOML reload, cross-tab
    writes) update the rendered widgets in place without a full redraw.
    """
    # key -> apply(value) callback for in-place widget updates
    appliers: dict[str, Callable[[Any], None]] = {}

    def _render_one(defn) -> None:
        key = defn._setting_key
        try:
            value, _ = registry.resolve(key)
        except KeyError:
            return
        attr_name = defn._attr_name or key.split(".")[-1]
        apply = _render_field_row(
            defn._label or attr_name,
            defn._description,
            defn,
            value,
            lambda coerce, k=key: _make_setter(registry, k, coerce),
            attr_name=attr_name,
        )
        if apply is not None:
            appliers[key] = apply

    column = _render_grouped(sorted_defns, category_of=lambda d: d._category, render_one=_render_one)

    def _on_registry_change(key: str, _value: Any) -> None:
        apply = appliers.get(key)
        if apply is None:
            return
        try:
            resolved, _ = registry.resolve(key)
            apply(resolved)
        except KeyError:
            pass

    # Subscribe at the common namespace prefix so we receive only the keys we rendered.
    all_keys = list(appliers.keys())
    if all_keys:
        parts_list = [k.split(".") for k in all_keys]
        min_len = min(len(p) for p in parts_list)
        namespace: str | None = None
        for depth in range(min_len, 0, -1):
            prefix = ".".join(parts_list[0][:depth])
            if all(".".join(p[:depth]) == prefix for p in parts_list):
                namespace = prefix
                break
        registry.subscribe(namespace, _on_registry_change)
        anchor_cleanup_to_element(column, lambda: registry.unsubscribe(namespace, _on_registry_change))


# ===========================================================================
# 3. Row rendering
# ===========================================================================


def _render_field_row(
    label_text: str, description: str, defn, value, make_setter, attr_name: str = ""
) -> Callable[[Any], None]:
    """Render a single label + widget row (registry path); return apply(value) for external sync."""
    vec_meta = get_vec_meta(defn._type)
    if vec_meta is not None:
        return _render_vec_field_rows(label_text, description, vec_meta, value, make_setter, attr_name)
    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else ""):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        return _build_field_widget(defn, value, make_setter)


def _render_reactive_field_row(
    obj: "Settings",
    attr_name: str,
    defn: "setting",
    updaters: dict[str, Callable[[], None]],
) -> None:
    """Render a single reactive field row (instance path).

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
            value_apply = _build_field_widget(
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


# ===========================================================================
# 4. Choose -> draw -> link
# ===========================================================================


def _build_field_widget(defn: "setting", value: Any, make_setter) -> Callable[[Any], None]:
    """Choose, draw, and link the widget for *defn*; return its ``apply(value)``.

    This is the single CHOOSE -> DRAW -> LINK stage every field passes through.
    ``make_setter(coerce)`` yields the on_change handler. The returned
    ``apply(value)`` updates the rendered widget IN PLACE (NiceGUI "Case 3" —
    safe from any asyncio task) when the model value changes externally.

    Routing:
    - ``label``      -> no ``.value`` (set_text), built here directly.
    - simple value   -> a ``_WidgetSpec`` (color/select/bool/number), wired by
                        ``_wire_widget`` — the shared draw+link path.
    - ``str``        -> inline input + expand-to-modal, built here (carries an
                        extra modal mirror-cell, so it isn't a plain spec).
    """
    if defn._widget == "label":
        return _build_label_widget(value)

    spec = _value_widget_spec(defn)
    if spec is not None:
        return _wire_widget(spec, value, make_setter)

    return _build_str_widget(defn, value, make_setter)


def _wire_widget(spec: "_WidgetSpec", value: Any, make_setter) -> Callable[[Any], None]:
    """Build a value-carrying widget from *spec* and return its ``apply(value)``.

    The single on_change (coerce → setter → write ``data-value``) and the
    model-driven ``apply`` both encode through ``spec.to_data`` against the same
    host, so they can't drift. ``apply`` assigns ``el.value`` in place (NiceGUI
    "Case 3", safe from any asyncio task); a value the element already holds is a
    no-op, so no echo guard is needed.
    """
    set_value = make_setter(spec.coerce)

    if spec.self_hosting:
        host: Any = None  # set after build; NumberDrag is its own data-value host

        def on_change(e: Any) -> None:
            set_value(_Event(spec.coerce(spec.read_event(e))))

        el = spec.build(value, on_change).classes(spec.classes)
        host = el
    else:
        host = ui.element("div").classes(spec.classes).props(f'data-value="{spec.to_data(value)}"')

        def on_change(e: Any) -> None:
            coerced = spec.coerce(spec.read_event(e))
            set_value(_Event(coerced))
            host.props(f'data-value="{spec.to_data(coerced)}"')

        with host:
            el = spec.build(value, on_change)

    def apply(v: Any) -> None:
        el.value = spec.to_widget(v)
        if not spec.self_hosting:
            host.props(f'data-value="{spec.to_data(v)}"')

    return apply


# ===========================================================================
# 5. Widget catalog
# ===========================================================================


@dataclass(frozen=True)
class _WidgetSpec:
    """Everything that varies between a value-carrying settings widget.

    Everything NOT here — the ``data-value`` host, the initial prop, the shared
    coerce→set→write-data-value ``on_change``, and the returned ``apply`` — lives
    once in ``_wire_widget``. ``apply`` and the handler both encode through
    ``to_data``, so the two sync directions cannot drift.

    - ``build(value, on_change)`` constructs the nicegui element, wiring
      *on_change* however that element expects (``.on_value_change`` for stock
      widgets, the ``on_change=`` ctor arg for NumberDrag).
    - ``self_hosting`` widgets (NumberDrag) maintain their own ``data-value``
      prop, so ``_wire_widget`` writes neither a wrapper nor a prop for them.
    """

    build: Callable[[Any, Callable[[Any], None]], Any]
    coerce: Callable[[Any], Any] = lambda v: v
    to_widget: Callable[[Any], Any] = lambda v: v
    to_data: Callable[[Any], str] = str
    read_event: Callable[[Any], Any] = lambda e: e.value
    classes: str = _WIDGET_CLASSES
    self_hosting: bool = False


def _value_widget_spec(defn: "setting") -> "_WidgetSpec | None":
    """Return the spec for *defn*'s value-carrying widget, or None.

    Returns None for the two widgets that are NOT plain value-carrying specs and
    are built directly in ``_build_field_widget``: ``label`` (no ``.value``) and
    ``str`` (carries an extra modal mirror-cell).
    """
    if defn._widget == "color":
        to_color = lambda v: v or "#ffffff"  # noqa: E731
        return _WidgetSpec(
            build=lambda v, oc: ui.color_input(value=to_color(v))
            .classes("w-full")
            .props("dense hide-bottom-space")
            .on_value_change(oc),
            coerce=str,
            to_widget=to_color,
            to_data=to_color,
        )

    choices = defn.choices
    if choices is not None:
        keys = choices if isinstance(choices, list) else list(choices.keys())
        in_keys = lambda v: v if v in keys else None  # noqa: E731
        return _WidgetSpec(
            build=lambda v, oc: ui.select(options=choices, value=in_keys(v))
            .classes("w-full text-xs")
            .props("dense hide-bottom-space")
            .on_value_change(oc),
            to_widget=in_keys,
            classes=f"{_WIDGET_CLASSES} overflow-hidden",
        )

    if defn._type is bool:
        return _WidgetSpec(
            build=lambda v, oc: ui.switch(value=bool(v)).props("dense").on_value_change(oc),
            coerce=bool,
            to_widget=bool,
            to_data=lambda v: str(bool(v)).lower(),
            classes="",
        )

    if defn._type in (int, float):
        return _number_spec(defn)

    return None


def _number_spec(defn: "setting") -> "_WidgetSpec":
    """Build the NumberDrag spec for an int/float field, deriving step/precision."""
    coerce = defn._type
    kwargs: dict = {}
    if defn._min is not None:
        kwargs["min"] = defn._min
    if defn._max is not None:
        kwargs["max"] = defn._max
    if defn._type is int:
        kwargs["step"] = 1
        kwargs["precision"] = 0
    else:
        kwargs["step"] = _float_step_from_default(defn._default)

    def _build(v, on_change, _k=kwargs):
        return NumberDrag(value=coerce(v) if v is not None else 0, on_change=on_change, **_k)

    return _WidgetSpec(
        build=_build,
        coerce=coerce,  # NumberDrag delivers its raw value via e.args (read_event)
        to_widget=lambda v: coerce(v) if v is not None else 0,
        read_event=lambda e: e.args,
        self_hosting=True,
    )


def _build_label_widget(value: Any) -> Callable[[Any], None]:
    """Display-only ``label`` widget — no ``.value`` (set_text, not BindableProperty)."""
    str_value = _escape(value)
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


def _build_str_widget(defn: "setting", value: Any, make_setter) -> Callable[[Any], None]:
    """str fallback — inline input + expand-to-modal button.

    str is the one widget that carries extra state: a ``current_value`` mirror
    cell the modal reads, kept in sync by both the inline handler and ``apply``.
    """
    wrapper = (
        ui.element("div")
        .classes(f"flex items-center gap-1 {_WIDGET_CLASSES}")
        .props(f'data-value="{_escape(value)}"')
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
                    _s(_Event(v))
                    _w.props(f'data-value="{_escape(v)}"')
                    dlg.close()

                hui.dialog_actions(on_confirm=_confirm, on_cancel=dlg.close)
            dlg.open()

        ui.button(icon=hui.icon.expand_full, on_click=_open_modal).props("flat dense size=xs").tooltip(
            "Edit in full"
        )

    def _apply_str(v, _w=wrapper, _el=input_el, _cv=current_value):
        s = str(v) if v is not None else ""
        _cv[0] = s
        _el.value = s
        _w.props(f'data-value="{_escape(s)}"')

    return _apply_str


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

    def _make_component_setter(idx, _cv=current, _ms=make_setter, _c=coerce):
        handler = _ms(lambda v: v)

        def _on_change(e, _i=idx, _h=handler, _cv=_cv, _c=_c):
            _cv[_i] = _c(e.args)
            _h(_Event(list(_cv)))

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
        # NumberDrag.value's setter rewrites its own data-value prop, so we only
        # assign .value here — no separate props() write needed.
        seq = list(v) if v is not None else [0] * _len
        while len(seq) < _len:
            seq.append(0)
        for i, nd in enumerate(_nds):
            coerced = _c(seq[i])
            _cur[i] = coerced
            nd.value = coerced

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


class _Event:
    """Minimal change-event stand-in: setters read only ``.value``."""

    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value


# ===========================================================================
# 6. Setters
# ===========================================================================


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
