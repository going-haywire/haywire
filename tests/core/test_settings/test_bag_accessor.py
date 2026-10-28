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


# --- a bag shared under different accessor names keeps one key per name ---


class Shared(NodeSettings):
    level = setting[INT](1, label="Level")


class _StubWrapper:
    graph = None
    state = None

    def mark_as_structuraly_dirty(self):
        pass


def _built(cls):
    from typing import Any, cast

    node_obj = cast(Any, cls)(node_id="n", wrapper=_StubWrapper())
    node_obj.init()
    return node_obj


def test_same_bag_twice_on_one_node_gives_two_ports(library_system):
    from haywire.core.node import BaseNode, NodeType, node
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    @node(label="Shared Twice Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _Probe(BaseNode):
        first = bag(Shared)
        second = bag(Shared)

        def init(self):
            pass

    node_obj = _built(_Probe)
    promote_setting(node_obj, "first", "level", direction=PortType.INLET)
    promote_setting(node_obj, "second", "level", direction=PortType.INLET)

    assert {"first.level", "second.level"} <= set(node_obj.ports)
    assert isinstance(node_obj.second, Shared)


def test_another_node_naming_the_bag_differently_keeps_a_saved_promotion(library_system):
    from haywire.core.node import BaseNode, NodeType, node
    from haywire.core.node.promotion import promote_setting
    from haywire.core.types.enums import PortType

    @node(label="Shared A Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _A(BaseNode):
        shared = bag(Shared)

        def init(self):
            pass

    original = _built(_A)
    promote_setting(original, "shared", "level", direction=PortType.INLET)
    saved = original.shared._to_dict()

    @node(label="Shared B Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _B(BaseNode):
        renamed = bag(Shared)

        def init(self):
            pass

    reloaded = _built(_A)
    reloaded.shared._from_dict(saved)
    reloaded._regenerate_promoted_ports()

    assert "shared.level" in reloaded.ports
    assert type(_built(_B).renamed)._settings_descriptors()["level"].storage_key == "renamed.level"
