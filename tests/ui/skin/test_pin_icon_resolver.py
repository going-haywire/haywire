"""The three tiers a pin's glyph resolves through, and the floor beneath them.

A declared icon wins, a skin's resolver answers next, and every role degrades
to ``"fallback"`` — so a one-key map is a complete resolver and no pin that
draws at all can end up without a glyph.
"""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar, cast

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, PortType
from haywire.core.types.enums import ShowWidgetStrategy, StoreStrategy
from haywire.ui.skin.pin_icons import DEFAULT_PIN_ICONS, PinIconResolver

pytestmark = pytest.mark.unit


def _typed(**icons: str | None) -> type:
    """A FLOAT-like type whose class_identity carries *icons*."""
    identity = dataclasses.replace(FLOAT.class_identity, **cast(Any, icons))
    return type("IconType", (FLOAT,), {"class_identity": identity})


def _port(type_cls: type, port_type: PortType, **kwargs) -> DataPort:
    """A port built through the type's own factory, as the app builds one."""
    factory = type_cls.as_inlet if port_type is PortType.INLET else type_cls.as_outlet  # type: ignore[attr-defined]
    spec = dict(factory(f"p_{port_type.value}")["kwargs"])
    for key in ("flow_type", "promoted", "port_type"):
        spec.pop(key, None)
    for field, enum in (("show_widget", ShowWidgetStrategy), ("store_strategy", StoreStrategy)):
        if field in spec and not isinstance(spec[field], enum):
            spec[field] = enum(spec[field])
    spec.update(type_cls=type_cls, flow_type=FlowType.DATA, **kwargs)
    return DataPort(port_type=port_type, **spec)


_BARE = dict(icon=None, icon_in=None, icon_in_multi=None, icon_out=None, icon_out_multi=None)


class TestTierOrder:
    def test_a_declared_icon_beats_the_resolver(self):
        port = _port(_typed(icon_in="from_type"), PortType.INLET)
        assert DEFAULT_PIN_ICONS.resolve(port) == "from_type"

    def test_the_resolver_answers_when_the_type_declares_nothing(self):
        port = _port(_typed(**_BARE), PortType.INLET)
        assert DEFAULT_PIN_ICONS.resolve(port) == "my_location"

    def test_a_per_port_override_beats_both(self):
        port = _port(_typed(icon_in="from_type"), PortType.INLET, icon_in="from_port")
        assert DEFAULT_PIN_ICONS.resolve(port) == "from_port"


class TestFallbackChain:
    def test_a_one_key_map_is_a_complete_resolver(self):
        """The lazy skin author's whole file."""

        class Minimal(PinIconResolver):
            ICONS = {"fallback": "circle"}

        bare = _typed(**_BARE)
        for port_type in (PortType.INLET, PortType.OUTLET):
            assert Minimal().resolve(_port(bare, port_type)) == "circle"

    def test_a_role_falls_back_to_its_flow_type(self):
        """``data`` covers every data role the map does not name."""

        class ByKind(PinIconResolver):
            ICONS = {"data": "square", "fallback": "circle"}

        assert ByKind().resolve(_port(_typed(**_BARE), PortType.INLET)) == "square"

    def test_a_narrower_role_wins_over_its_flow_type(self):
        class Mixed(PinIconResolver):
            ICONS = {"data_in": "inlet_glyph", "data": "square", "fallback": "circle"}

        assert Mixed().resolve(_port(_typed(**_BARE), PortType.INLET)) == "inlet_glyph"
        assert Mixed().resolve(_port(_typed(**_BARE), PortType.OUTLET)) == "square"

    def test_a_map_without_fallback_still_draws(self):
        """A subclass cannot make a pin undrawable by forgetting a key."""

        class NoFallback(PinIconResolver):
            ICONS: ClassVar[dict[str, str]] = {}

        assert NoFallback().resolve(_port(_typed(**_BARE), PortType.INLET)) == "circle"


class TestMultiLink:
    def test_a_multi_link_inlet_takes_the_multi_role(self):
        port = _port(_typed(**_BARE), PortType.INLET, allow_multiple_links=True)
        assert DEFAULT_PIN_ICONS.resolve(port) == "fiber_smart_record"

    def test_a_multi_role_falls_back_to_its_direction(self):
        class OnlyDirection(PinIconResolver):
            ICONS = {"data_in": "inlet_glyph", "fallback": "circle"}

        port = _port(_typed(**_BARE), PortType.INLET, allow_multiple_links=True)
        assert OnlyDirection().resolve(port) == "inlet_glyph"


class TestRoles:
    def test_role_names_are_kind_direction_multi(self):
        bare = _typed(**_BARE)
        assert DEFAULT_PIN_ICONS.role_of(_port(bare, PortType.INLET)) == "data_in"
        multi = _port(bare, PortType.INLET, allow_multiple_links=True)
        assert DEFAULT_PIN_ICONS.role_of(multi) == "data_in_multi"

    def test_a_compound_type_takes_the_compound_kind(self):
        from haybale_core.types import ArrayType

        port = _port(ArrayType[FLOAT], PortType.INLET)
        assert DEFAULT_PIN_ICONS.role_of(port) == "compound_in"
        assert DEFAULT_PIN_ICONS.resolve(port) == "view_day"

    def test_a_pinless_flow_type_resolves_to_no_icon(self):
        """``render_pin`` draws nothing for it, which an icon would contradict."""
        port = _port(_typed(**_BARE), PortType.INLET)
        port.flow_type = FlowType.NONE
        assert DEFAULT_PIN_ICONS.resolve(port) is None


class TestSkinWiring:
    """A skin's resolver is what its pins actually draw with."""

    def test_every_skin_starts_on_the_framework_vocabulary(self):
        from haywire.ui.skin.base import BaseSkin

        assert BaseSkin.pin_icons is DEFAULT_PIN_ICONS

    def test_a_skin_override_reaches_the_renderer(self):
        from haywire.ui.skin.pin_render import _resolve_pin_icon

        class Minimal(PinIconResolver):
            ICONS = {"fallback": "hexagon"}

        port = _port(_typed(**_BARE), PortType.INLET)
        assert _resolve_pin_icon(port) == "my_location"
        assert _resolve_pin_icon(port, Minimal()) == "hexagon"

    def test_a_declared_icon_survives_a_skin_override(self):
        """Tier 3 is a framework guarantee, not a skin's to revoke."""
        from haywire.ui.skin.pin_render import _resolve_pin_icon

        class Minimal(PinIconResolver):
            ICONS = {"fallback": "hexagon"}

        port = _port(_typed(icon_in="from_type"), PortType.INLET)
        assert _resolve_pin_icon(port, Minimal()) == "from_type"
