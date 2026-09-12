"""Every icon field a data type declares must reach the pin that renders it.

``DataTypeIdentity`` carries four — ``icon_in``, ``icon_in_multi``,
``icon_out``, ``icon_out_multi`` — each falling back to the widest value it
inherits (``icon_out_multi < icon_out < icon``). A field nothing reads fails
silently: the pin draws the framework default and the declaration looks
honoured.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType
from haywire.ui.skin.pin_render import _resolve_pin_icon

pytestmark = pytest.mark.unit


def _typed(**icons: str | None) -> type:
    """A FLOAT-like type whose class_identity carries *icons*."""
    # replace() is typed per-field, which a kwargs bag cannot satisfy.
    identity = dataclasses.replace(FLOAT.class_identity, **cast(Any, icons))
    return type("IconType", (FLOAT,), {"class_identity": identity})


def _port(type_cls: type, port_type: PortType, **kwargs) -> DataPort:
    return DataPort(
        registry_id="icon",
        registry_key="test:type:icon",
        label="I",
        id=f"p_{port_type.value}",
        type_cls=type_cls,
        port_type=port_type,
        flow_type=FlowType.DATA,
        **kwargs,
    )


def test_a_data_inlet_uses_icon_in():
    port = _port(_typed(icon_in="my_inlet"), PortType.INLET)
    assert _resolve_pin_icon(port) == "my_inlet"


def test_a_multi_link_data_inlet_uses_icon_in_multi():
    port = _port(_typed(icon_in_multi="my_multi"), PortType.INLET, allow_multiple_links=True)
    assert _resolve_pin_icon(port) == "my_multi"


def test_a_multi_link_inlet_falls_back_to_icon_in():
    """Each step falls through to the next-widest one that is declared."""
    port = _port(_typed(icon_in="my_inlet"), PortType.INLET, allow_multiple_links=True)
    assert _resolve_pin_icon(port) == "my_inlet"


def test_a_data_outlet_uses_icon_out():
    """The regression: outlets read icon_out_multi only, so icon_out was dead."""
    port = _port(_typed(icon_out="my_outlet"), PortType.OUTLET)
    assert _resolve_pin_icon(port) == "my_outlet"


def test_icon_out_multi_wins_on_a_multi_link_outlet():
    port = _port(_typed(icon_out="general", icon_out_multi="specific"), PortType.OUTLET)
    assert port.allow_multiple_links is True
    assert _resolve_pin_icon(port) == "specific"


def test_icon_out_multi_is_ignored_on_a_single_link_outlet():
    """The _multi step applies only while the pin accepts several links."""
    port = _port(_typed(icon_out="general", icon_out_multi="specific"), PortType.OUTLET)
    port.allow_multiple_links = False
    assert _resolve_pin_icon(port) == "general"


def test_the_icon_shorthand_reaches_both_directions():
    """``icon=`` is the widest step, used when nothing narrower is declared."""
    shared = _typed(icon="one_icon")
    assert _resolve_pin_icon(_port(shared, PortType.INLET)) == "one_icon"
    assert _resolve_pin_icon(_port(shared, PortType.OUTLET)) == "one_icon"


def test_every_icon_field_is_defined_after_construction():
    """Each field resolves to the widest value it inherits, never to None."""
    identity = cast(Any, _typed(icon="wide", icon_out="narrow")).class_identity
    assert identity.icon_in == "wide"
    assert identity.icon_in_multi == "wide"
    assert identity.icon_out == "narrow"
    # _multi inherits its own direction, so icon_out reaches it rather than icon.
    assert identity.icon_out_multi == "narrow"


def test_a_narrower_field_is_not_shadowed_by_the_icon_shorthand():
    """``icon=`` reaches a _multi field only through its own direction.

    Inheriting it directly would let the widest value win on the narrowest
    pin: a type declaring icon= plus icon_out= would lose icon_out on its
    multi-link outlets, which is every DATA outlet.
    """
    both = _typed(icon="wide", icon_out="narrow")
    assert _resolve_pin_icon(_port(both, PortType.OUTLET)) == "narrow"
    # The shorthand still covers the direction that declared nothing.
    assert _resolve_pin_icon(_port(both, PortType.INLET)) == "wide"


def test_a_type_declaring_no_icon_falls_back_to_the_defaults():
    bare = _typed(icon=None, icon_in=None, icon_in_multi=None, icon_out=None, icon_out_multi=None)
    assert _resolve_pin_icon(_port(bare, PortType.INLET)) == "my_location"
    assert _resolve_pin_icon(_port(bare, PortType.OUTLET)) == "circle"
