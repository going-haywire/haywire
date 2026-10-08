"""A port's edges in two sets: those ending at it (incoming) and those leaving it (outgoing)."""

import pytest

from haywire.barn.builtin.types import CALLBACK, EXEC, FLOAT
from haywire.core.types import DataPort, PortType
from haywire.core.types.link_set import LinkSet

pytestmark = pytest.mark.unit


def _port(type_cls, port_type, **kwargs) -> DataPort:
    return DataPort(
        registry_id="p",
        registry_key=type_cls.class_identity.registry_key,
        label="P",
        id="p",
        type_cls=type_cls,
        port_type=port_type,
        **kwargs,
    )


@pytest.mark.parametrize("port_type", [PortType.INLET, PortType.OUTLET, PortType.SWINGLET, PortType.CONFIG])
def test_every_port_has_both_sets(port_type):
    port = _port(FLOAT, port_type)
    assert isinstance(port.incoming, LinkSet)
    assert port.incoming.is_incoming
    assert isinstance(port.outgoing, LinkSet)
    assert not port.outgoing.is_incoming
    assert port.incoming.linked == {}
    assert port.outgoing.all == {}


@pytest.mark.parametrize(
    ("type_cls", "incoming_many", "outgoing_many"),
    [(FLOAT, False, True), (EXEC, True, False), (CALLBACK, False, True)],
)
def test_each_set_takes_its_half_of_the_ceiling(type_cls, incoming_many, outgoing_many):
    port = _port(type_cls, PortType.SWINGLET)
    assert port.incoming.takes_many is incoming_many
    assert port.outgoing.takes_many is outgoing_many


def test_a_visual_swinglet_takes_many_at_both_ends():
    from haybale_testing.types import TEST_VISUAL

    port = _port(TEST_VISUAL, PortType.SWINGLET)
    assert port.incoming.takes_many
    assert port.outgoing.takes_many


def test_single_link_narrows_both_sets():
    port = _port(FLOAT, PortType.SWINGLET, single_link=True)
    assert not port.incoming.takes_many
    assert not port.outgoing.takes_many


def test_takes_many_links_reads_the_receiving_set_except_on_an_outlet():
    assert _port(EXEC, PortType.SWINGLET).takes_many_links is True
    assert _port(EXEC, PortType.INLET).takes_many_links is True
    assert _port(EXEC, PortType.OUTLET).takes_many_links is False
