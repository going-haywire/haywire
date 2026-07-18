"""RerouteNode: port-less default, on_startup port caching, lean worker forward."""

import pytest

pytestmark = pytest.mark.unit


def _make_reroute_node():
    """Bypass BaseNode.__init__ (requires DI context) — only need _cache for these tests."""
    from haywire.barn.builtin.nodes.reroute import RerouteNode
    from haywire.core.node.user_data import NodeCache

    node = RerouteNode.__new__(RerouteNode)
    node._cache = NodeCache()
    return node


def test_reroute_node_ships_port_less_and_flags_reroute():
    from haywire.barn.builtin.nodes.reroute import RerouteNode

    assert RerouteNode.class_identity._is_reroute is True
    # NodeType.REROUTE bit is set
    from haywire.core.node import NodeType

    assert NodeType.REROUTE in RerouteNode.class_behavior.node_type


def test_worker_returns_none_when_port_less():
    """With no ports cached, worker forwards nothing and returns None."""
    node = _make_reroute_node()
    # cache empty (on_startup not run / no ports): worker must be a no-op.
    node.cache.inlet = None
    node.cache.outlet = None
    assert node.worker(context=None) is None


def test_on_startup_caches_single_inlet_and_outlet(monkeypatch):
    """on_startup resolves exactly one inlet + one outlet into the cache."""
    from haywire.core.types.enums import PortType

    node = _make_reroute_node()

    class _FakePort:
        def __init__(self, pid):
            self.id = pid

    inlet = _FakePort("in")
    outlet = _FakePort("out")

    def fake_get_ports(is_port_type=None, has_pin=None, **kw):
        if is_port_type == PortType.INLET:
            return [inlet]
        if is_port_type == PortType.OUTLET:
            return [outlet]
        return []

    monkeypatch.setattr(node, "get_ports", fake_get_ports)
    node.on_startup(context=None)
    assert node.cache.inlet is inlet
    assert node.cache.outlet is outlet


def test_worker_forwards_inlet_to_outlet_and_returns_outlet_id():
    """worker reads cached inlet value and writes it to cached outlet, returns outlet id."""
    node = _make_reroute_node()
    written = {}

    class _Inlet:
        id = "in"

        def get_value(self):
            return 42.0

    class _Outlet:
        id = "out"

        def set_value(self, v):
            written["v"] = v

    node.cache.inlet = _Inlet()
    node.cache.outlet = _Outlet()
    result = node.worker(context=None)
    assert written["v"] == 42.0
    assert result == "out"
