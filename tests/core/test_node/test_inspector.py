"""Unit tests for NodeInstanceInspector against real, library-loaded node instances."""

import pytest

from haywire.core.node.inspector import NodeInstanceInspector, PortInfo, SettingInfo


@pytest.mark.integration
@pytest.mark.core
def test_ports_returns_portinfo_with_schema_shape(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    inspector = NodeInstanceInspector(wrapper.node)

    ports = inspector.ports()
    assert isinstance(ports, list)
    assert ports
    for p in ports:
        assert isinstance(p, PortInfo)
        assert isinstance(p.id, str)
        assert p.id
        assert p.direction in ("inlet", "outlet", "config")
        assert p.flow_type in ("data", "control", "callback", "none")
        assert isinstance(p.hidden, bool)


@pytest.mark.integration
@pytest.mark.core
def test_ports_report_config_direction_distinctly(graph_with_library_system):
    """A CONFIG port must report 'config', not be collapsed into 'outlet'.

    PerformanceTester declares exec (inlet), port_count (INT config), and
    trigger (outlet) — one of each direction.
    """
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper("testing:node:PerformanceTester", position=(0, 0))
    inspector = NodeInstanceInspector(wrapper.node)

    by_id = {p.id: p.direction for p in inspector.ports()}
    assert by_id["exec"] == "inlet"
    assert by_id["port_count"] == "config"  # regression guard: was mislabeled "outlet"
    assert by_id["trigger"] == "outlet"


@pytest.mark.integration
@pytest.mark.core
def test_settings_returns_settinginfo_with_resolved_defaults(graph_with_library_system):
    graph = graph_with_library_system
    wrapper = graph.create_node_wrapper("testing:node:SettingsNode", position=(0, 0))
    inspector = NodeInstanceInspector(wrapper.node)

    settings = inspector.settings()
    assert isinstance(settings, list)
    assert settings
    for s in settings:
        assert isinstance(s, SettingInfo)
        assert isinstance(s.name, str)
        assert s.name
        assert isinstance(s.bag, str)
        assert s.bag
        assert isinstance(s.category, str)
        assert s.category
        # default must be a plain value, never a zero-arg callable left unresolved
        assert not callable(s.default)

    validated = next(s for s in settings if s.name == "even_int")
    assert validated.validator_name == "<lambda>"
    assert validated.type_name == "INT"
