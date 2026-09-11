# haywire/ui/panel/render_utils.py
"""Render ``FrameworkSettings``/``LibrarySettings``/``NodeSettings`` fields as form rows.

Every entry point takes a ``SessionContext`` first. The fields themselves do
not need it — value, chrome and widget come from the bag or the registry — but
a row's context menu offers session-scoped actions such as opening a
component's source in this session's editor slot. A caller with no session
builds a throwaway context rather than passing ``None``.

Both row renderers carry the same override chrome, a • dirty glyph and a
right-click Reset on the row's label, over different notions of overridden:

- reactive (instance): the bag holds a local opinion, mirror or plain. Reset
  restores the global for a ``mirrors=`` field, otherwise the descriptor
  default. Suppressed while a promoted inlet owns the value, since the graph
  drives it. This menu is also the only promote surface (``_build_row_menu``).
- registry (schema/keys): the workspace tier is set, the only tier the UI
  writes. Reset clears it and the value falls back through ``resolve()`` to
  the global tier or the descriptor default, whichever it lands on, and the
  menu item is worded to match. A registry key belongs to no node, so there is
  no promote half.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Iterable
from itertools import groupby
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from haywire.core.settings import UiState
from haywire.ui import elements as hui
from haywire.ui.panel.host_rendering import drawing_panel
from haywire.ui.utils import anchor_cleanup_to_element
from haywire.ui.widget.base import DISABLED_STYLE

if TYPE_CHECKING:
    from haywire.core.node.data import NodeData
    from haywire.core.session.context import SessionContext
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


def render_settings(
    ctx: "SessionContext", obj: "Settings", *, categories: Iterable[str] | None = None
) -> None:
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

    Args:
        categories: Narrows the render to these ``category=`` groups, for a
            surface wanting one slice of a bag. A filter, not a re-sort:
            order, grouping, headers, chrome and the subscription are what an
            unfiltered render gives. An unknown name selects nothing and
            renders the empty state.
    """

    fields = type(obj)._settings_descriptors()
    if categories is None:
        visible_fields = dict(fields)
    else:
        wanted = set(categories)
        visible_fields = {name: defn for name, defn in fields.items() if defn._category in wanted}
    if not visible_fields:
        ui.label("No fields defined.").classes("text-xs hw-text-muted px-2 py-1")
        return

    # _settings_descriptors() already yields fields in declaration order (base-first
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
        wrapper.set_visibility(any(obj._effective_ui_state(n) is not UiState.HIDDEN for n in names))

    def _render_one(item: tuple[str, "setting"]) -> None:
        category = item[1]._category

        def _on_applied() -> None:
            _refresh_group_visibility(category)

        _render_reactive_field_row(ctx, obj, item[0], item[1], updaters, on_ui_state_applied=_on_applied)

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

    obj._subscribe(_on_model_change)
    obj._subscribe_ui_state(_on_ui_state_change)

    # Explicit initial sync — exercise every row's apply() path once at render,
    # so "the widget shows the model" is a property of the apply path. Mirrors
    # BaseWidget.render() calling on_model_changed() once after wiring dispatch.
    for _updater in updaters.values():
        _updater()

    # Tear down both subscriptions when the column leaves the DOM (redraw via
    # content.clear() or page close).
    def _teardown() -> None:
        obj._unsubscribe(_on_model_change)
        obj._unsubscribe_ui_state(_on_ui_state_change)

    anchor_cleanup_to_element(column, _teardown)


def render_schema(ctx: "SessionContext", schema_cls: type["Settings"], registry: "SettingsRegistry") -> None:
    """Render the fields declared on *schema_cls* as form rows, in declaration order.

    Filters to registry-known keys, so keys another caller registered under
    the same namespace prefix are left out. An order-preserving filter, not a
    re-sort: unlike :func:`render_keys`, nothing is reordered by category.

    A field a subclass re-declares renders at the base class's position, since
    the override replaces the value without moving the key. Unreachable for
    ``LibrarySettings`` and ``FrameworkSettings``, which block deep
    subclassing.
    """
    prop_fields: dict[str, setting] = schema_cls._settings_descriptors()
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
            ctx,
            defn._label or attr_name,
            defn._description,
            defn,
            registry,
            key,
            attr_name=attr_name,
            cell=cell,
        )

    _render_grouped(ordered_defns, category_of=lambda d: d._category, render_one=_render_one)


def render_keys(ctx: "SessionContext", prefix: str, registry: "SettingsRegistry") -> None:
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

    _render_definitions(ctx, _sort_definitions(defns.values()), registry)


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
    sorted_items: list, category_of, render_one, group_wrappers: dict[str, Any] | None = None
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


def _render_definitions(ctx: "SessionContext", sorted_defns: list, registry: "SettingsRegistry") -> None:
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
            ctx,
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
# 2b. Developer submenu
#
# Every row's menu can offer "open the code behind this row" — the settings
# class and the panel that drew it — gated on ctx.developer_mode.
#
# Keys are resolved, never assumed: a NodeSettings bag has no identity, so the
# target is the owning node, whose source file holds the inner `class
# Settings` anyway. An unresolvable key yields no entry rather than a dead one.
# ===========================================================================


def _component_key(obj: Any) -> str | None:
    """The registry key for a class or instance, or ``None`` if it has no identity.

    An unregistered class answers ``None`` rather than raising, and ``None``
    in is ``None`` out, so callers can pass a lookup that found nothing.
    """
    if obj is None:
        return None
    cls = obj if isinstance(obj, type) else type(obj)
    identity = getattr(cls, "class_identity", None)
    return getattr(identity, "registry_key", None) if identity is not None else None


def _bag_source_key(obj: "Settings") -> str | None:
    """Where the code for this settings bag lives, as a registry key, or ``None``.

    A registered bag answers its own key; a ``NodeSettings`` bag answers the
    owning node's, whose source file is where its inner ``class Settings`` is
    written.
    """
    own = _component_key(obj)
    if own is not None:
        return own
    node = getattr(obj, "_node", None)
    return _component_key(node) if node is not None else None


def _open_component_source(ctx: "SessionContext", registry_key: str) -> None:
    """Ask whoever hosts a source viewer to show ``registry_key``.

    Publishes a signal naming no editor, since core cannot import the barn
    library that owns one. ``haybale-studio`` answers it by revealing its
    ``ComponentSourceEditor``; with no source-viewer library installed nothing
    answers, which is a working configuration.
    """
    from haywire.core.signals import RevealComponentSource

    ctx.session.publish(RevealComponentSource(registry_key=registry_key))


def component_source_path(ctx: "SessionContext", registry_key: str) -> "Path | None":
    """The file ``registry_key``'s class is declared in, or ``None``.

    ``None`` covers every way this finds nothing: no app on the context, an
    unresolvable key, or a generated class with no file.
    """
    app = ctx.app
    if app is None:
        return None
    cls = app.library_service.lookup_component_class(registry_key)
    if cls is None:
        return None
    try:
        return Path(inspect.getfile(cls))
    except (TypeError, OSError):
        return None


def _open_source_file(ctx: "SessionContext", registry_key: str) -> None:
    """Ask whoever edits files to open ``registry_key``'s source file.

    The key is resolved to a path here, because ``RevealSource`` is
    file-shaped: its subscriber knows nothing about registries. A key
    resolving to no file opens nothing.
    """
    from haywire.core.signals import RevealSource

    path = component_source_path(ctx, registry_key)
    if path is None:
        return
    ctx.session.publish(RevealSource(binding_id=str(path), label=path.name))


def _build_developer_menu(ctx: "SessionContext", *entries: tuple[str, str | None]) -> None:
    """Draw the Developer submenu for a settings row, if it has anything to say.

    *entries* are ``(label, registry_key)`` pairs; a pair whose key is None is
    dropped.
    """
    resolved = [(label, key) for label, key in entries if key]
    if not resolved:
        return
    # dense=False: the anchor must match the density of the Reset/Promote items
    # it sits beside, which are plain menu_items. The default (True) suits
    # NodeMenuBuilder, whose own leaves are dense, and left the Developer row
    # visibly shorter than the rest of this menu. Same reasoning applies one
    # level down, to each entry's own sub-flyout anchor.
    siblings: list = []
    with hui.flyout_category("Developer", siblings, dense=False) as entry_siblings:
        # entry_siblings (yielded, not a fresh list per entry) is what makes the
        # per-entry sub-flyouts (below) siblings of EACH OTHER. A fresh list per
        # iteration would register each sub-flyout into its own private group of
        # one — open_on_hover would then have nothing else to close, and opening
        # "Open panel source" would leave "Open settings source"'s body visibly
        # still open beside it (regression caught in review: both stayed open
        # onscreen at once).
        for label, key in resolved:
            with hui.flyout_category(label, entry_siblings, dense=False):
                # nowrap for the same reason flyout_category pins its own anchor.
                ui.menu_item(
                    "Open in Context",
                    on_click=lambda k=key: _open_component_source(ctx, k),
                    auto_close=True,
                ).style("white-space: nowrap")
                ui.menu_item(
                    "Open in Code Editor",
                    on_click=lambda k=key: _open_source_file(ctx, k),
                    auto_close=True,
                ).style("white-space: nowrap")


# ===========================================================================
# 3. Row rendering
# ===========================================================================


def _render_field_row(
    ctx: "SessionContext",
    label_text: str,
    description: str,
    defn,
    registry: "SettingsRegistry",
    key: str,
    attr_name: str = "",
    cell: "DataField | None" = None,
) -> Callable[[Any], None] | None:
    """Render one label + widget row against the registry, or ``None`` if hidden.

    The same override chrome as ``_render_reactive_field_row``, over the
    registry's tier stack: the • dirty prefix means the workspace tier is set,
    and Reset clears it so the value falls back to the global tier or the
    descriptor default. The item is worded from wherever it would land, so it
    never promises a fallback that isn't there.

    Args:
        cell: The registry-owned cell the widget binds for live external sync.
    """
    if defn._ui_state is UiState.HIDDEN:
        return None
    # Before the row, not inside it: as a flex sibling its w-full claims a
    # third column and wraps the widget onto its own line.
    error_container = ui.element("div").classes("w-full")
    on_edit = _registry_on_edit(registry, key, error_container)

    def _is_workspace_set() -> bool:
        return registry.get_global_tier(key, "workspace").is_set

    def _reset_label() -> str:
        # Worded for where a reset lands: the global tier is hand-edited and
        # often unset, in which case the fallback is the descriptor default.
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
        # reset_global notifies only when the effective value moves, so refresh
        # the chrome here instead of waiting on the subscription.
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
                # No bag instance on this path — the schema class that DECLARED
                # the field is the settings source, and the descriptor records
                # it as _owner_cls at __set_name__.
                if ctx.developer_mode:
                    _build_developer_menu(
                        ctx,
                        ("Settings source", _component_key(getattr(defn, "_owner_cls", None))),
                        ("Panel source", _component_key(drawing_panel())),
                    )
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
    ctx: "SessionContext",
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
    # goes read-only. An OUTLET or a CONFIG keeps the setting as source of truth,
    # so the editable widget stays. Recomputed per render — link-state staleness
    # until the next redraw is accepted, no reactive tracking beyond this
    # per-render check.
    port = obj._node.ports.get(defn.storage_key) if (is_promoted and obj._node is not None) else None
    is_promoted_input = False
    promoted_hint = ""
    if port is not None:
        if port.is_inlet():
            is_promoted_input = True
            promoted_hint = "driven by inlet" if port.is_linked() else "promoted to inlet"
        elif port.is_config():
            # A CONFIG port has no edge, ever — the setting stays the source of
            # truth and its widget is the only write path. Like an OUTLET, the
            # row keeps its editable widget: promoting to config ADDS a live
            # widget on the node/Ports Panel, it does not move the panel one.
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
        if controller_name in type(obj)._settings_descriptors():
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
    # promoted INLET. A promoted OUTLET or CONFIG keeps the setting as source of
    # truth (its widget stays editable), so its chrome stays; an inlet-driven or
    # inlet-promoted row is read-only, so resetting there is meaningless. Plain
    # fields get the same affordance as mirrors, only the tooltip/meaning differs
    # by field kind.
    def _has_local_opinion() -> bool:
        return obj._is_locally_set(attr_name) and not is_promoted_input

    # The • dirty prefix is narrower than "has a reset button": it's suppressed for
    # ANY promotion direction (not just inlet) and while the row is DISABLED — a
    # promoted or locked row isn't something the user can act on right now, so the
    # marker would just be noise.
    def _should_show_dirty() -> bool:
        return (
            _has_local_opinion() and not is_promoted and obj._effective_ui_state(attr_name) is UiState.NORMAL
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
        obj._reset(attr_name)
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
    none_item: Any = None

    def _set_to_none() -> None:
        setattr(obj, attr_name, None)

    # Every wrapper field lists "Set to none", a field defaulting to absence
    # included: Reset greys whenever there is no local opinion, so hiding it
    # there leaves no enabled route back to absence.
    offers_none = defn._is_wrapper_type()

    def _refresh_reset_item() -> None:
        # Transient entries stay listed and grey while the row is clean or
        # DISABLED. Promote/Demote are per-render constants: a promotion
        # change rebuilds the panel.
        editable = obj._effective_ui_state(attr_name) is UiState.NORMAL
        if reset_item is not None:
            reset_item.set_enabled(_has_local_opinion() and editable)
        if none_item is not None:
            # Greyed once the value already IS absent — nothing left to do.
            none_item.set_enabled(editable and getattr(obj, attr_name) is not None)

    def _build_row_menu() -> None:
        # Structural facts hide entries (no node, ineligible direction,
        # Promote vs Demote); transient ones only grey them. Nested in the
        # label cell so the widget column keeps the browser's own menu.
        nonlocal reset_item, none_item
        from haywire.core.node.promotion import eligible_promotion_directions

        node = obj._node
        # Promotion collapses to ONE top-level entry: "Demote" once promoted,
        # else a "Promote to" flyout holding the eligible directions. Always a
        # flyout, even at one eligible direction, so the entry keeps a fixed
        # position and the row menu's own shape does not shift per field.
        directions: list["PortType"] = []
        if node is not None and not is_promoted:
            directions = list(eligible_promotion_directions(defn))
        offers_demote = node is not None and is_promoted
        with ui.context_menu().props('data-row-menu="true"'):
            if offers_demote:
                ui.menu_item("Demote", on_click=_demote, auto_close=True)
            elif directions:
                # dense=False: the anchor's Quasar density must match the plain
                # menu_items beside it (Reset et al are not dense), or it renders
                # visibly shorter than the rest of the menu. See flyout_category.
                # The sibling group is this menu's own — one flyout, nothing to
                # close beside it, but the primitive owns that bookkeeping.
                promote_siblings: hui.FlyoutSiblings = []
                with hui.flyout_category("Promote to", promote_siblings, dense=False):
                    for direction in directions:
                        # nowrap for the same reason flyout_category pins its own
                        # anchor: when Quasar flips the flyout leftward it
                        # shrink-to-fits, and an unpinned label wraps.
                        ui.menu_item(
                            direction.name.lower(),
                            on_click=lambda d=direction: _promote(d),
                            auto_close=True,
                        ).style("white-space: nowrap")
            # Reset is listed permanently for a writable row — it greys when the
            # row is clean rather than disappearing, so the menu never renders
            # empty and its shape does not depend on the current value.
            reset_item = ui.menu_item(reset_tooltip, on_click=_on_reset_click, auto_close=True)
            if offers_none:
                # Adjacent to Reset on purpose: both are "put this field back to
                # not-my-problem", and they differ only in where back is. Each
                # says where it lands, because where they land can coincide.
                none_item = ui.menu_item("Set to none", on_click=_set_to_none, auto_close=True)
                none_item.tooltip("Clear the value — pass nothing")
                reset_item.tooltip(f"Back to {defn._default!r}")
            if ctx.developer_mode:
                _build_developer_menu(
                    ctx,
                    ("Settings source", _bag_source_key(obj)),
                    ("Panel source", _component_key(drawing_panel())),
                )
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
    row_props += f' data-ui-state="{obj._effective_ui_state(attr_name).name.lower()}"'

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
        state = obj._effective_ui_state(attr_name)
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

        obj._subscribe_field(_controller, _on_controller_changed)

        def _unsubscribe(cb: Callable[[Any, Any], None] = _on_controller_changed) -> None:
            obj._unsubscribe(cb)

        anchor_cleanup_to_element(row_element, _unsubscribe)

    def _refresh_chrome():
        # value_apply is set only for the unknown-widget label fallback, which
        # has no cell subscription of its own; real widgets hear the cell
        # directly. The rest is override chrome, refreshed live so an edit
        # shows its • and reset without a panel redraw.
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

    An unknown widget key falls back to a read-only label, so a missing widget
    never renders a silent blank.

    Args:
        bag: Supplies the instance cell to bind when *cell* is not given.
        cell: The registry-owned cell to bind instead.
        on_edit: Write-policy closure every edit routes through, never raw
            into the cell.

    Returns:
        ``(apply_callback, set_enabled)``. ``apply_callback`` is ``None`` for
        a real widget, which hears cell writes itself, and the label
        fallback's ``apply(value)`` otherwise. ``set_enabled`` is never
        ``None``.
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

    # BaseWidget.render() anchors cleanup to client disconnect, not element
    # deletion, so a panel re-render leaves the old widget subscribed to the
    # shared cell and a later edit syncs a deleted element. cleanup() is
    # idempotent, so this is safe alongside the disconnect hook.
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
    """Best-effort canvas pin refresh after a promote or demote from the row menu.

    Requests a redraw the debounced validation pass picks up; a node with no
    graph, as in headless tests, is skipped. Never publishes synchronously: a
    redraw of the emitting panel from inside its own click handler deletes the
    handler's slot mid-flight (``.insights/feedback_nicegui_async.md``).
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
        descriptor = type(obj)._settings_descriptors().get(attr_name)
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
    """Clear *key*'s workspace tier and save, so it falls back to global or default.

    The save is not optional: only set values are written, so persisting is
    what drops the key from the workspace JSON, and without it the old value
    returns on the next load. The global tier, hand-edited and never written
    by the app, is untouched.
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
