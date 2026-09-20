"""The Ports panel's edit affordance: what it offers, and on which ports.

The rendering itself is verified in the studio; these cover the decisions
behind it — which ports the pen is live on, what the row's tooltip says, and
the model that backs the default-value editor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import PortOrigin
from haywire.ui.panel.port_default_widget_model import PortDefaultWidgetModel

from haybale_graph_editor.panels.properties.introspect.node_ports import _identity_tooltip

from tests.conftest import make_node

if TYPE_CHECKING:
    from haybale_graph_editor.protocols import GraphContainer
    from haywire.ui.widget.base import BaseWidget

pytestmark = [pytest.mark.integration]

_ADD = "haybale-testing:node:TestAddFloatNode"


@pytest.fixture
def ports(graph_with_library_system: BaseGraph):
    """One port of each origin, plus a documented one."""
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)
    with wrapper.node.rejig():
        wrapper.node.add(FLOAT.as_inlet("declared", label="Declared", origin=PortOrigin.DECLARED))
        wrapper.node.add(FLOAT.as_inlet("resolved", label="Resolved", origin=PortOrigin.RESOLVED))
        wrapper.node.add(
            FLOAT.as_inlet(
                "documented",
                label="Documented",
                description="How strict the filter is",
                origin=PortOrigin.RESOLVED,
            )
        )
    return wrapper.node.ports


class TestWhichPortsAreEditable:
    def test_a_resolved_port_is(self, ports):
        assert ports["resolved"].origin is PortOrigin.RESOLVED

    def test_a_declared_port_is_not(self, ports):
        assert ports["declared"].origin is not PortOrigin.RESOLVED


class TestTheRowTooltip:
    def test_it_carries_the_port_id(self, ports):
        assert _identity_tooltip(ports["resolved"]).startswith("resolved")

    def test_it_carries_an_authored_description(self, ports):
        tooltip = _identity_tooltip(ports["documented"])

        assert "documented" in tooltip
        assert "How strict the filter is" in tooltip

    def test_it_leaves_out_the_types_own_blurb(self, ports):
        """An undocumented port inherits its type's description; every port of
        that type would repeat it, so it is noise rather than documentation."""
        port = ports["resolved"]

        assert port.description == port.type_cls.class_identity.description
        assert _identity_tooltip(port) == "resolved"


class TestTheDefaultValueModel:
    @pytest.fixture
    def port_with_default(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT

        graph = graph_with_library_system
        wrapper = make_node(graph, _ADD)
        with wrapper.node.rejig():
            wrapper.node.add(FLOAT.as_inlet("gain", default=0.75, origin=PortOrigin.RESOLVED))
        return wrapper.node.ports["gain"]

    def test_it_starts_at_the_ports_default(self, port_with_default):
        model = PortDefaultWidgetModel(port_with_default, on_edit=lambda _v: None)

        assert model.get_value() == pytest.approx(0.75)

    def test_it_takes_the_ports_widget_config(self, port_with_default):
        """So the editor renders with the port's own bounds."""
        model = PortDefaultWidgetModel(port_with_default, on_edit=lambda _v: None)

        assert model.widget_config == dict(port_with_default.widget_config or {})

    def test_editing_reports_the_value(self, port_with_default):
        seen: list[float] = []
        model = PortDefaultWidgetModel(port_with_default, on_edit=seen.append)

        model.set_value(0.25)

        assert seen == [pytest.approx(0.25)]

    def test_editing_leaves_the_port_alone(self, port_with_default):
        """An abandoned dialog must not have moved anything."""
        model = PortDefaultWidgetModel(port_with_default, on_edit=lambda _v: None)

        model.set_value(0.25)

        assert port_with_default.default == {"value": 0.75}
        assert port_with_default.get_value() == pytest.approx(0.75)

    def test_as_default_is_the_shape_the_port_stores(self, port_with_default):
        model = PortDefaultWidgetModel(port_with_default, on_edit=lambda _v: None)
        model.set_value(0.25)

        assert model.as_default() == {"value": 0.25}


class TestFindingTheEditor:
    """The panel is handed a graph; the editor has to be found from it.

    Only documents are registered in ``GraphAppState`` — the container for an
    open Group is the graph editor's own — so a Group's graph finds none, and
    the panel must still produce an editor or the pen does nothing.
    """

    def test_a_subgraph_is_not_in_the_app_state(self, graph_with_library_system: BaseGraph):
        """The premise: this is why looking the container up is not enough."""
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        graph = graph_with_library_system
        definition = graph.add_subgraph(
            SubgraphDefinition(key="sg", label="G", validation_scheduler=SyncScheduler())
        )
        app_state = GraphAppState()

        assert app_state.get_by_graph(definition) is None

    def test_the_host_history_is_found_for_a_subgraph(self, graph_with_library_system, library_system):
        """An edit inside a Group records on the document's history."""
        from haywire.core.graph.editor import Editor
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haybale_graph_editor.panels.properties.introspect.node_ports import _host_history
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        graph = graph_with_library_system
        definition = graph.add_subgraph(
            SubgraphDefinition(key="sg", label="G", validation_scheduler=SyncScheduler())
        )
        document_editor = Editor(graph, library_system.get_node_factory())

        app_state = GraphAppState()
        app_state.register(cast("GraphContainer", _FakeContainer(document_editor)))

        assert _host_history(app_state, definition) is document_editor.history_manager

    def test_a_nested_subgraph_reaches_the_same_history(self, graph_with_library_system, library_system):
        from haywire.core.graph.editor import Editor
        from haywire.core.graph.scheduler import SyncScheduler
        from haywire.core.graph.subgraph import SubgraphDefinition
        from haybale_graph_editor.panels.properties.introspect.node_ports import _host_history
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        graph = graph_with_library_system
        outer = graph.add_subgraph(
            SubgraphDefinition(key="outer", label="O", validation_scheduler=SyncScheduler())
        )
        inner = outer.add_subgraph(
            SubgraphDefinition(key="inner", label="I", validation_scheduler=SyncScheduler())
        )
        document_editor = Editor(graph, library_system.get_node_factory())

        app_state = GraphAppState()
        app_state.register(cast("GraphContainer", _FakeContainer(document_editor)))

        assert _host_history(app_state, inner) is document_editor.history_manager

    def test_a_graph_no_document_claims_gets_its_own(self, graph_with_library_system, library_system):
        """Better a private history than silently recording nowhere."""
        from haywire.core.graph.editor import Editor
        from haybale_graph_editor.panels.properties.introspect.node_ports import _host_history
        from haybale_graph_editor.state.graph_app_state import GraphAppState

        graph = graph_with_library_system
        Editor(graph, library_system.get_node_factory())

        assert _host_history(GraphAppState(), graph) is None


class _FakeContainer:
    """The two attributes ``_host_history`` reads off a container."""

    def __init__(self, editor) -> None:
        self.editor = editor
        self.binding_id = "doc"
        self.display_name = "doc"
        self.path = None
        self.unsaved = False

    def save(self, save_as=None):
        return None


class TestTheWidgetActuallyBuilds:
    """The model has to satisfy what the widget construction path reads.

    ``WidgetFactory.render_widget`` is not that path: it takes a real
    ``DataPort`` and reads ``promoted``/``_node`` to decide whether to route
    writes through a setting, so handing it a model raises ``AttributeError``
    before the widget is ever constructed. The dialog builds from the widget
    class directly, as the Properties panel does for a settings field.
    """

    @pytest.fixture
    def model_for(self, graph_with_library_system: BaseGraph):
        from haywire.barn.builtin.types import FLOAT

        graph = graph_with_library_system
        wrapper = make_node(graph, _ADD)
        with wrapper.node.rejig():
            wrapper.node.add(FLOAT.as_inlet("gain", default=0.75, origin=PortOrigin.RESOLVED))
        port = wrapper.node.ports["gain"]
        return port, PortDefaultWidgetModel(port, on_edit=lambda _v: None)

    def test_the_port_declares_a_widget_to_render(self, model_for):
        port, _model = model_for

        assert port.widget_key is not None

    def test_that_widget_class_resolves(self, model_for):
        from haywire.ui.widget.globals import get_widget_class

        port, _model = model_for

        assert get_widget_class(port.widget_key) is not None

    def test_the_widget_constructs_against_the_model(self, model_for):
        """The regression: the widget must accept the model, not just a port."""
        from haywire.ui.widget.globals import get_widget_class

        port, model = model_for
        widget_cls = get_widget_class(port.widget_key)
        assert widget_cls is not None

        widget = widget_cls(model)

        # get_value is BaseWidget's, not on the IWidget interface get_widget_class returns.
        assert cast("BaseWidget", widget).get_value() == pytest.approx(0.75)

    def test_the_model_satisfies_the_widget_model_protocol(self, model_for):
        _port, model = model_for

        assert isinstance(model.id, str)
        assert isinstance(model.widget_config, dict)
        assert model.data is not None
        assert callable(model.get_value)
        assert callable(model.set_value)
