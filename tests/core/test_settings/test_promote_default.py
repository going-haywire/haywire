"""`setting(promote_default=...)` — an author-declared default node face.

Replaces calling `bag.promote(...)` from node code, which is a footgun: done in
`post_init()` it runs on graph load too, *after* promotions are restored, so it
silently re-promotes a field the user demoted and the demotion can never stick.

The property that makes the declarative form safe is that the seed is a
DEFAULT, not a policy: it is written at bag construction and `_from_dict`
clears the block before restoring, so a saved graph always wins — including
when what it saved is the *absence* of a promotion.
"""

import pytest

from haywire.core.di.test_config import create_test_settings_registry
from haywire.core.settings import NodeSettings, Promotable, setting
from haywire.core.types.enums import PortType
from haywire.barn.builtin.types import BOOL, INT

pytestmark = [pytest.mark.unit, pytest.mark.core]


class Faced(NodeSettings):
    """One seeded field, one not."""

    shown = setting[INT](5, label="Shown", promote_default=PortType.CONFIG)
    hidden = setting[BOOL](False, label="Hidden")


def _bag():
    return Faced(registry=create_test_settings_registry())


def test_seed_is_recorded_at_construction():
    bag = _bag()
    assert bag._get_promoted_direction("shown") is PortType.CONFIG


def test_unseeded_field_is_not_promoted():
    assert _bag()._get_promoted_direction("hidden") is None


def test_seed_serializes_like_any_promotion():
    """So a fresh node, once saved, records the face it actually had."""
    assert _bag()._to_dict()["promoted"] == {"shown": {"direction": "config"}}


def test_a_saved_graph_beats_the_seed():
    """The load path is authoritative — including for what it does NOT say."""
    bag = _bag()
    # What a graph saved after the user demoted the seeded field looks like:
    bag._from_dict({"values": {}, "promoted": {}})

    assert bag._get_promoted_direction("shown") is None, "seed survived a load and re-promoted"


def test_a_saved_promotion_is_restored_over_a_seed():
    bag = _bag()
    bag._from_dict({"values": {}, "promoted": {"shown": {"direction": "inlet"}}})

    assert bag._get_promoted_direction("shown") is PortType.INLET


def test_a_user_promotion_of_an_unseeded_field_survives():
    bag = _bag()
    bag._from_dict({"values": {}, "promoted": {"hidden": {"direction": "outlet"}}})

    assert bag._get_promoted_direction("hidden") is PortType.OUTLET
    assert bag._get_promoted_direction("shown") is None


def test_a_bag_absent_from_the_saved_data_keeps_its_seed():
    """A library adding a bag later still gets the face its author intended —
    BaseNode._initialize_from_dict only iterates bags present in the file."""
    bag = _bag()  # never _from_dict'ed, as for an unknown bag

    assert bag._get_promoted_direction("shown") is PortType.CONFIG


def test_default_must_be_a_direction_promotable_allows():
    """A declaration promote_setting() would refuse should fail loudly at
    class-definition time, not when one node fails to build."""
    with pytest.raises(ValueError, match=r"promote_default"):

        class Contradictory(NodeSettings):
            field = setting[INT](1, promotable=Promotable.CONFIG, promote_default=PortType.INLET)


def test_promotable_none_rejects_any_default():
    with pytest.raises(ValueError, match=r"allowed: none"):

        class NoneButSeeded(NodeSettings):
            field = setting[INT](1, promotable=Promotable.NONE, promote_default=PortType.CONFIG)


# --- end to end: the seed must produce a real port, and lose to a saved graph ---


class _StubWrapper:
    graph = None
    state = None

    def mark_as_structuraly_dirty(self):
        pass


def _seeded_node_cls():
    from haywire.core.node import BaseNode, NodeType, node
    from haywire.core.settings import bag

    @node(label="Promote Default Probe", menu="testing/testbed", node_type=NodeType.DATA)
    class _Probe(BaseNode):
        faced = bag(Faced)

        def init(self):
            self.add(BOOL.as_inlet("plain", label="Plain"))

    return _Probe


def test_fresh_node_gets_the_seeded_port(library_system):
    """The node author writes no promote() call at all."""
    from typing import Any, cast

    cls = _seeded_node_cls()
    node_obj = cast(Any, cls)(node_id="p", wrapper=_StubWrapper())
    node_obj.init()
    node_obj._regenerate_promoted_ports()  # what NodeWrapper._initialize now does

    assert "faced.shown" in node_obj.ports
    assert node_obj.ports["faced.shown"].port_type is PortType.CONFIG
    assert "faced.hidden" not in node_obj.ports


def test_seeded_port_lands_after_author_declared_ports(library_system):
    """Regeneration runs after init(), so the node face keeps its declared order."""
    from typing import Any, cast

    cls = _seeded_node_cls()
    node_obj = cast(Any, cls)(node_id="p", wrapper=_StubWrapper())
    node_obj.init()
    node_obj._regenerate_promoted_ports()

    assert list(node_obj.ports) == ["plain", "faced.shown"]


def test_demotion_survives_a_save_load_round_trip(library_system):
    """The bug this replaces: a promote() in post_init() came back every load."""
    from typing import Any, cast

    from haywire.core.node.promotion import demote_setting

    cls = _seeded_node_cls()
    original = cast(Any, cls)(node_id="p", wrapper=_StubWrapper())
    original.init()
    original._regenerate_promoted_ports()

    demote_setting(original, "faced.shown")
    assert "faced.shown" not in original.ports

    saved = original.faced._to_dict()

    reloaded = cast(Any, cls)(node_id="p", wrapper=_StubWrapper())
    reloaded.faced._from_dict(saved)
    reloaded._regenerate_promoted_ports()

    assert "faced.shown" not in reloaded.ports, "the seed re-promoted a demoted field on load"
