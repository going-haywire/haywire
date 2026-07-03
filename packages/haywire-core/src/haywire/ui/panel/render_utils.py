# haywire/ui/panel/render_utils.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.

The module reads top-to-bottom as a waterfall:

    1. Entry points     render_settings / render_schema / render_keys
    2. Collect & group  sort fields, group by category, lay out the column
    3. Row rendering     one label + widget row (reactive instance / registry)
    4. Resolve widget   _build_field_widget -> _resolve_widget_instance: resolve a
                         shared BaseWidget by resolved_widget_key, build it against
                         a SettingWidgetModel, return an apply(value) sync hook
    5. Setters           make-setter factories (instance vs. registry tier)

Every field flows through the same stages. Stage 4 returns an ``apply(value)``
callback that pushes an external model change into the widget in place (NiceGUI
"Case 3"); the reactive path stores it for external-change sync, the registry
path discards it.
"""

from __future__ import annotations

from itertools import groupby
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.ui import elements as hui
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
    column = ui.column().classes("w-full compact-fields sf-field-list").style(_COLUMN_STYLE)
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
    # A promoted field is driven by a DATA port (see haywire.core.node.promotion).
    # The row is marked so the panel doesn't silently present an editable widget for
    # a value the graph now owns; the value display stays live (the setting and the
    # port share one cell, so getattr(obj, attr_name) reflects the port). The port id
    # is the truth — _promoted_port_id was retired (ADR 0014).
    from haywire.core.node.promotion import is_field_promoted

    is_promoted = is_field_promoted(obj, attr_name)

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

    # Every field — scalars, vectors, color — resolves a shared BaseWidget by its
    # resolved_widget_key (see _resolve_widget_instance). VecWidget handles vec
    # types via widget_config['vec_meta']; the panel no longer special-cases them.
    error_container = ui.element("div").classes("w-full")

    # A column-oriented VecWidget renders multiple flush component rows; top-align
    # the label against the first row rather than centering it across the whole
    # block. Field-to-field spacing comes uniformly from the parent column's gap
    # (same for scalars and vectors) — no per-field margin, which would compound
    # unevenly between two adjacent vec rows. Scalars keep items-center.
    row_classes = _ROW_CLASSES
    if defn.resolved_widget_key == "builtin:widget:VecWidget":
        orientation = defn.resolved_widget_config.get("properties", {}).get("orientation", "column")
        if orientation == "column":
            row_classes = _ROW_CLASSES.replace("items-center", "items-start")

    row_props = f'data-field="{attr_name}"'
    if is_promoted:
        row_props += ' data-promoted="true"'

    with ui.row().classes(row_classes).props(row_props):
        _render_label()
        value_apply = _build_field_widget(
            defn,
            getattr(obj, attr_name),
            _make_reactive_setter(obj, attr_name, error_container),
            bag=obj,
        )
        if is_promoted:
            ui.label("↳ driven by inlet").classes("text-xs hw-text-muted px-2").props(
                'data-promoted-hint="true"'
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


def _build_field_widget(
    defn: "setting", value: Any, make_setter, bag: "Settings | None" = None
) -> Callable[[Any], None]:
    """Resolve, build, and link the shared widget for *defn*; return ``apply(value)``.

    Every field resolves a ``BaseWidget`` by ``defn.resolved_widget_key`` (type
    default, or desugared from ``choices``/``widget=``). The widget owns the
    control; the panel keeps the surrounding chrome (label, override •/reset,
    category groups, error container). ``make_setter(coerce)`` yields the
    on_change handler; the returned ``apply(value)`` pushes an external model
    change into the widget in place. When *bag* is given, the widget binds its
    shared cell for display (registry/edge changes show live).
    """
    return _resolve_widget_instance(defn, value, make_setter, bag=bag)


def _resolve_widget_instance(
    defn: "setting", value: Any, make_setter, bag: "Settings | None" = None
) -> Callable[[Any], None]:
    """Build the shared ``BaseWidget`` for *defn* via a ``SettingWidgetModel``.

    Falls back to a read-only label when the resolved widget key is unknown, so a
    missing widget never renders a silent blank. When *bag* is given, the model
    binds the bag's shared ``DataField`` cell for display (write still routes
    through the descriptor via *make_setter*).
    """
    from haywire.ui.widget.globals import get_widget_class
    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

    key = defn.resolved_widget_key
    widget_cls = get_widget_class(key)
    if widget_cls is None:
        return _build_label_widget(value)

    # Bind the bag's shared cell for display so a registry/edge write into it shows
    # live; None for the registry path (no bag) keeps the throwaway-field fallback.
    shared_cell = bag._cell_for(defn) if bag is not None else None

    model = SettingWidgetModel(
        field_id=defn._attr_name or defn._label,
        itype=defn._type,
        value=value,
        widget_config=defn.resolved_widget_config,
        make_setter=make_setter,
        field=shared_cell,
    )

    # Render the widget inside an sf-widget cell so it sits in the value column
    # next to the sf-label (CSS in app/shell.py sizes the two side by side). Port
    # widgets are authored w-full to fill a node card; nesting them in the cell
    # makes that "100% of the cell" instead of "100% of the row" (which would win
    # the class-vs-class width fight and wrap the control below the label).
    with ui.element("div").classes(f"{_WIDGET_CLASSES} min-w-0"):
        widget = widget_cls(model)
        widget.render()

    def _apply(v: Any) -> None:
        model.apply_external(v)

    return _apply


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
            registry.set_global(key, val)
            registry.save_to_json_debounced()
        except Exception:
            pass

    return handler
