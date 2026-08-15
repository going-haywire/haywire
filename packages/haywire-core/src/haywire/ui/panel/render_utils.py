# haywire/ui/panel/render_utils.py
"""
Utility collection of renderer functions for
FrameworkSettings / LibrarySettings / NodeSettings schema classes.

The module reads top-to-bottom as a waterfall:

    1. Entry points     render_settings / render_schema / render_keys
    2. Collect & group  sort fields, group by category, lay out the column
    3. Row rendering     one label + widget row (reactive instance / registry)
    4. Resolve widget   _resolve_widget_instance: resolve a shared BaseWidget
                         by defn.widget_key (stamped once at __set_name__),
                         build it against a SettingWidgetModel wired to
                         an on_edit closure; returns None for a real widget, or
                         the label fallback's apply(value) sync hook
    5. Write policy      on_edit closure factories (instance vs. registry tier)

Every field flows through the same stages. Stage 4 returns an ``apply(value)``
callback used ONLY by the label fallback for an unknown widget key (no cell
binding to hear); real widgets bind the field's shared cell directly and hear
writes via ``on_changed``.

BOTH row renderers carry the same override chrome — a • dirty glyph and a
right-click Reset item on the row's label — over different notions of
"overridden", and each keeps it in sync itself (the reactive path via the
``updaters`` dict, the registry path via a per-row registry subscription):

- reactive (instance): overridden = the bag holds a local opinion, mirror or
  plain. Reset restores the global (mirror) or the descriptor default. The
  chrome is suppressed when a promoted inlet owns the value — the graph drives
  it, so reset is meaningless. Promote/Demote share this one menu (see
  ``_build_row_menu``) — there is no other promote surface.
- registry (schema/keys): overridden = the WORKSPACE tier is set, the tier the
  UI writes. Reset clears it and the value falls back through ``resolve()`` to
  the global tier (``~/.haywire/settings.json``, hand-edited, never written by
  the app) or the descriptor default — the menu item is worded from whichever
  it lands on. No promote half: a registry key belongs to no node.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from itertools import groupby
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.core.settings import UiState
from haywire.ui import elements as hui
from haywire.ui.utils import anchor_cleanup_to_element
from haywire.ui.widget.base import DISABLED_STYLE

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.settings.registry import SettingsRegistry
    from haywire.core.settings import Settings, setting
    from haywire.core.types.enums import PortType
    from haywire.core.types.fields import DataField

logger = logging.getLogger(__name__)

_ROW_CLASSES = "w-full items-center justify-between gap-0 px-2"
_WIDGET_CLASSES = "sf-widget"
_COLUMN_STYLE = "container-type: inline-size; container-name: settings-panel;"


# ===========================================================================
# 1. Entry points
# ===========================================================================


def render_settings(obj: "Settings") -> None:
    """Render all ``setting()`` fields of a ``Settings`` instance as labelled form rows.

    - Any locally-set field shows a • dirty prefix and a reset button (unless a
      promoted inlet owns the value): "Reset to global default" for a ``mirrors=``
      field, "Reset to default" for a plain one.
    - A field's ``ui_state`` (``NORMAL``/``DISABLED``/``HIDDEN``)
      controls its chrome: DISABLED renders the widget non-interactive,
      HIDDEN removes the row. ``watch()`` seeds DISABLED — a mirrored field
      renders as a greyed widget, same mechanism as any other disabled field.
    - Subscribes to *obj* so external changes (another tab / worker / mirror
      propagation) update the rendered widgets in place. The subscription is
      removed when the rendered column leaves the DOM.
    """

    fields = type(obj)._property_settings()
    visible_fields = dict(fields)
    if not visible_fields:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    # _property_settings() already yields fields in declaration order (base-first
    # MRO walk over class __dict__, which Python preserves in insertion order) —
    # render in that order directly, no re-sort. Categories are NOT pre-grouped:
    # _render_grouped's groupby only merges CONSECUTIVE same-category entries, so
    # a category interrupted by a different one re-opens as a second section
    # (see internals/superpowers/2026-07-18-settings-panel-ordering-spec.md).
    sorted_fields = list(visible_fields.items())

    # attr_name -> zero-arg updater that re-reads the model and applies it to the
    # widget + override chrome in place. Populated by _render_reactive_field_row.
    updaters: dict[str, Callable[[], None]] = {}

    # Category-group visibility: a section whose rows are ALL effectively
    # HIDDEN hides its wrapper (header included). Derived state only —
    # recomputed from effective_ui_state, never stored per category.
    group_wrappers: dict[str, Any] = {}
    fields_by_category: dict[str, list[str]] = {}
    for _name, _defn in sorted_fields:
        fields_by_category.setdefault(_defn._category, []).append(_name)

    def _refresh_group_visibility(category: str) -> None:
        wrapper = group_wrappers.get(category)
        if wrapper is None:
            return
        names = fields_by_category.get(category, [])
        wrapper.set_visibility(any(obj.effective_ui_state(n) is not UiState.HIDDEN for n in names))

    def _render_one(item: tuple[str, "setting"]) -> None:
        category = item[1]._category

        def _on_applied() -> None:
            _refresh_group_visibility(category)

        _render_reactive_field_row(obj, item[0], item[1], updaters, on_ui_state_applied=_on_applied)

    column = _render_grouped(
        sorted_fields,
        category_of=lambda item: item[1]._category,
        render_one=_render_one,
        group_wrappers=group_wrappers,
    )

    def _on_model_change(name: str, value: Any, old: Any) -> None:
        # Dispatch by field name to that row's in-place updater. Only Case-3
        # mutations happen inside, so this is safe even when fired from another
        # session's asyncio task (cross-tab write).
        updater = updaters.get(name)
        if updater is not None:
            updater()

    def _on_ui_state_change(name: str, _state: UiState) -> None:
        # Same dispatch shape as _on_model_change, arriving on the DEDICATED
        # ui-state channel — set_ui_state never echoes through the cells,
        # so value subscribers (widgets, node live-control handlers, promoted
        # ports) never hear chrome changes.
        updater = updaters.get(name)
        if updater is not None:
            updater()

    obj.subscribe(_on_model_change)
    obj.subscribe_ui_state(_on_ui_state_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path. Mirrors
    # BaseWidget.render() calling on_model_changed() once after wiring dispatch.
    for _updater in updaters.values():
        _updater()

    # Tear down both subscriptions when the column leaves the DOM (redraw via
    # content.clear() or page close).
    def _teardown() -> None:
        obj.unsubscribe(_on_model_change)
        obj.unsubscribe_ui_state(_on_ui_state_change)

    anchor_cleanup_to_element(column, _teardown)


def render_schema(schema_cls: type["Settings"], registry: "SettingsRegistry") -> None:
    """Render only the fields declared on *schema_cls* as labelled form rows,
    in declaration order.

    Walks the schema's own _property_settings() directly (already in
    declaration order — base-first MRO walk preserving dict insertion order)
    and filters to registry-known keys, so keys registered under the same
    namespace prefix by other code (e.g. dynamic library keys) are not
    accidentally included. This is an order-preserving FILTER, not a
    collect-then-sort: unlike render_keys, no (category, order, key) re-sort
    happens here (see internals/superpowers/2026-07-18-settings-panel-ordering-spec.md).

    MRO caveat: if a subclass re-declares a field name also present on a base
    class, _property_settings()'s dict-assignment overwrites the VALUE at that
    key but does not move the key's position, so the field renders at the base
    class's declaration position, not the subclass's. LibrarySettings /
    FrameworkSettings block deep subclassing, so this is unreachable for
    either — documented, not fixed.
    """
    prop_fields: dict[str, setting] = schema_cls._property_settings()
    ordered_defns = [
        defn
        for defn in prop_fields.values()
        if defn._setting_key and registry.has_definition(defn._setting_key)
    ]
    if not ordered_defns:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    def _render_one(defn: setting) -> None:
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

    _render_grouped(ordered_defns, category_of=lambda d: d._category, render_one=_render_one)


def render_keys(prefix: str, registry: "SettingsRegistry") -> None:
    """Render all registry keys whose full key starts with *prefix*.

    Intended for dynamically registered keys (e.g. per-library log levels)
    that are not declared on any schema class. The category label is derived
    from the key structure via the category group.
    """
    match_prefix = prefix + "."
    defns: dict[str, setting] = {
        key: defn for key, defn in registry.all_definitions().items() if key.startswith(match_prefix)
    }
    if not defns:
        ui.label(f"No fields found under: {prefix}.*").classes("text-xs hw-text-muted px-2 py-1")
        return

    _render_definitions(_sort_definitions(defns.values()), registry)


# ===========================================================================
# 2. Collect & group
# ===========================================================================


def _category_sort_key(category: str, order: int, tiebreak: "str | int") -> tuple[str, int, "str | int"]:
    """Shared (category, order, tiebreak) sort key. ``root`` sorts before all others.

    ``tiebreak`` is a setting key/name (alphabetical) for registry-backed callers,
    or a declaration-order index for ``render_settings`` — callers never mix the
    two within one sort, so comparability across the union type is not needed.
    """
    return ("" if category.lower() == "root" else category, order, tiebreak)


def _sort_definitions(defns: "Iterable[setting]") -> list[setting]:
    """Sort a collection of field descriptors by (category, order, setting_key)."""
    return sorted(
        defns,
        key=lambda d: _category_sort_key(d._category, d._order, d._setting_key),
    )


def _group_by_category(
    items: list, key: Callable[[Any], str] = lambda x: x._category
) -> list[tuple[str, list]]:
    """Group a pre-sorted list of descriptors by category, preserving order."""
    return [(cat, list(grp)) for cat, grp in groupby(items, key=key)]


def _render_grouped(
    sorted_items: list[setting], category_of, render_one, group_wrappers: dict[str, Any] | None = None
) -> Any:
    """Lay out *sorted_items* as a settings column, grouped into category sections.

    Returns the outer ``ui.column`` so callers can anchor teardown to it.
    *render_one* is called once per item, inside its category group. Each
    section sits in a wrapper div stamped ``data-category-group`` so callers
    (and tests/CSS) can toggle a whole section; when *group_wrappers* is
    given it maps ``category -> wrapper`` for visibility recomputes — a
    fully-hidden category hides header and all.

    category 'advanced' is initially closed, all others open.
    """
    column = ui.column().classes("w-full compact-fields sf-field-list").style(_COLUMN_STYLE)
    with column:
        for category, group in _group_by_category(sorted_items, key=category_of):
            wrapper = ui.element("div").classes("w-full").props(f'data-category-group="{category}"')
            if group_wrappers is not None:
                group_wrappers[category] = wrapper
            with wrapper:
                default_open = category.lower() != "advanced"
                with hui.category_group(category, default_open=default_open):
                    for item in group:
                        render_one(item)
    return column


def _render_definitions(sorted_defns: list, registry: "SettingsRegistry") -> None:
    """Render a pre-sorted list of registry-backed field descriptors.

    Each widget binds the registry-owned cell for its key, so
    external changes (JSON reload, cross-tab writes) show live via the cell's
    own event — no registry subscription, re-resolve loop, or per-widget
    throwaway field.
    """

    def _render_one(defn: setting) -> None:
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
    *cell* (the registry-owned cell) for live external sync.

    Carries the same override chrome as ``_render_reactive_field_row`` — a •
    dirty prefix and a right-click Reset item on the label — but against the
    registry's TIER stack rather than a bag's local opinion. "Locally set"
    here means the workspace tier is set (the tier the UI writes, see
    ``_registry_on_edit``); reset clears it and the value falls back through
    ``resolve()`` to the global tier or the descriptor default. The menu item
    is worded from ``resolve()``'s reported source so it never promises a
    fallback that isn't there. There is no promote/demote half: a registry key
    belongs to no node.

    *error_container* is a block-level element BEFORE the label+widget row,
    not a third flex child inside it (mirrors ``_render_reactive_field_row``):
    as a flex sibling inside the row, its own ``w-full`` would claim a third
    column, squeezing the widget onto a wrapped second line instead of
    sitting beside the label.
    """
    if defn._ui_state is UiState.HIDDEN:
        return None
    error_container = ui.element("div").classes("w-full")
    on_edit = _registry_on_edit(registry, key, error_container)

    def _is_workspace_set() -> bool:
        return registry.get_global_tier(key, "workspace").is_set

    def _reset_label() -> str:
        # Wording follows where a reset would actually land. The global tier is
        # hand-edited and never written by the app (see save_to_json), so
        # "reset to global" is offered only when that tier really holds a value
        # — otherwise the fallback is the descriptor default.
        return (
            "Reset to global setting"
            if registry.get_global_tier(key, "global").is_set
            else "Reset to default"
        )

    reset_item: Any = None
    reset_caption: Any = None
    label: Any = None

    def _refresh_chrome() -> None:
        dirty = _is_workspace_set()
        if label is not None:
            label.set_text(f"• {label_text}" if dirty else label_text)
        if reset_item is not None:
            reset_item.set_enabled(dirty)
        if reset_caption is not None:
            # A ui.menu_item has no set_text — its caption is a child label,
            # which is why the wording is re-applied through that element.
            reset_caption.set_text(_reset_label())

    def _on_reset_click() -> None:
        # reset_global only notifies when the effective value actually MOVES
        # (workspace value equal to the global/default it falls back to fires
        # nothing), so refresh this row's chrome directly rather than relying
        # on the subscription — same reasoning as the reactive path's
        # _on_reset_click.
        _registry_reset(registry, key, error_container)
        _refresh_chrome()

    with ui.row().classes(_ROW_CLASSES).props(f'data-field="{attr_name}"' if attr_name else "") as row:
        with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
            label = ui.label(label_text).classes("text-xs min-w-0 truncate")
            if description:
                label.tooltip(description)
            # Nested in the label cell so the widget column keeps the browser's
            # native context menu (copy/paste in inputs) — as in the reactive path.
            with ui.context_menu().props('data-row-menu="true"'):
                reset_item = ui.menu_item(on_click=_on_reset_click, auto_close=True)
                with reset_item:
                    reset_caption = ui.label(_reset_label())
        callback, _set_enabled = _resolve_widget_instance(defn, on_edit, cell=cell)

    # The registry stores subscriptions as weakrefs, so this closure must be kept
    # alive by something with the row's lifetime — the cleanup callback anchored
    # to the row element holds the only strong reference.
    def _on_registry_change(_key: str, _value: Any) -> None:
        _refresh_chrome()

    registry.subscribe(key, _on_registry_change)

    def _teardown(_cb: Callable[[str, Any], None] = _on_registry_change) -> None:
        registry.unsubscribe(key, _cb)

    anchor_cleanup_to_element(row, _teardown)

    _refresh_chrome()
    return callback


def _render_reactive_field_row(
    obj: "Settings",
    attr_name: str,
    defn: "setting",
    updaters: dict[str, Callable[[], None]],
    on_ui_state_applied: Callable[[], None] | None = None,
) -> None:
    """Render a single reactive field row (instance path).

    Registers an entry in *updaters* keyed by ``attr_name``: a zero-arg callback
    that re-reads the current model value and applies it to the rendered widget
    and override chrome IN PLACE (no element rebuild), so external changes to the
    model (other tab / worker / mirror) are reflected.
    """

    is_mirrored = defn.is_mirror or defn.is_graph_mirror
    # A promoted field is driven by a DATA port (see haywire.core.node.promotion).
    # The row is marked so the panel doesn't silently present an editable widget for
    # a value the graph now owns; the value display stays live (the setting and the
    # port share one cell, so getattr(obj, attr_name) reflects the port). The
    # presence of the port is the truth.
    from haywire.core.node.promotion import is_field_promoted

    is_promoted = is_field_promoted(obj, attr_name)

    # Direction- and link-aware promoted row: an INLET means the graph now owns
    # the value (an incoming edge, or simply having been promoted), so the row
    # goes read-only; an OUTLET keeps the setting as source of truth, so the
    # editable widget stays. Recomputed per render — link-state staleness until
    # the next redraw is accepted, no reactive tracking beyond this per-render
    # check.
    port = obj._node.ports.get(defn.storage_key) if (is_promoted and obj._node is not None) else None
    is_promoted_input = False
    promoted_hint = ""
    if port is not None:
        if port.is_inlet():
            is_promoted_input = True
            promoted_hint = "driven by inlet" if port.is_linked() else "promoted to inlet"
        elif port.is_config():
            # A CONFIG port has no edge, ever — its widget is the only write
            # path. It still renders read-only here: the interactive widget
            # moves to wherever a CONFIG port's live widget already renders
            # today (Ports Panel / node card), not the Properties panel row.
            is_promoted_input = True
            promoted_hint = "promoted to config"
        else:
            promoted_hint = "promoted to outlet"

    # Declarative same-bag gating (enabled_when / visible_when metadata
    # conventions — see setting-canon.md). The CHECK lives on the bag
    # (effective_ui_state, severity max with the imperative state); only the
    # warn-once-per-row-build for a typo'd controller and the live
    # subscription wiring belong here. A controller-VALUE change is a genuine
    # cell event (subscribe_field below); the imperative state arrives on the
    # bag's UI-state channel subscribed in render_settings.
    def _gate_controller(meta_key: str) -> str | None:
        gate = defn._metadata.get(meta_key) if defn._metadata else None
        if gate is None:
            return None
        controller_name, _expected = gate
        if controller_name in type(obj)._property_settings():
            return controller_name
        logger.warning(
            "%s=%r on field %r references unknown field %r on %s "
            "— ignoring (field will never be auto-gated by this rule)",
            meta_key,
            gate,
            attr_name,
            controller_name,
            type(obj).__name__,
        )
        return None

    gate_controllers = {
        name for name in (_gate_controller("enabled_when"), _gate_controller("visible_when")) if name
    }

    # Override chrome (reset button) is offered whenever the field carries a local
    # opinion (_set_keys membership) AND the graph doesn't own its value through a
    # promoted INLET. A promoted OUTLET keeps the setting as source of truth (its
    # widget stays editable), so its chrome stays; an inlet-driven or inlet-promoted
    # row is read-only, so resetting there is meaningless. Plain fields get the
    # same affordance as mirrors, only the tooltip/meaning differs by field kind.
    def _has_local_opinion() -> bool:
        return obj.is_locally_set(attr_name) and not is_promoted_input

    # The • dirty prefix is narrower than "has a reset button": it's suppressed for
    # ANY promotion direction (not just inlet) and while the row is DISABLED — a
    # promoted or locked row isn't something the user can act on right now, so the
    # marker would just be noise.
    def _should_show_dirty() -> bool:
        return (
            _has_local_opinion() and not is_promoted and obj.effective_ui_state(attr_name) is UiState.NORMAL
        )

    # "Reset to global default" re-seeds a mirror field from the current global and
    # resumes tracking; a plain field has no global — reset restores the descriptor
    # default. reset() already branches this internally; only the wording differs.
    reset_tooltip = "Reset to global default" if is_mirrored else "Reset to default"

    def _label_text(dirty: bool) -> str:
        base = defn._label or attr_name
        prefix = ("→" if is_promoted else "") + ("•" if dirty else "")
        return f"{prefix} {base}" if prefix else base

    label: Any = None
    value_apply: Callable[[Any], None] | None = None

    def _on_reset_click():
        obj.reset(attr_name)
        # reset() discards the local opinion but only writes the cell when the
        # value actually changes (old != new). A field that was locally-set yet
        # already equalled its default — e.g. promoted-then-demoted unchanged —
        # fires NO cell event, so the bag subscription driving _refresh_chrome
        # never runs and the • / greyed-reset state would linger. Refresh this
        # row's chrome directly so it clears regardless of whether the value moved.
        _refresh_chrome()

    def _promote(direction: "PortType") -> None:
        from haywire.core.node.promotion import bag_accessor, promote_setting

        node = obj._node
        if node is None:
            return
        accessor = bag_accessor(node, obj)
        if accessor is None:
            return
        promote_setting(node, accessor, attr_name, direction)
        _request_canvas_redraw(node)

    def _demote() -> None:
        from haywire.core.node.promotion import demote_setting

        node = obj._node
        if node is None:
            return
        demote_setting(node, defn.storage_key)
        _request_canvas_redraw(node)

    reset_item: Any = None

    def _refresh_reset_item() -> None:
        # Reset is the menu's one transient entry — listed permanently, greyed
        # while the row is clean OR while UiState locks the row's
        # value-editing chrome (DISABLED). Promote/Demote are structural and
        # per-render constants: promotion changes rebuild the whole panel.
        if reset_item is not None:
            reset_item.set_enabled(
                _has_local_opinion() and obj.effective_ui_state(attr_name) is UiState.NORMAL
            )

    def _build_row_menu() -> None:
        # The setting-row menu (sole promote surface). Structural facts HIDE
        # entries: no node -> no promotion; ineligible direction -> absent;
        # promoted <-> unpromoted swaps Promote/Demote. Transient facts DISABLE:
        # reset greys when clean/DISABLED. Nested in the label cell so the
        # widget column keeps the browser's native context menu (copy/paste in
        # inputs).
        nonlocal reset_item
        from haywire.core.node.promotion import eligible_promotion_directions

        node = obj._node
        structural: list[tuple[str, Callable[..., None]]] = []
        if node is not None:
            if is_promoted:
                structural.append(("Demote", _demote))
            else:
                for direction in eligible_promotion_directions(defn):
                    structural.append(
                        (f"Promote to {direction.name.lower()}", lambda d=direction: _promote(d))
                    )
        offers_reset = True
        if not structural and not offers_reset:
            return  # nothing this row can ever do — no menu at all
        with ui.context_menu().props('data-row-menu="true"'):
            for text, handler in structural:
                ui.menu_item(text, on_click=handler, auto_close=True)
            if offers_reset:
                reset_item = ui.menu_item(reset_tooltip, on_click=_on_reset_click, auto_close=True)
        _refresh_reset_item()

    def _render_label():
        nonlocal label
        with ui.row().classes("items-center gap-0 shrink-0 sf-label"):
            label = ui.label(_label_text(_should_show_dirty())).classes("text-xs truncate")
            tooltip_parts = [p for p in (defn._description, promoted_hint) if p]
            if tooltip_parts:
                label.tooltip(" — ".join(tooltip_parts))
            _build_row_menu()

    # Every field — scalars, vectors, color — resolves a shared BaseWidget by its
    # widget_key, stamped once at __set_name__ (see _resolve_widget_instance).
    # VecWidget handles vec types via widget_config['vec_meta']; the panel does
    # not special-case them.
    error_container = ui.element("div").classes("w-full")

    # A column-oriented widget (e.g. VecWidget in row-per-component mode) renders
    # multiple flush component rows; top-align the label against the first row
    # rather than centering it across the whole block. Field-to-field spacing
    # comes uniformly from the parent column's gap (same for scalars and
    # vectors) — no per-field margin, which would compound unevenly between two
    # adjacent vec rows. Scalars keep items-center. Config-driven: no widget
    # identity named here, just the "orientation" property.
    row_classes = _ROW_CLASSES
    if defn.widget_config.get("properties", {}).get("orientation", "") == "column":
        row_classes = _ROW_CLASSES.replace("items-center", "items-start")

    row_props = f'data-field="{attr_name}"'
    if is_promoted:
        row_props += ' data-promoted="true"'
        if port is not None:
            direction_attr = "config" if port.is_config() else ("inlet" if is_promoted_input else "outlet")
            row_props += f' data-promoted-direction="{direction_attr}"'
        if promoted_hint:
            row_props += f' data-hint="{promoted_hint}"'
    row_props += f' data-ui-state="{obj.effective_ui_state(attr_name).name.lower()}"'

    widget_set_enabled: Callable[[bool], None] | None = None
    with ui.row().classes(row_classes).props(row_props) as row_element:
        _render_label()
        if is_promoted_input:
            promoted_lbl = (
                ui.label("promoted")
                .classes(f"text-xs text-right italic hw-text-muted {_WIDGET_CLASSES}")
                .props('data-promoted-hint="true" data-value="promoted"')
            )
            if promoted_hint:
                promoted_lbl.tooltip(promoted_hint)
        else:
            on_edit = _bag_on_edit(obj, attr_name, error_container)
            value_apply, widget_set_enabled = _resolve_widget_instance(defn, on_edit, bag=obj)

    def _refresh_row_ui_state() -> None:
        state = obj.effective_ui_state(attr_name)
        row_element.set_visibility(state is not UiState.HIDDEN)
        row_element.props(f'data-ui-state="{state.name.lower()}"')
        if widget_set_enabled is not None:
            widget_set_enabled(state is UiState.NORMAL)
        _refresh_reset_item()
        if on_ui_state_applied is not None:
            on_ui_state_applied()

    for _controller in gate_controllers:

        def _on_controller_changed(_value: Any, _old: Any) -> None:
            _refresh_row_ui_state()

        obj.subscribe_field(_controller, _on_controller_changed)

        def _unsubscribe(cb: Callable[[Any, Any], None] = _on_controller_changed) -> None:
            obj.unsubscribe(cb)

        anchor_cleanup_to_element(row_element, _unsubscribe)

    def _refresh_chrome():
        # Real widgets bind the shared cell directly (on_changed), so
        # re-pushing their value here would be a structural no-op:
        # value_apply is None for every case except the unknown-widget label
        # fallback, which owns no cell subscription of its own and needs this
        # to reflect external changes at all. Everything else in this callback
        # is pure override chrome: the • prefix, the menu's Reset enabled-state,
        # and the ui-disabled marker.
        #
        # Applies to plain fields too: editing a plain field's widget writes
        # its cell, and the • / reset must appear live rather than waiting
        # for the next full panel redraw. is_promoted_input is a per-render constant
        # (structural, needs a redraw to change), so a cell-value change only flips
        # the is_locally_set half — recomputed here.
        if value_apply is not None:
            value_apply(getattr(obj, attr_name))
        dirty = _should_show_dirty()
        if label is not None:
            label.set_text(_label_text(dirty))
        _refresh_reset_item()
        _refresh_row_ui_state()

    updaters[attr_name] = _refresh_chrome


# ===========================================================================
# 4. Choose -> draw -> link
# ===========================================================================


def _resolve_widget_instance(
    defn: "setting",
    on_edit: Callable[[Any], None],
    bag: "Settings | None" = None,
    cell: "DataField | None" = None,
) -> tuple[Callable[[Any], None] | None, Callable[[bool], None]]:
    """Build the shared ``BaseWidget`` for *defn* via a ``SettingWidgetModel``.

    Falls back to a read-only label when the resolved widget key is unknown, so
    a missing widget never renders a silent blank. The model always binds the
    field's shared ``DataField`` cell: *cell* when given (the
    registry-owned cell, registry path), else *bag*'s instance cell. Writes
    route through *on_edit* — the write-policy closure (``_bag_on_edit`` /
    ``_registry_on_edit``) — never raw into the cell.

    Returns ``(apply_callback, set_enabled)``. ``apply_callback`` is ``None``
    for a real widget (it hears cell writes directly via ``on_changed``, so
    there is nothing left for a caller to push) or the label fallback's
    ``apply(value)`` when the widget key is unknown (that display has no cell
    binding of its own). ``set_enabled(bool)`` toggles the widget's
    disabled state — ``BaseWidget.set_enabled`` (Quasar ``:disable`` / §2.11
    CSS fallback) for a real widget, a style toggle on the label fallback —
    and is never ``None``.
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
    assert shared_cell is not None, f"no cell for setting widget {defn._attr_name!r}"

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

    # get_widget_class()'s declared return type is Type[IWidget] (the minimal
    # interface), but set_enabled is a BaseWidget addition — every widget
    # actually resolved here subclasses BaseWidget (module docstring),
    # so this is always present in practice. Fail soft rather than assert:
    # an IWidget implemented directly against the interface (no BaseWidget)
    # simply can't be disabled, which degrades to "always enabled" instead
    # of crashing the panel.
    set_enabled = getattr(widget, "set_enabled", lambda _enabled: None)

    return None, set_enabled


def _build_label_widget(value: Any) -> tuple[Callable[[Any], None], Callable[[bool], None]]:
    """Display-only ``label`` widget — no ``.value`` (set_text, not BindableProperty).

    ``apply(value)`` exists solely for this label fallback (no cell binding);
    real widgets hear the cell directly. ``set_enabled(bool)`` applies/removes
    the §2.11 disabled style directly on the label (a ui.label is not a
    DisableableElement, so there is no Quasar :disable to prefer here).
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

    def _set_label_enabled(enabled: bool, _lbl=lbl) -> None:
        if enabled:
            _lbl.style(remove=DISABLED_STYLE)
        else:
            _lbl.style(add=DISABLED_STYLE)

    return _apply_label, _set_label_enabled


def _request_canvas_redraw(node: "NodeData") -> None:
    """Best-effort canvas pin refresh after a promote/demote from the row menu.

    Routes through BaseGraph.request_node_redraw: the debounced validation pass
    picks the node up, the app layer (haystack) marks the graph unsaved and
    broadcasts GraphDataMutated, and the settings panel's redraw_on rebuilds
    this row with its new promotion state. Deliberately NO synchronous
    publish here — a redraw of the emitting panel from inside its own click
    handler deletes the handler's slot mid-flight (see
    .insights/feedback_nicegui_async.md).

    Headless tests build nodes on stub wrappers without a graph, hence the
    getattr guard.
    """
    graph = getattr(node.wrapper, "_graph", None)
    if graph is not None:
        graph.request_node_redraw(node.node_id)


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

    Surfaces failures instead of swallowing them: set_global raises
    ValueError on validator rejection and KeyError on a dropped definition
    (hot-reload race)."""

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


def _registry_reset(registry: "SettingsRegistry", key: str, error_container) -> None:
    """Reset policy for the registry path: clear the workspace tier → debounced save.

    The mirror of ``_registry_on_edit``: that closure SETS the workspace tier,
    this clears it, and the value falls back through ``resolve()`` to the
    global tier or the descriptor default. The save is not optional —
    ``_collect_workspace_entries`` writes only *set* values, so persisting is
    what actually drops the key from the workspace JSON; without it the old
    value returns on the next load.

    Only the workspace tier is ever touched. The global tier is hand-edited by
    the user and never written by the app (see ``save_to_json``).
    """
    try:
        registry.reset_global(key, "workspace")
        registry.save_to_json_debounced()
    except KeyError as exc:
        # Definition dropped underneath us (hot-reload race) — same failure
        # surface as _registry_on_edit rather than a swallowed exception.
        error_container.clear()
        with error_container:
            ui.label(str(exc)).classes("text-xs hw-text-danger px-2").props('data-error="true"')
        return
    error_container.clear()
