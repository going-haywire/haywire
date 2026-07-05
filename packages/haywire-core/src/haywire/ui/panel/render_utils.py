# haywire/ui/panel/render_utils.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.

The module reads top-to-bottom as a waterfall:

    1. Entry points     render_settings / render_schema / render_keys
    2. Collect & group  sort fields, group by category, lay out the column
    3. Row rendering     one label + widget row (reactive instance / registry)
    4. Resolve widget   _resolve_widget_instance: resolve a shared BaseWidget
                         by defn.widget_key (stamped once at __set_name__, ADR
                         0017), build it against a SettingWidgetModel wired to
                         an on_edit closure; returns None for a real widget, or
                         the label fallback's apply(value) sync hook
    5. Write policy      on_edit closure factories (instance vs. registry tier)

Every field flows through the same stages. Stage 4 returns an ``apply(value)``
callback used ONLY by the label fallback for an unknown widget key (no cell
binding to hear); real widgets bind the field's shared cell directly and hear
writes via ``on_changed`` (ADR 0016) — the reactive path still keeps its own
override-chrome (• prefix / reset button) in sync via the ``updaters`` dict. That
chrome shows for any locally-set field, mirror or plain, unless a promoted inlet
owns the value (the graph drives it, so reset is meaningless).
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
    from haywire.core.types.fields import DataField

_ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
_LABEL_CLASSES = "text-xs min-w-0 truncate sf-label"
_WIDGET_CLASSES = "sf-widget"
_COLUMN_STYLE = "container-type: inline-size; container-name: settings-panel;"


# ===========================================================================
# 1. Entry points
# ===========================================================================


def render_settings(obj: "Settings") -> None:
    """Render all ``setting()`` fields of a ``Settings`` instance as labelled form rows.

    - Fields with ``read_only=True`` are skipped (not rendered).
    - Any locally-set field shows a • dirty prefix and a reset button (unless a
      promoted inlet owns the value): "Reset to global default" for a ``mirrors=``
      field, "Reset to default" for a plain one.
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

    Each widget binds the registry-owned cell for its key (ADR 0016), so
    external changes (JSON reload, cross-tab writes) show live via the cell's
    own event — no registry subscription, re-resolve loop, or per-widget
    throwaway field.
    """

    def _render_one(defn) -> None:
        key = defn._setting_key
        try:
            cell = registry.cell_for(key)
        except KeyError:
            return
        attr_name = defn._attr_name or key.split(".")[-1]
        _render_field_row(
            defn._label or attr_name,
            defn._description,
            defn,
            registry,
            key,
            attr_name=attr_name,
            cell=cell,
        )

    _render_grouped(sorted_defns, category_of=lambda d: d._category, render_one=_render_one)


# ===========================================================================
# 3. Row rendering
# ===========================================================================


def _render_field_row(
    label_text: str,
    description: str,
    defn,
    registry: "SettingsRegistry",
    key: str,
    attr_name: str = "",
    cell: "DataField | None" = None,
) -> Callable[[Any], None] | None:
    """Render a single label + widget row (registry path). The widget binds
    *cell* (the registry-owned cell) for live external sync (ADR 0016).

    *error_container* is a block-level element BEFORE the label+widget row,
    not a third flex child inside it (mirrors ``_render_reactive_field_row``):
    as a flex sibling inside the row, its own ``w-full`` would claim a third
    column, squeezing the widget onto a wrapped second line instead of
    sitting beside the label.
    """
    error_container = ui.element("div").classes("w-full")
    on_edit = _registry_on_edit(registry, key, error_container)
    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else ""):
        lbl = ui.label(label_text).classes(_LABEL_CLASSES)
        if description:
            lbl.tooltip(description)
        return _resolve_widget_instance(defn, on_edit, cell=cell)


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

    # Direction- and link-aware promoted row (decision 7bA): an INLET means the
    # graph now owns the value (an incoming edge, or simply having been promoted),
    # so the row goes read-only; an OUTLET keeps the setting as source of truth,
    # so the editable widget stays. Recomputed per render — link-state staleness
    # until the next redraw is accepted (decision Q7), no reactive tracking beyond
    # this per-render check.
    port = obj._node.ports.get(defn.storage_key) if (is_promoted and obj._node is not None) else None
    is_promoted_inlet = False
    promoted_hint = ""
    if port is not None:
        if port.is_inlet():
            is_promoted_inlet = True
            promoted_hint = "driven through inlet" if port.is_linked() else "promoted to inlet"
        else:
            promoted_hint = "promoted to outlet"

    # Override chrome (• dirty prefix + reset button) is shown whenever the field
    # carries a local opinion (_set_keys membership) AND the graph doesn't own its
    # value through a promoted INLET. A promoted OUTLET keeps the setting as source
    # of truth (its widget stays editable), so its chrome stays; an inlet-driven or
    # inlet-promoted row is read-only, so resetting there is meaningless. The mirror
    # gate is gone (decision Q1): plain fields get the same affordance, only the
    # tooltip/meaning differs by field kind.
    def _has_local_opinion() -> bool:
        return obj.is_locally_set(attr_name) and not is_promoted_inlet

    # "Reset to global default" re-seeds a mirror field from the current global and
    # resumes tracking; a plain field has no global — reset restores the descriptor
    # default. reset() already branches this internally; only the wording differs.
    reset_tooltip = "Reset to global default" if is_mirrored else "Reset to default"

    def _label_text(dirty: bool) -> str:
        base = defn._label or attr_name
        return f"• {base}" if dirty else base

    label: Any = None
    reset_btn: Any = None
    value_apply: Callable[[Any], None] | None = None

    def _render_label():
        nonlocal label, reset_btn

        def _on_reset_click():
            obj.reset(attr_name)
            # reset() discards the local opinion but only writes the cell when the
            # value actually changes (old != new). A field that was locally-set yet
            # already equalled its default — e.g. promoted-then-demoted unchanged —
            # fires NO cell event, so the bag subscription driving _refresh_chrome
            # never runs and the • / reset button would linger. Refresh this row's
            # chrome directly so it clears regardless of whether the value moved.
            _refresh_chrome()

        with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
            label = ui.label(_label_text(_has_local_opinion())).classes("text-xs truncate")
            if defn._description:
                label.tooltip(defn._description)
            if promoted_hint:
                (
                    ui.button(icon=hui.icon.promote)
                    .props("flat dense size=xs")
                    .tooltip(promoted_hint)
                )
            else:
                reset_btn = (
                    ui.button(icon=hui.icon.reset)
                    .props("flat dense size=xs")
                    .tooltip(reset_tooltip)
                    .on("click", _on_reset_click)
                )
                reset_btn.set_visibility(_has_local_opinion())

    # Every field — scalars, vectors, color — resolves a shared BaseWidget by its
    # widget_key, stamped once at __set_name__ (see _resolve_widget_instance, ADR
    # 0017). VecWidget handles vec types via widget_config['vec_meta']; the panel
    # no longer special-cases them.
    error_container = ui.element("div").classes("w-full")

    # A column-oriented widget (e.g. VecWidget in row-per-component mode) renders
    # multiple flush component rows; top-align the label against the first row
    # rather than centering it across the whole block. Field-to-field spacing
    # comes uniformly from the parent column's gap (same for scalars and
    # vectors) — no per-field margin, which would compound unevenly between two
    # adjacent vec rows. Scalars keep items-center. Config-driven (ADR 0017): no
    # widget identity named here, just the "orientation" property.
    row_classes = _ROW_CLASSES
    if defn.widget_config.get("properties", {}).get("orientation", "") == "column":
        row_classes = _ROW_CLASSES.replace("items-center", "items-start")

    row_props = f'data-field="{attr_name}"'
    if is_promoted:
        row_props += ' data-promoted="true"'
        if port is not None:
            row_props += f' data-promoted-direction="{"inlet" if is_promoted_inlet else "outlet"}"'

    with ui.row().classes(row_classes).props(row_props):
        _render_label()
        if is_promoted_inlet is False:
            on_edit = _bag_on_edit(obj, attr_name, error_container)
            value_apply = _resolve_widget_instance(defn, on_edit, bag=obj)

    def _refresh_chrome():
        # Real widgets bind the shared cell directly (on_changed, ADR 0016), so
        # re-pushing their value here would be a structural no-op — verified:
        # value_apply is None for every case except the unknown-widget label
        # fallback, which owns no cell subscription of its own and needs this
        # to reflect external changes at all. Everything else in this callback
        # is pure override chrome: the • prefix and reset-button visibility.
        #
        # Applies to plain fields too (decision Q1): editing a plain field's widget
        # writes its cell, and the • / reset must appear live rather than waiting
        # for the next full panel redraw. is_promoted_inlet is a per-render constant
        # (structural, needs a redraw to change), so a cell-value change only flips
        # the is_locally_set half — recomputed here.
        if value_apply is not None:
            value_apply(getattr(obj, attr_name))
        dirty = _has_local_opinion()
        if label is not None:
            label.set_text(_label_text(dirty))
        if reset_btn is not None:
            reset_btn.set_visibility(dirty)

    updaters[attr_name] = _refresh_chrome


# ===========================================================================
# 4. Choose -> draw -> link
# ===========================================================================


def _resolve_widget_instance(
    defn: "setting",
    on_edit: Callable[[Any], None],
    bag: "Settings | None" = None,
    cell: "DataField | None" = None,
) -> Callable[[Any], None] | None:
    """Build the shared ``BaseWidget`` for *defn* via a ``SettingWidgetModel``.

    Falls back to a read-only label when the resolved widget key is unknown, so
    a missing widget never renders a silent blank. The model always binds the
    field's shared ``DataField`` cell (ADR 0016): *cell* when given (the
    registry-owned cell, registry path), else *bag*'s instance cell. Writes
    route through *on_edit* — the write-policy closure (``_bag_on_edit`` /
    ``_registry_on_edit``) — never raw into the cell.

    Returns ``None`` for a real widget: it hears cell writes directly via
    ``on_changed`` (ADR 0016), so there is nothing left for a caller to push.
    Returns the label fallback's ``apply(value)`` when the widget key is
    unknown, since that display has no cell binding of its own.
    """
    from haywire.ui.widget.globals import get_widget_class
    from haywire.ui.panel.setting_widget_model import SettingWidgetModel

    key = defn.widget_key
    widget_cls = get_widget_class(key)
    if widget_cls is None:
        shared_cell = cell if cell is not None else (bag._cell_for(defn) if bag is not None else None)
        value = shared_cell.get_value() if shared_cell is not None else None
        return _build_label_widget(value)

    shared_cell = cell if cell is not None else (bag._cell_for(defn) if bag is not None else None)
    assert shared_cell is not None, f"no cell for setting widget {defn._attr_name!r} (ADR 0016)"

    model = SettingWidgetModel(
        field_id=defn._attr_name or defn._label,
        widget_config=defn.widget_config,
        cell=shared_cell,
        on_edit=on_edit,
    )

    # Render the widget inside an sf-widget cell so it sits in the value column
    # next to the sf-label (CSS in app/shell.py sizes the two side by side). Port
    # widgets are authored w-full to fill a node card; nesting them in the cell
    # makes that "100% of the cell" instead of "100% of the row" (which would win
    # the class-vs-class width fight and wrap the control below the label).
    with ui.element("div").classes(f"{_WIDGET_CLASSES} min-w-0") as widget_cell:
        widget = widget_cls(model)
        widget.render()

    # Tear the widget's cell subscription down when its row leaves the DOM.
    # BaseWidget.render() only anchors cleanup to *client* disconnect, not to
    # element deletion — so a panel re-render (e.g. promoting the field to an
    # inlet, which rebuilds this row) would otherwise leave the old widget's
    # _model_dispatch_cb subscribed to the shared cell. A later edit then fires
    # sync_to_view() against the deleted element (NiceGUI "element deleted but
    # still being used"). cleanup() is idempotent, so this is safe alongside
    # the client-disconnect hook.
    anchor_cleanup_to_element(widget_cell, widget.cleanup)

    return None


def _build_label_widget(value: Any) -> Callable[[Any], None]:
    """Display-only ``label`` widget — no ``.value`` (set_text, not BindableProperty).

    ``apply(value)`` exists solely for this label fallback (no cell binding);
    real widgets hear the cell directly (ADR 0016).
    """
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


# ===========================================================================
# 5. Write policy — on_edit closures
# ===========================================================================


def _bag_on_edit(obj: "Settings", attr_name: str, error_container) -> Callable[[Any], None]:
    """Write policy for the instance path: validate → setattr → error chrome."""

    def on_edit(value: Any) -> None:
        descriptor = type(obj)._property_settings().get(attr_name)
        if descriptor is not None and not descriptor.validate(value):
            error_container.clear()
            with error_container:
                ui.label(f"Invalid value: {value!r}").classes("text-xs hw-text-danger px-2").props(
                    'data-error="true"'
                )
            return
        setattr(obj, attr_name, value)
        error_container.clear()

    return on_edit


def _registry_on_edit(registry: "SettingsRegistry", key: str, error_container) -> Callable[[Any], None]:
    """Write policy for the registry path: set_global → debounced save → error chrome.

    Surfaces failures instead of swallowing them (review finding #6):
    set_global raises ValueError on validator rejection and KeyError on a
    dropped definition (hot-reload race)."""

    def on_edit(value: Any) -> None:
        try:
            registry.set_global(key, value)
            registry.save_to_json_debounced()
        except (KeyError, ValueError) as exc:
            error_container.clear()
            with error_container:
                ui.label(str(exc)).classes("text-xs hw-text-danger px-2").props('data-error="true"')
            return
        error_container.clear()

    return on_edit
