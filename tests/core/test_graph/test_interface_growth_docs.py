"""An interface port is seeded from the interior, and is then the user's.

Both paths that create one — collapsing a selection, and wiring an interior
port to a boundary node's growing slot — take the naming port's label,
description, widget and default, so a Group arrives documented and presents
the affordances its interior does. All of it is ``RESOLVED`` from then on: the
Subgraph owns its interface (ADR 0036), so a user edit survives revalidation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.graph.subgraph import SubgraphDefinition
from haywire.core.types.enums import PortOrigin, PortType

from tests.conftest import make_node

if TYPE_CHECKING:
    from haywire.barn.builtin.nodes.graph_node import GraphNode

pytestmark = [pytest.mark.integration]

_ADD_FLOAT = "haybale-testing:node:TestAddFloatNode"
_INPUT = "haywire-core:node:SubgraphInputNode"
_OUTPUT = "haywire-core:node:SubgraphOutputNode"
_CARD = "haywire-core:node:GraphNode"


def _definition(graph: BaseGraph, key: str = "sg") -> SubgraphDefinition:
    return graph.add_subgraph(
        SubgraphDefinition(key=key, label="Group", validation_scheduler=SyncScheduler())
    )


def _slot(node) -> str:
    """The id of the boundary node's growing slot."""
    from haywire.barn.builtin.types import ADD

    return next(p.id for p in node.get_all_ports() if p.type_cls is not None and issubclass(p.type_cls, ADD))


@pytest.fixture
def grown_outlet(graph_with_library_system: BaseGraph):
    """A documented interior outlet wired into the Subgraph Output's slot."""
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    definition = _definition(graph)
    output_node = make_node(definition, _OUTPUT)

    producer = make_node(definition, _ADD_FLOAT)
    with producer.node.rejig():
        producer.node.add(
            FLOAT.as_outlet(
                "score",
                label="Match Score",
                description="How close the match is",
                default=0.6,
            )
        )

    slot_id = _slot(output_node.node)
    definition.create_edge_wrapper(producer.node_id, "score", output_node.node_id, slot_id)
    definition.force_validation()
    return definition, output_node, slot_id


class TestSeededFromTheOtherEnd:
    def test_the_grown_port_takes_the_source_label(self, grown_outlet):
        _definition, output_node, slot_id = grown_outlet

        assert output_node.node.ports[slot_id].label == "Match Score"

    def test_the_grown_port_takes_the_source_description(self, grown_outlet):
        """Without this the port would carry the type's generic blurb."""
        _definition, output_node, slot_id = grown_outlet

        assert output_node.node.ports[slot_id].description == "How close the match is"

    def test_the_grown_port_takes_the_source_default(self, grown_outlet):
        _definition, output_node, slot_id = grown_outlet

        assert output_node.node.ports[slot_id].default == {"value": 0.6}

    def test_the_grown_port_is_resolved(self, grown_outlet):
        """RESOLVED is what makes it the user's to rename and remove."""
        _definition, output_node, slot_id = grown_outlet

        assert output_node.node.ports[slot_id].origin is PortOrigin.RESOLVED

    def test_a_fresh_slot_takes_its_place(self, grown_outlet):
        _definition, output_node, slot_id = grown_outlet

        assert _slot(output_node.node) != slot_id


class TestTheDocsAreThenTheUsers:
    def test_a_rename_survives_revalidation(self, grown_outlet):
        """``hb_grow`` fires again on every re-link; it must not re-stamp."""
        definition, output_node, slot_id = grown_outlet
        port = output_node.node.ports[slot_id]

        port.label = "Confidence"
        port.description = "0 to 1, higher is better"
        definition.force_validation()

        after = output_node.node.ports[slot_id]
        assert after.label == "Confidence"
        assert after.description == "0 to 1, higher is better"

    def test_the_rename_serializes(self, grown_outlet):
        _definition, output_node, slot_id = grown_outlet
        port = output_node.node.ports[slot_id]
        port.label = "Confidence"

        assert port.to_dict()["kwargs"]["label"] == "Confidence"


class TestTheInputSideGrowsTheSameWay:
    def test_an_inlet_side_slot_takes_the_sinks_docs(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT

        graph = graph_with_library_system
        definition = _definition(graph, key="sg_in")
        input_node = make_node(definition, _INPUT)

        consumer = make_node(definition, _ADD_FLOAT)
        with consumer.node.rejig():
            consumer.node.add(FLOAT.as_inlet("gain", label="Gain", description="Input multiplier"))

        slot_id = _slot(input_node.node)
        definition.create_edge_wrapper(input_node.node_id, slot_id, consumer.node_id, "gain")
        definition.force_validation()

        grown = input_node.node.ports[slot_id]
        assert grown.label == "Gain"
        assert grown.description == "Input multiplier"
        assert grown.port_type is PortType.OUTLET


class TestTheWidgetTravels:
    """An interior port behind a slider gives the card a slider."""

    @pytest.fixture
    def slider_interface(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.widgets import SliderWidget
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

        graph = graph_with_library_system
        definition = _definition(graph, key="sg_widget")
        input_node = make_node(definition, _INPUT)
        consumer = make_node(definition, _ADD_FLOAT)
        with consumer.node.rejig():
            consumer.node.add(
                FLOAT.as_inlet(
                    "gain",
                    label="Gain",
                    default=0.75,
                    widget=SliderWidget.config(min=0.0, max=1.0),
                )
            )

        slot_id = _slot(input_node.node)
        definition.create_edge_wrapper(input_node.node_id, slot_id, consumer.node_id, "gain")
        definition.force_validation()

        card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg_widget"}})
        cast("GraphNode", card.node).reconcile_interface()
        return input_node, card, slot_id

    def test_the_boundary_port_takes_the_widget(self, slider_interface):
        input_node, _card, slot_id = slider_interface
        grown = input_node.node.ports[slot_id]

        assert grown.widget_key == "haywire-core:widget:SliderWidget"
        assert grown.widget_config == {"min": 0.0, "max": 1.0}

    def test_the_card_pin_takes_it_too(self, slider_interface):
        """``_mirror`` carries it the last hop, which is where it renders."""
        _input_node, card, slot_id = slider_interface
        pin = card.node.ports[f"in_{slot_id}"]

        assert pin.widget_key == "haywire-core:widget:SliderWidget"
        assert pin.widget_config == {"min": 0.0, "max": 1.0}

    def test_the_card_pin_takes_the_default(self, slider_interface):
        _input_node, card, slot_id = slider_interface

        assert card.node.ports[f"in_{slot_id}"].get_value() == pytest.approx(0.75)

    def test_the_card_pin_renders_that_widget(self, slider_interface):
        _input_node, card, slot_id = slider_interface

        assert card.node.ports[f"in_{slot_id}"].should_show_widget() is True


class TestCollapseSeedsTheSameWay:
    """The other path that mints an interface port."""

    @pytest.fixture
    def collapsed(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.widgets import SliderWidget
        from haywire.core.undo.actions.graph_actions import CollapseToGraphNodeAction

        graph = graph_with_library_system
        producer = make_node(graph, _ADD_FLOAT)
        consumer = make_node(graph, _ADD_FLOAT)
        with consumer.node.rejig():
            consumer.node.add(
                FLOAT.as_inlet(
                    "gain",
                    label="Gain",
                    description="Input multiplier",
                    default=0.75,
                    widget=SliderWidget.config(min=0.0, max=1.0),
                )
            )
        graph.create_edge_wrapper(producer.node_id, "result", consumer.node_id, "gain")
        graph.force_validation()

        action = CollapseToGraphNodeAction(
            graph=graph,
            node_ids=[consumer.node_id],
            card_registry_key=_CARD,
            input_registry_key=_INPUT,
            output_registry_key=_OUTPUT,
            label="G",
        )
        action.execute()
        graph.force_validation()
        definition = graph.get_subgraph(action.subgraph_key)
        assert definition is not None
        definition.force_validation()
        return definition, graph.get_node_wrapper(action.card_node_id)

    def _interface_port(self, definition):
        from haywire.barn.builtin.types import ADD

        return next(
            p
            for p in definition.input_node.node.get_all_ports()
            if p.type_cls is not None and not issubclass(p.type_cls, ADD)
        )

    def test_the_interface_port_takes_the_inner_label(self, collapsed):
        definition, _card = collapsed

        assert self._interface_port(definition).label == "Gain"

    def test_the_interface_port_takes_the_inner_description(self, collapsed):
        definition, _card = collapsed

        assert self._interface_port(definition).description == "Input multiplier"

    def test_the_interface_port_takes_the_inner_widget(self, collapsed):
        definition, _card = collapsed
        port = self._interface_port(definition)

        assert port.widget_key == "haywire-core:widget:SliderWidget"
        assert port.widget_config == {"min": 0.0, "max": 1.0}

    def test_the_interface_port_takes_the_inner_default(self, collapsed):
        definition, _card = collapsed

        assert self._interface_port(definition).default == {"value": 0.75}

    def test_the_card_pin_mirrors_all_of_it(self, collapsed):
        definition, card = collapsed
        port = self._interface_port(definition)
        pin = card.node.ports[f"in_{port.id}"]

        assert pin.label == "Gain"
        assert pin.description == "Input multiplier"
        assert pin.widget_key == "haywire-core:widget:SliderWidget"


class TestARenameReachesTheCard:
    """Renaming an interface port updates the Graph-node's mirrored pin.

    The card watches its definition's validation and reconciles when the batch
    requires reassembly. A rename changes no structure, so the edit has to say
    so itself — see ``SetPortMetadataAction._apply``.
    """

    @pytest.fixture
    def card_over_a_named_interface(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT
        from haywire.barn.builtin.nodes.graph_node import SUBGRAPH_KEY

        graph = graph_with_library_system
        definition = _definition(graph, key="sg_rename")
        input_node = make_node(definition, _INPUT)
        consumer = make_node(definition, _ADD_FLOAT)
        with consumer.node.rejig():
            consumer.node.add(FLOAT.as_inlet("gain", label="Gain", description="first"))

        slot_id = _slot(input_node.node)
        definition.create_edge_wrapper(input_node.node_id, slot_id, consumer.node_id, "gain")
        definition.force_validation()

        card = make_node(graph, _CARD, node_data={"store": {SUBGRAPH_KEY: "sg_rename"}})
        cast("GraphNode", card.node).reconcile_interface()
        return definition, input_node, card, slot_id

    def test_the_card_starts_with_the_seeded_name(self, card_over_a_named_interface):
        _definition, _input_node, card, slot_id = card_over_a_named_interface

        assert card.node.ports[f"in_{slot_id}"].label == "Gain"

    def test_renaming_the_interface_port_reaches_the_card(self, card_over_a_named_interface, library_system):
        from haywire.core.graph.editor import Editor

        definition, input_node, card, slot_id = card_over_a_named_interface
        editor = Editor(definition, library_system.get_node_factory())

        ok, reason = editor.set_port_metadata(input_node.node_id, slot_id, label="Confidence")
        assert (ok, reason) == (True, None)
        definition.force_validation()

        assert card.node.ports[f"in_{slot_id}"].label == "Confidence"

    def test_the_description_follows_too(self, card_over_a_named_interface, library_system):
        from haywire.core.graph.editor import Editor

        definition, input_node, card, slot_id = card_over_a_named_interface
        editor = Editor(definition, library_system.get_node_factory())

        editor.set_port_metadata(input_node.node_id, slot_id, description="0 to 1")
        definition.force_validation()

        assert card.node.ports[f"in_{slot_id}"].description == "0 to 1"

    def test_undoing_the_rename_reaches_the_card(self, card_over_a_named_interface, library_system):
        from haywire.core.graph.editor import Editor

        definition, input_node, card, slot_id = card_over_a_named_interface
        editor = Editor(definition, library_system.get_node_factory())
        editor.set_port_metadata(input_node.node_id, slot_id, label="Confidence")
        definition.force_validation()

        editor.undo()
        definition.force_validation()

        assert card.node.ports[f"in_{slot_id}"].label == "Gain"
