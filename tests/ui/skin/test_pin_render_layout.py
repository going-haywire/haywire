"""render_pin places a pin's CSS side and direction vector from ONE source.

The load-bearing property: a pin's `{side}: -Npx` offset and its
`data-pin-dir-x/y` must always agree on an axis. Before LayoutDirection they
were computed independently (side from the caller, vector from
`pin.is_inlet()`), which is exactly the kind of mismatch that renders pins on
the right edge with edges curving the wrong way and reports nothing.
"""

from __future__ import annotations

import pytest

from haywire.barn.builtin.types import FLOAT
from haywire.core.types import DataPort, FlowType, LayoutDirection, PortType
from haywire.ui.skin.pin_render import render_pin

pytestmark = pytest.mark.unit

L2R = LayoutDirection.LEFT_TO_RIGHT
R2L = LayoutDirection.RIGHT_TO_LEFT
T2B = LayoutDirection.TOP_TO_BOTTOM
B2T = LayoutDirection.BOTTOM_TO_TOP

_PIN_GUTTER = 20
_CARD_PADDING = 16
_PIN_PROTRUSION = 0
# offset = card_padding + gutter//2 + protrusion
_OFFSET_PX = _CARD_PADDING + _PIN_GUTTER // 2 + _PIN_PROTRUSION


def _make_port(port_type: PortType) -> DataPort:
    return DataPort(
        registry_id="float",
        registry_key="haybale_core:type:float",
        label="F",
        id=f"p_{port_type.value}",
        type_cls=FLOAT,
        port_type=port_type,
        flow_type=FlowType.DATA,
    )


@pytest.fixture
def simple_ports(nicegui_slot_context) -> tuple[DataPort, DataPort]:
    """(inlet, outlet) — rendering needs a live NiceGUI slot."""
    return _make_port(PortType.INLET), _make_port(PortType.OUTLET)


def _render(port, layout):
    return render_pin(
        port,
        "node-1",
        layout=layout,
        pin_gutter=_PIN_GUTTER,
        card_padding=_CARD_PADDING,
        pin_protrusion=_PIN_PROTRUSION,
    )


def _render_default(port):
    """Render without passing a layout at all — the legacy call shape."""
    return render_pin(
        port,
        "node-1",
        pin_gutter=_PIN_GUTTER,
        card_padding=_CARD_PADDING,
        pin_protrusion=_PIN_PROTRUSION,
    )


def _offset_side(element) -> str:
    """The single CSS side this pin is offset on, e.g. 'left'."""
    sides = [s for s in ("left", "right", "top", "bottom") if s in element._style]
    assert len(sides) == 1, f"expected exactly one offset side, got {sides}"
    return sides[0]


def _vector(element) -> tuple[float, float]:
    return (
        float(element._props["data-pin-dir-x"]),
        float(element._props["data-pin-dir-y"]),
    )


@pytest.mark.parametrize(
    ("layout", "inlet_side", "outlet_side"),
    [
        (L2R, "left", "right"),
        (R2L, "right", "left"),
        (T2B, "top", "bottom"),
        (B2T, "bottom", "top"),
    ],
)
def test_pin_offsets_on_the_layouts_side(simple_ports, layout, inlet_side, outlet_side):
    inlet, outlet = simple_ports
    inlet_el, outlet_el = _render(inlet, layout), _render(outlet, layout)
    assert _offset_side(inlet_el) == inlet_side
    assert _offset_side(outlet_el) == outlet_side
    assert inlet_el._style[inlet_side] == f"-{_OFFSET_PX}px"
    assert outlet_el._style[outlet_side] == f"-{_OFFSET_PX}px"


@pytest.mark.parametrize("layout", list(LayoutDirection))
def test_side_and_vector_never_disagree(simple_ports, layout):
    """The invariant this whole design exists to protect."""
    horizontal_sides = {"left", "right"}
    for port in simple_ports:
        element = _render(port, layout)
        side = _offset_side(element)
        dir_x, dir_y = _vector(element)

        assert (side in horizontal_sides) == (dir_x != 0)
        assert (side in ("left", "top")) == ((dir_x + dir_y) < 0)


@pytest.mark.parametrize("layout", list(LayoutDirection))
def test_edge_ends_carry_opposed_vectors(simple_ports, layout):
    inlet, outlet = simple_ports
    ix, iy = _vector(_render(inlet, layout))
    ox, oy = _vector(_render(outlet, layout))
    assert (ix, iy) == (-ox, -oy)


def test_default_layout_reproduces_pre_feature_output(simple_ports):
    """A skin that passes no layout must render exactly what it used to."""
    inlet, outlet = simple_ports
    explicit = _render(inlet, L2R)
    implicit = _render_default(inlet)
    assert implicit._style == explicit._style
    assert _vector(implicit) == (-1.0, 0.0)
    assert _vector(_render_default(outlet)) == (1.0, 0.0)


@pytest.mark.parametrize(
    ("layout", "expected"),
    [(L2R, None), (R2L, "scaleX(-1)"), (T2B, "rotate(90deg)"), (B2T, "rotate(-90deg)")],
)
def test_non_default_layouts_reaim_the_glyph(simple_ports, layout, expected):
    """L/R-pointing icons are re-aimed by a transform, not by new icon constants.

    EVERY non-L2R direction needs one, not just the vertical pair: R2L puts
    inlets on the right edge, so an un-mirrored glyph points out of the card,
    and B2T reverses T2B's flow. Symmetric DATA icons hide a missing transform;
    CALLBACK's directional arrows are where it shows.

    The transform must land on the ``--hw-pin-rotate`` custom property, NOT on
    ``transform``: canvas.vue scales pins on hover/drag/invalid by writing the
    whole ``transform`` property, which would replace a raw transform and snap
    the pin back to its unaimed orientation. Those rules compose the variable.
    """
    for port in simple_ports:
        style = _render(port, layout)._style
        assert style.get("--hw-pin-rotate") == expected
        assert "transform" not in style, "the transform must not be written as `transform`"


@pytest.mark.parametrize("layout", list(LayoutDirection))
def test_layout_is_advertised_on_the_element(simple_ports, layout):
    for port in simple_ports:
        assert _render(port, layout)._props["data-hw-layout"] == layout.value
