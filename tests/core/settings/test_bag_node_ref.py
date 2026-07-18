import pytest


@pytest.mark.integration
def test_bag_receives_node_via_constructor(make_node_with_setting):
    """The settings bag holds a plain _node attribute set through __init__,
    not via object.__setattr__ monkeypatching."""
    node = make_node_with_setting(accessor="filter", field="threshold")
    assert node.filter._node is node


def test_standalone_bag_defaults_node_to_none():
    """A bag built without a node (Framework/Library settings) has _node = None."""
    from haywire.core.settings.settings import Settings

    bag = Settings()
    assert bag._node is None
