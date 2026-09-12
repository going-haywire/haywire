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
from haywire.core.types.enums import ShowWidgetStrategy, StoreStrategy
from haywire.ui.skin.pin_render import _resolve_pin_icon

pytestmark = pytest.mark.unit


def _typed(**icons: str | None) -> type:
    """A FLOAT-like type whose class_identity carries *icons*."""
    # replace() is typed per-field, which a kwargs bag cannot satisfy.
    identity = dataclasses.replace(FLOAT.class_identity, **cast(Any, icons))
    return type("IconType", (FLOAT,), {"class_identity": identity})


def _port(type_cls: type, port_type: PortType, **kwargs) -> DataPort:
    """A port built the way the app builds one, through the type's own factory.

    ``as_inlet``/``as_outlet`` merge the type's identity into the spec, which is
    where a port gets its icons; constructing ``DataPort`` directly leaves all
    four unset and the pin draws the framework default.
    """
    factory = type_cls.as_inlet if port_type is PortType.INLET else type_cls.as_outlet  # type: ignore[attr-defined]
    spec = dict(factory(f"p_{port_type.value}")["kwargs"])
    spec.pop("flow_type", None)
    spec.pop("promoted", None)
    spec.pop("port_type", None)
    for field, enum in (("show_widget", ShowWidgetStrategy), ("store_strategy", StoreStrategy)):
        if field in spec and not isinstance(spec[field], enum):
            spec[field] = enum(spec[field])
    spec.update(type_cls=type_cls, flow_type=FlowType.DATA, **kwargs)
    return DataPort(port_type=port_type, **spec)


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


def test_a_per_port_override_reaches_the_glyph():
    """``as_inlet(icon_in=...)`` overrides the type, like ``color=`` already does."""
    port = _port(_typed(icon_in="from_type"), PortType.INLET, icon_in="from_port")
    assert _resolve_pin_icon(port) == "from_port"


def test_a_parameterized_type_keeps_its_own_glyph():
    """``ADD[STRING]`` is an ADD pin that carries STRING, and must look like one.

    Its ``stored_type`` is ``STRING`` — that is the seam that lets the adapter
    layer treat it as an ordinary STRING sink — so resolving the icon from the
    stored type would draw STRING's default and lose the affordance that tells
    the user the pin grows.
    """
    from haywire.barn.builtin.types import ADD, STRING

    assert ADD[STRING].create_field().get_stored_type() is STRING
    assert _resolve_pin_icon(_port(ADD[STRING], PortType.INLET)) == "add_circle_outline"
    assert _resolve_pin_icon(_port(ADD[STRING], PortType.OUTLET)) == "add_circle"


def test_a_wrapper_type_still_renders_as_its_element():
    """``OPTIONAL[INT]`` declares no icon of its own, so it draws INT's pin (ADR 0033)."""
    from haywire.barn.builtin.types import INT, OPTIONAL

    assert _resolve_pin_icon(_port(OPTIONAL[INT], PortType.INLET)) == "my_location"
    assert _resolve_pin_icon(_port(OPTIONAL[INT], PortType.OUTLET)) == "circle"
