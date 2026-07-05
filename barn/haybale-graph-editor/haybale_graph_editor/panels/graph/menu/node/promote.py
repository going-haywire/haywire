# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py
"""Node right-click 'Promote setting' submenu.

Lists every ``setting()`` field on the right-clicked node that is not already
promoted, and lets the user promote it to a DATA **inlet or outlet** per the P5
eligibility rule (ADR 0014): a read-only ``watch()`` field is outlet-only;
``shadow()`` and plain fields can be promoted either way. The matching 'Detach
from setting' panel on the pin menu lives in ``../port/port.py``.

The settings are rendered as a hierarchical **flyout menu** — a single
``➕ Promote Setting`` entry unfolding on hover to ``bag ▸ field ▸ direction``
(mirroring the add-node menu). A field with a single eligible direction collapses
to a labeled leaf (``field → outlet``); a two-direction field stays a
``field ▸ [inlet|outlet]`` flyout. The bag level is always rendered. The shared
hover/sibling-close mechanics live in ``haywire.ui.elements.flyout``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.types.enums import PortType

from haywire.ui import elements as hui
from haywire.ui.elements.flyout import FlyoutSiblings, flyout_category
from haywire.ui.panel import BasePanel
from haywire.ui.panel.layout import PanelLayout
from haywire.ui.panel.decorator import panel

from .....focuses import SelectionFocus
from .....state.edit_state import EditState
from .....editors.graph_canvas.handlers.context_menu_actions import SelectionContextActions

if TYPE_CHECKING:
    from haywire.core.session.context import SessionContext


def promotable_fields(node) -> list[tuple[str, str, tuple[PortType, ...]]]:
    """Return ``(accessor, field, directions)`` for every ``setting()`` on *node*
    that is not already promoted, where *directions* are the eligible
    ``PortType``s per the two-flag rule (ADR 0014):

    * a read-only (``watch()``) field ⇒ ``(OUTLET,)`` — it has no write path in.
    * any writable field (plain / ``shadow()``) ⇒ ``(INLET, OUTLET)``.

    *node* is a ``NodeData`` instance (the ``NodeWrapper.node``).
    """
    out: list[tuple[str, str, tuple[PortType, ...]]] = []
    for accessor in type(node)._settings_bags:
        bag = getattr(node, accessor)
        # MRO-aware (matches is_field_promoted/_resolve_promoted) so a field inherited
        # from a settings-bag base class is offered too, not just one declared directly.
        for field, desc in type(bag)._property_settings().items():
            # already promoted -> skip. The promoted port's id is the setting's
            # storage_key (ADR 0015).
            if desc.storage_key in node.ports:
                continue
            if getattr(desc, "_read_only", False):
                directions: tuple[PortType, ...] = (PortType.OUTLET,)
            else:
                directions = (PortType.INLET, PortType.OUTLET)
            out.append((accessor, field, directions))
    return out


def field_description(node, accessor: str, field: str) -> str:
    """Return the ``description=`` help text of *field* on *node*'s *accessor* bag,
    or ``""`` when none was declared. Surfaced as the flyout item's tooltip."""
    bag = getattr(node, accessor)
    desc = type(bag)._property_settings().get(field)
    return getattr(desc, "_description", "") if desc is not None else ""


def promotable_by_bag(node) -> dict[str, list[tuple[str, tuple[PortType, ...], str]]]:
    """Group :func:`promotable_fields` by settings-bag accessor.

    Returns ``{accessor: [(field, directions, description), ...]}`` preserving
    declaration order, so the flyout renders one ``bag ▸`` category per settings
    bag with its promotable fields beneath. ``description`` is the field's help
    text (``""`` when absent). Bags with no promotable field are omitted.
    """
    by_bag: dict[str, list[tuple[str, tuple[PortType, ...], str]]] = {}
    for accessor, field, directions in promotable_fields(node):
        description = field_description(node, accessor, field)
        by_bag.setdefault(accessor, []).append((field, directions, description))
    return by_bag


_DIRECTION_LABEL = {PortType.INLET: "inlet", PortType.OUTLET: "outlet"}


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Promote Setting",
    icon=hui.icon.promote,
    order=00,
)
class PromoteSettingMenuPanel(BasePanel):
    """Node right-click panel listing promotable settings; clicking one promotes it
    in the chosen direction.

    Shown only for a single-node selection (the menu acts on the active node).
    """

    actions: SelectionContextActions

    @classmethod
    def poll(cls, ctx: "SessionContext") -> bool:
        edit = ctx.data[EditState]
        # Single-node selection only — promotion targets one node's settings.
        if edit.selected_edges or len(edit.selected_nodes) != 1:
            return False
        wrapper = edit.active_node
        return wrapper is not None and bool(promotable_fields(wrapper.node))

    def draw(self, ctx: "SessionContext", layout: PanelLayout) -> None:
        wrapper = ctx.data[EditState].active_node
        if wrapper is None:
            return
        node_id = wrapper.node_id
        by_bag = promotable_by_bag(wrapper.node)
        with layout:
            # Single collapsed entry unfolding on hover into `bag ▸ field ▸ direction`,
            # mirroring the add-node menu's `➕ Add Nodes` flyout.
            with hui.button(
                "Promote ...", 
                icon=hui.icon.promote, 
                tooltip="Promote settings to inlets or outlets"
            ):
                with ui.menu().props(hui.FLYOUT_PROPS).style(hui.FLYOUT_Z):
                    # Bag flyouts are siblings: opening one closes the rest.
                    bag_siblings: FlyoutSiblings = []
                    for accessor, fields in by_bag.items():
                        self._draw_bag(node_id, accessor, fields, bag_siblings)

    def _draw_bag(
        self,
        node_id: str,
        accessor: str,
        fields: list[tuple[str, tuple[PortType, ...], str]],
        siblings: FlyoutSiblings,
    ) -> None:
        """Render one `bag ▸` category holding its promotable fields."""
        with flyout_category(f"📁 {accessor}", siblings) as field_siblings:
            for field, directions, description in fields:
                self._draw_field(node_id, accessor, field, directions, description, field_siblings)

    def _draw_field(
        self,
        node_id: str,
        accessor: str,
        field: str,
        directions: tuple[PortType, ...],
        description: str,
        siblings: FlyoutSiblings,
    ) -> None:
        """Render one field: a labeled leaf when it has a single eligible
        direction, or a `field ▸ [inlet|outlet]` flyout when it has both.

        A collapsed leaf carries the field's ``description`` as a tooltip; a
        two-direction flyout carries it on the ``field ▸`` anchor row instead, so
        the help text is reachable however the field renders."""
        if len(directions) == 1:
            direction = directions[0]
            verb = _DIRECTION_LABEL[direction]
            item = ui.menu_item(
                f"{field} → {verb}",
                lambda a=accessor, f=field, d=direction: self.actions.promote_setting(node_id, a, f, d),
            ).props("dense")
            if description:
                hui.menu_item_tooltip(item, description)
            return

        with flyout_category(field, siblings, tooltip=description):
            for direction in directions:
                verb = _DIRECTION_LABEL[direction]
                ui.menu_item(
                    verb,
                    lambda a=accessor, f=field, d=direction: self.actions.promote_setting(node_id, a, f, d),
                ).props("dense")
