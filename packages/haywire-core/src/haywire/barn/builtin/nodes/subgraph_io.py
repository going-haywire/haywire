"""The two boundary nodes that define a Subgraph's interface.

``SubgraphInputNode`` and ``SubgraphOutputNode`` ship **port-less**: ``init()``
declares no ports. The collapse action derives the interface from the edges that
cross the selection and stamps the ports onto them; from then on those ports are
the interface, and the Graph-node card mirrors their shape.

Both are ``NodeType.BOUNDARY``, which carries neither the DATA nor the CONTROL
bit, so one pair of classes serves data and control crossings alike. That also
keeps them out of ``_execute``'s data-node shortcut, which skips a worker whose
node has no dirty port — a boundary node has nothing feeding it and must run
regardless.

They execute as ordinary nodes in the host's flow: the Subgraph Input copies the
card's inlet values onto its own outlets, and the Subgraph Output copies its
inlet values onto the card's outlets. Each write fires that port's own pipes, so
every value travels the rest of the way over real edges. Control reaches them
across virtual crossings the assembler's view supplies — see
``haywire.core.graph.subgraph_crossing``.

The port-less state is legal because the nodes are ``NodeType.BOUNDARY`` — the
structural validator accepts a boundary node with no ports (see
``_validate_boundary_node``).

These nodes live in the framework-owned **builtin** library so headless graphs
can always load a Subgraph without importing any display-only library: they
declare their skin by registry-key *string* on their own ``props`` bag, never
importing the skin class.
"""

from __future__ import annotations

from haywire.barn.builtin.types import CHOICES
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.graph.subgraph_crossing import (
    boundary_port_id,
    copy_inward,
    copy_outward,
    crossed_enter_id,
    exit_crossing_id,
)
from haywire.core.node import node, BaseNode, NodeType
from haywire.core.settings import setting
from haywire.core.settings.descriptor import UiState
from haywire.core.types import FlowType

_SKIN_KEY = "haywire-core:skin:SubgraphIOSkin"


@node(
    label="Subgraph Input",
    description="Defines the inlets of the Graph-node that owns this Subgraph.",
    node_type=NodeType.BOUNDARY,
    hidden=True,
    _is_subgraph_input=True,
)
class SubgraphInputNode(BaseNode):
    """Carries only **outlets** — the values arriving from the parent graph.

    Named for the side it represents on the Graph-node card, not for its own
    ports: it is the card's *input* side, so inside the Subgraph it hands those
    values out. Each outlet here becomes one inlet on the Graph-node.

    Ships port-less; the collapse action stamps the interface. The port ids are
    chosen by that action, so this node never names a fixed id.
    """

    # Subclasses the INHERITED bag (BaseNode.props), not NodeProperties: the
    # inherited bag is what @node's conflict check compares against, and it is
    # itself a NodeProperties subclass, so anything it declares is kept too.
    # mypy sees BaseNode.props as the `props: NodeProperties` instance
    # annotation from BaseNode's TYPE_CHECKING branch, hence the ignore.
    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        """Overrides the framework ``skin`` prop; inherits every other field.

        A boundary node renders in exactly one skin — that is a constraint of
        what the node IS, so this replaces ``NodeProperties.skin``'s ``graph()``
        mirror with a plain field: the graph's (or studio's) default skin never
        reaches a boundary node, and "reset to default" returns HERE.

        Bound by registry-key STRING, never by importing the skin class:
        importing it would pull haywire.ui + nicegui onto the headless
        execution path. The renderer resolves the key lazily at render time.
        """

        skin = setting[CHOICES](
            _SKIN_KEY,
            label="Skin",
            description="Boundary nodes always use the subgraph rail skin",
            category="appearance",
            order=10,
        )

    def init(self) -> None:
        # No ports. The collapse action stamps the interface right after creation.
        pass

    def post_init(self) -> None:
        # Whole-category chrome gating; the skin binding itself is declared on
        # the props bag above. Runs on both fresh creation and load.
        for cat in ("state", "appearance", "annotation", "layout"):
            self.props._set_ui_state_all(UiState.HIDDEN, category=cat)

    def worker(self, context: ExecutionContext) -> str | None:
        """Hand the card's inlet values to the Subgraph, and control with them.

        Entered through a virtual ``enter_`` crossing naming the card control
        inlet the Graph-node was entered by; leaves through this node's matching
        real control outlet, so a Subgraph with several control inlets routes
        each to its own interior chain.

        Returns the control outlet to follow, or ``None`` when the Subgraph is
        crossed by data alone and there is no control chain to continue.
        """
        card = self._card()
        if card is not None:
            copy_inward(card, self)

        entered_by = crossed_enter_id(context.control_pin or "")
        if entered_by is None:
            return None
        # The crossing names a CARD inlet; this node's outlets are named from
        # the boundary side, which is what the card's pins mirror.
        outlet_id = boundary_port_id(entered_by)
        return outlet_id if outlet_id in self.ports else None

    def _card(self) -> BaseNode | None:
        """The Graph-node whose card this Subgraph sits behind, or ``None``."""
        definition = self.wrapper.graph if self.wrapper else None
        if not isinstance(definition, SubgraphDefinition):
            return None
        wrapper = definition.graph_node_wrapper()
        return wrapper.node if wrapper is not None else None


@node(
    label="Subgraph Output",
    description="Defines the outlets of the Graph-node that owns this Subgraph.",
    node_type=NodeType.BOUNDARY,
    hidden=True,
    _is_subgraph_output=True,
)
class SubgraphOutputNode(BaseNode):
    """Carries only **inlets** — the values leaving for the parent graph.

    Named for the side it represents on the Graph-node card, not for its own
    ports: it is the card's *output* side, so inside the Subgraph it collects
    those values in. Each inlet here becomes one outlet on the Graph-node.

    Ships port-less; the collapse action stamps the interface. The port ids are
    chosen by that action, so this node never names a fixed id.
    """

    class props(BaseNode.props):  # type: ignore[valid-type,misc]
        """Overrides the framework ``skin`` prop; inherits every other field.

        See ``SubgraphInputNode.props``.
        """

        skin = setting[CHOICES](
            _SKIN_KEY,
            label="Skin",
            description="Boundary nodes always use the subgraph rail skin",
            category="appearance",
            order=10,
        )

    def init(self) -> None:
        # No ports. The collapse action stamps the interface right after creation.
        pass

    def post_init(self) -> None:
        for cat in ("state", "appearance", "annotation", "layout"):
            self.props._set_ui_state_all(UiState.HIDDEN, category=cat)

    def worker(self, context: ExecutionContext) -> str | None:
        """Hand the Subgraph's results to the card, and control back out with them.

        Entered through one of this node's real control inlets; leaves through
        the matching virtual ``exit_`` crossing, which carries control to the
        Graph-node's exit hop. A Subgraph with several control inlets here — one
        per exec exit of the interior, such as a Switch's two — routes each to
        its own outlet on the card.

        Returns the crossing to follow, or ``None`` when the Subgraph is crossed
        by data alone.
        """
        card = self._card()
        if card is not None:
            copy_outward(self, card)

        # In a data-only Subgraph this node runs inside a host control node's
        # data flow, so control_pin holds THAT node's inlet; only one of this
        # node's own control inlets names a crossing back to the card.
        entered_by = context.control_pin
        if entered_by is None:
            return None
        inlet = self.ports.get(entered_by)
        if inlet is None or inlet.flow_type is not FlowType.CONTROL:
            return None
        return exit_crossing_id(entered_by)

    def _card(self) -> BaseNode | None:
        """The Graph-node whose card this Subgraph sits behind, or ``None``."""
        definition = self.wrapper.graph if self.wrapper else None
        if not isinstance(definition, SubgraphDefinition):
            return None
        wrapper = definition.graph_node_wrapper()
        return wrapper.node if wrapper is not None else None
