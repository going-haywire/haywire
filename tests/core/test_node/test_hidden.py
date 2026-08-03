"""Hidden nodes are registered and usable but never offered in selection UIs.

Smoke coverage for the `hidden` field on BaseIdentity: a node with
``@node(hidden=True)`` is excluded from the create menu (``get_menu_structure``)
and node search (``search_nodes``), while a visible node is not. Also confirms
the converged behaviour that an empty ``menu=""`` routes a *visible* node to the
top-level ``misc`` category rather than hiding it.
"""

from typing import Any, cast

import pytest

from haywire.core.node import node, BaseNode, NodeFactory, NodeRegistry


@pytest.mark.unit
@pytest.mark.core
def test_hidden_node_absent_from_menu(node_registry: NodeRegistry):
    @node(registry_id="visible_node", label="Visible Node", menu="test/basic")
    class VisibleNode(BaseNode):
        def init(self):
            pass

    @node(registry_id="hidden_node", label="Hidden Node", menu="test/basic", hidden=True)
    class HiddenNode(BaseNode):
        def init(self):
            pass

    node_registry._register_class(cast(Any, VisibleNode), VisibleNode.class_library)
    node_registry._register_class(cast(Any, HiddenNode), HiddenNode.class_library)

    factory = NodeFactory(node_registry)

    menu = factory.get_menu_structure()
    labels_in_menu = {ni.identity.label for nodes in menu.values() for ni in nodes}
    assert "Visible Node" in labels_in_menu
    assert "Hidden Node" not in labels_in_menu

    # Hidden node is also unfindable in search.
    search_labels = {ni.identity.label for ni in factory.search_nodes("Node")}
    assert "Visible Node" in search_labels
    assert "Hidden Node" not in search_labels


@pytest.mark.unit
@pytest.mark.core
def test_empty_menu_routes_visible_node_to_misc(node_registry: NodeRegistry):
    """An explicit empty menu no longer hides — it lands under the top-level 'misc' bucket."""

    @node(registry_id="uncategorized_node", label="Uncategorized Node", menu="")
    class UncategorizedNode(BaseNode):
        def init(self):
            pass

    node_registry._register_class(cast(Any, UncategorizedNode), UncategorizedNode.class_library)

    menu = NodeFactory(node_registry).get_menu_structure()
    assert "misc" in menu
    assert "Uncategorized Node" in {ni.identity.label for ni in menu["misc"]}
