"""Reroute discovery via the _is_reroute identity flag + registry/factory."""

import haywire.core.graph.editor  # noqa: F401 — import first (circular-import guard)

import pytest

pytestmark = pytest.mark.unit


def test_identity_carries_is_reroute_flag():
    """A node decorated @node(_is_reroute=True) exposes it on class_identity."""
    from haywire.core.node import node, BaseNode, NodeType

    @node(node_type=NodeType.REROUTE, _is_reroute=True)
    class _RR(BaseNode):
        def init(self) -> None:
            pass

        def worker(self, context):
            return None

    assert _RR.class_identity._is_reroute is True


def test_identity_is_reroute_defaults_false():
    from haywire.core.node import node, BaseNode, NodeType

    @node(node_type=NodeType.DATA)
    class _Plain(BaseNode):
        def init(self) -> None:
            pass

        def worker(self, context):
            return None

    assert _Plain.class_identity._is_reroute is False


def test_registry_tracks_reroute_node():
    """Registering a node with _is_reroute makes it discoverable via _get_reroute_node."""
    from haywire.core.node import node, BaseNode, NodeType
    from haywire.core.node.registry import NodeRegistry

    reg = NodeRegistry()

    @node(node_type=NodeType.REROUTE, _is_reroute=True)
    class _RR(BaseNode):
        def init(self) -> None:
            pass

        def worker(self, context):
            return None

    assert reg._get_reroute_node() is None
    reg._register_class(_RR)
    assert reg._get_reroute_node() is _RR


def test_registry_clears_reroute_on_unregister():
    from haywire.core.node import node, BaseNode, NodeType
    from haywire.core.node.registry import NodeRegistry

    reg = NodeRegistry()

    @node(node_type=NodeType.REROUTE, _is_reroute=True)
    class _RR(BaseNode):
        def init(self) -> None:
            pass

        def worker(self, context):
            return None

    key = reg._register_class(_RR)
    assert reg._get_reroute_node() is _RR
    reg._unregister_class(key)
    assert reg._get_reroute_node() is None


def test_factory_exposes_reroute_node():
    """NodeFactory.get_reroute_node proxies the registry's reroute provider."""
    from haywire.core.node import node, BaseNode, NodeType
    from haywire.core.node.registry import NodeRegistry
    from haywire.core.node.factory import NodeFactory

    reg = NodeRegistry()
    factory = NodeFactory(reg)
    assert factory.get_reroute_node() is None

    @node(node_type=NodeType.REROUTE, _is_reroute=True)
    class _RR(BaseNode):
        def init(self) -> None:
            pass

        def worker(self, context):
            return None

    reg._register_class(_RR)
    assert factory.get_reroute_node() is _RR
