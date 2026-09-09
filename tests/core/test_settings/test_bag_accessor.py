"""`bag()` — a typed settings-bag accessor for node classes.

Replaces the four-line `if TYPE_CHECKING: ... else: ...` alias every node
otherwise needs so a bag touched from an *annotated* method types as the bound
instance rather than the class.

The helper returns the CLASS while declaring it returns an instance, so these
tests pin the runtime half of that contract: `@node`'s bag collection walks the
class body looking for `NodeSettings` subclasses, and its "redeclare only as a
subclass" check does `issubclass`. Both must keep working. (The typing half is
enforced by mypy over this file in CI, not by an assertion.)
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, bag, setting
from haywire.core.settings.settings import Settings
from haywire.barn.builtin.types import INT

pytestmark = [pytest.mark.unit, pytest.mark.core]


class Style(NodeSettings):
    marker_size = setting[INT](3, label="Marker Size")


def test_returns_the_class_at_runtime():
    """@node's collection walk needs a NodeSettings subclass in __dict__."""
    declared = bag(Style)
    assert declared is Style
    # Runtime shape, asserted through the class object @node will actually see.
    assert isinstance(Style, type)
    assert issubclass(Style, NodeSettings)


def test_survives_the_class_body_round_trip():
    class Holder:
        style = bag(Style)

    assert Holder.__dict__["style"] is Style


def test_node_decorator_collects_a_bag_declared_this_way():
    from haywire.core.node import BaseNode, NodeType, node

    @node(label="Bag Accessor Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _Probe(BaseNode):
        style = bag(Style)

    assert _Probe._settings_bags.get("style") is Style


def test_bound_instance_is_what_the_attribute_resolves_to():
    """The fiction the helper tells is narrowly true: the ATTRIBUTE really is
    an instance, because NodeData.__init__ replaces the class placeholder."""

    class Holder:
        style = bag(Style)

    holder = Holder()
    # Stand in for what NodeData.__init__ does to every declared bag.
    object.__setattr__(holder, "style", Style(registry=create_test_settings_registry()))

    assert isinstance(holder.style, Settings)
    assert holder.style.marker_size == 3


def test_subclass_redeclaration_check_still_applies():
    """@node permits redeclaring an inherited bag only as a subclass of it —
    the `selection_bag()` pattern. bag() must not defeat that issubclass test."""

    class Extended(Style):
        extra = setting[INT](9, label="Extra")

    assert bag(Extended) is Extended
    assert issubclass(Extended, Style)
