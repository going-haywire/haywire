"""InsetView — a Subgraph's stage drawn inside another card.

The Inset skin's body: one ordinary card per staged interior node, each drawn
with its stage skin at its stage position. The view is static: the host card
redraws whenever the interior changes visually, which builds a new view.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from haywire.core.graph.types import ChangeReason
from haywire.core.node.layout import STAGE

from .ui_node import UINode

if TYPE_CHECKING:
    from haywire.core.graph.edit_route import EditRoute
    from haywire.core.graph.subgraph import SubgraphDefinition
    from haywire.ui.skin.factory import SkinFactory


class InsetView:
    """The staged nodes of one Subgraph, each drawn by its own UINode with its stage skin.

    Builds its cards into *body* when constructed: stage (0, 0) is the body's
    top-left corner, and cards stack by ``stage_z``, ties in creation order. Each
    card writes through *route*'s :meth:`~EditRoute.for_subgraph` route, so at the
    host level's mode; with no route, its widgets refuse every write. A card's
    container carries ``data-hw-inset-node``, never ``data-node-id``, so the host
    canvas does not take it for one of its own nodes.

    Example::

        with body:
            view = InsetView(body, card.node.resolve_definition(), skin_factory, host_route)
        ...
        view.cleanup()   # when the host card is redrawn or torn down
    """

    def __init__(
        self,
        body: ui.element,
        definition: SubgraphDefinition | None,
        factory: SkinFactory,
        route: EditRoute | None,
    ) -> None:
        self._cards: dict[str, UINode] = {}
        if definition is None:
            return
        interior_route = route.for_subgraph(definition) if route is not None else None
        staged = [w for w in definition.node_wrappers.values() if STAGE.includes(w.node.props)]
        staged.sort(key=lambda w: w.node.props.stage_z)
        with body:
            for wrapper in staged:
                x, y = wrapper.node.props.get_position(STAGE)
                with (
                    ui.element("div")
                    .classes("absolute")
                    .style(f"left: {x}px; top: {y}px; transform-origin: top-left;")
                    .props(f'data-hw-inset-node="{wrapper.node_id}"') as container
                ):
                    card = UINode(container, wrapper, factory, interior_route, channel=STAGE)
                    card.refresh(ChangeReason.NODE_ADDED)
                self._cards[wrapper.node_id] = card

    @property
    def cards(self) -> dict[str, UINode]:
        """Each staged interior node's card, by node id."""
        return self._cards

    def cleanup(self) -> None:
        """Release every card's subscriptions; their DOM goes with the host card's."""
        cards, self._cards = self._cards, {}
        for card in cards.values():
            card.teardown_subscriptions()
