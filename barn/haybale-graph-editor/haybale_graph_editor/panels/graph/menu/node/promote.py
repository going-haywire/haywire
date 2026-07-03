# barn/haybale-graph-editor/haybale_graph_editor/panels/graph/menu/node/promote.py
"""Node right-click 'Promote setting' submenu.

Lists every ``setting()`` field on the right-clicked node that is not already
promoted, and lets the user promote it to a DATA **inlet or outlet** per the P5
eligibility rule (ADR 0014): a read-only ``watch()`` field is outlet-only;
``shadow()`` and plain fields can be promoted either way. The matching 'Detach
from setting' panel on the pin menu lives in ``../port/port.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from haywire.core.types.enums import PortType

from haywire.ui import elements as hui
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


_DIRECTION_LABEL = {PortType.INLET: "inlet", PortType.OUTLET: "outlet"}


@panel(
    actions=SelectionContextActions,
    focus=SelectionFocus,
    label="Promote Setting",
    icon=hui.icon.add,
    order=50,
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
        with layout:
            hui.section_label("Promote Setting")
            for accessor, field, directions in promotable_fields(wrapper.node):
                for direction in directions:
                    verb = _DIRECTION_LABEL[direction]
                    hui.button(
                        f"{accessor}.{field} → {verb}",
                        icon=hui.icon.add,
                        on_click=lambda a=accessor, f=field, d=direction: self.actions.promote_setting(
                            node_id, a, f, d
                        ),
                    )
