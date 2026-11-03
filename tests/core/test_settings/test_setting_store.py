"""setting(store=...): a field the graph does not save."""

import pytest

from haywire.barn.builtin.types import INT
from haywire.core.settings import NodeSettings, setting, shadow
from haywire.core.types.enums import PortType, StoreStrategy

pytestmark = pytest.mark.unit


class _Bag(NodeSettings):
    kept = setting[INT](1)
    computed = setting[INT](2, store=StoreStrategy.NEVER, promote_default=PortType.OUTLET)


def test_an_unsaved_field_is_left_out_but_its_promotion_is_kept():
    bag = _Bag()
    bag.kept = 5
    bag.computed = 7
    data = bag._to_dict()
    assert data["values"] == {"kept": 5}
    assert "computed" in data["promoted"]


def test_saved_reads_the_declaration():
    assert _Bag.kept.saved is True
    assert _Bag.computed.saved is False


def test_a_mirror_takes_its_source_choice_unless_given_one():
    class _Mirrors(NodeSettings):
        same = shadow(_Bag.computed)
        own = shadow(_Bag.computed, store=StoreStrategy.ALWAYS)

    assert _Mirrors.same.saved is False
    assert _Mirrors.own.saved is True


@pytest.mark.parametrize("store", [StoreStrategy.HAS_WIDGET, StoreStrategy.NODE_SET, StoreStrategy.NONE])
def test_only_always_and_never_are_accepted(store):
    with pytest.raises(TypeError):
        setting[INT](0, store=store)
