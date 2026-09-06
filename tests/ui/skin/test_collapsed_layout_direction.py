"""A folded card observes its LayoutDirection, and reserves room for its pins.

Two invariants, both previously unpinned and both silent when broken.

**Folding must not re-side a pin.** A folded T2B node keeps its inlets on the
card's TOP edge. An earlier `_fold_layout` mapped both vertical directions onto
a horizontal one, so folding a T2B node silently moved every pin to the sides
and re-routed its wires — legible only by eye, on a graph the user had already
laid out vertically.

**A folded card must reserve the axis its pins stack on.** Both pin containers
are absolutely positioned and so contribute nothing to flow size; without an
explicit reservation a node with several linked ports spills its pins past the
card border. That is not cosmetic — the edge layer anchors on each pin's
``getBoundingClientRect()``, so a spilled pin's wires terminate outside the
card too.

The whole suite renders real cards through ``SkinFactory`` and reads the
emitted ``data-hw-layout`` / ``side`` styling, so it breaks on a skin that
stops observing the direction, not on a restyle.
"""

from __future__ import annotations

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.core.types import LayoutDirection
from haywire.ui.skin.factory import SkinFactory

pytestmark = [pytest.mark.integration]

_PORT_COUNT = 4


def _node(graph):
    """The node under test, with real edges on both its inlets and outlets.

    The edges are the whole fixture. ``get_folded_ports()`` returns only LINKED
    ports, so an unwired node folds to zero pins and every assertion here
    passes vacuously — which is exactly how the first draft of this file
    "passed" against a skin that re-sided everything.
    """
    from haybale_testing.nodes.testbed.test_performance import PerformanceTester

    key = PerformanceTester.class_identity.registry_key
    wrapper = graph.create_node_wrapper(key, position=(0, 0))
    peer = graph.create_node_wrapper(key, position=(400, 0))
    assert wrapper is not None
    assert peer is not None
    for w in (wrapper, peer):
        w.node.ports["port_count"].set_value(_PORT_COUNT)
    graph.force_validation()

    # Wire peer -> wrapper (fills wrapper's inlets) and wrapper -> peer (its
    # outlets), so the folded card carries pins in BOTH directions.
    inlets = [p for p in wrapper.node.get_visible_ports() if p.is_inlet()]
    outlets = [p for p in wrapper.node.get_visible_ports() if p.is_outlet()]
    peer_inlets = [p for p in peer.node.get_visible_ports() if p.is_inlet()]
    peer_outlets = [p for p in peer.node.get_visible_ports() if p.is_outlet()]

    # strict=False deliberately: a node's inlet and outlet counts differ, and
    # pairing only as far as the shorter list is the intent — every edge made
    # is a real one, and the fixture asserts below that both directions landed.
    for inlet, peer_outlet in zip(inlets, peer_outlets, strict=False):
        graph.create_edge_wrapper(peer.node_id, peer_outlet.id, wrapper.node_id, inlet.id)
    for outlet, peer_inlet in zip(outlets, peer_inlets, strict=False):
        graph.create_edge_wrapper(wrapper.node_id, outlet.id, peer.node_id, peer_inlet.id)
    graph.force_validation()

    # Both guards matter: a fold with pins in only ONE direction still exercises
    # a side assertion, but never the opposite edge — which is half the point.
    folded = wrapper.node.get_folded_ports()
    vacuous = (
        "fixture wired no edges — a folded card would draw no pins and every "
        f"assertion in this file would pass vacuously (folded={folded})"
    )
    assert any(p.is_inlet() for p in folded), vacuous
    assert any(not p.is_inlet() for p in folded), vacuous
    return wrapper


@pytest.fixture
def ctx(library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = BaseGraph(filestem="collapsed layout", validation_scheduler=SyncScheduler())
    wrapper = _node(graph)
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    assert skin_key, "no default skin registered"
    return skin_factory, graph, wrapper, skin_key


def _render_folded(ctx, direction: LayoutDirection) -> ui.element:
    skin_factory, _graph, wrapper, skin_key = ctx
    wrapper.node.props.layout_direction = direction.value
    wrapper.node.props.collapsed = True
    container = ui.element("div")
    with container:
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrapper)
    return container


def _pins(container: ui.element) -> list:
    """Every real pin on the card — the ghosts carry no `data-pin-data-type`."""
    return [
        el
        for el in container.descendants()
        if "data-pin-id" in el._props and "data-pin-data-type" in el._props
    ]


@pytest.mark.parametrize(
    ("direction", "inlet_side", "outlet_side"),
    [
        (LayoutDirection.LEFT_TO_RIGHT, "left", "right"),
        (LayoutDirection.RIGHT_TO_LEFT, "right", "left"),
        (LayoutDirection.TOP_TO_BOTTOM, "top", "bottom"),
        (LayoutDirection.BOTTOM_TO_TOP, "bottom", "top"),
    ],
)
class TestFoldingPreservesLayoutDirection:
    def test_folded_pins_sit_on_the_direction_s_own_edges(self, ctx, direction, inlet_side, outlet_side):
        """The regression this file exists for: a folded vertical node must NOT
        be re-sided onto the horizontal axis."""
        pins = _pins(_render_folded(ctx, direction))
        assert pins, "a folded card drew no pins at all"

        # The seating edge is a STYLE KEY (`render_pin` writes `{side}: -Npx`),
        # so assert on the key set. A substring check over the whole style
        # string passes on the very regression this test exists to catch —
        # "top" also occurs in `top: 50%` on the wrong-axis path.
        opposite = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}
        for pin in pins:
            expected = inlet_side if pin._props["data-pin-dir"] == "inlet" else outlet_side
            assert expected in pin._style, (
                f"{direction.value}: a {pin._props['data-pin-dir']} pin is not seated "
                f"on the {expected} edge — folding re-sided it. Style: {pin._style}"
            )
            assert opposite[expected] not in pin._style, (
                f"{direction.value}: a {pin._props['data-pin-dir']} pin is seated on BOTH "
                f"{expected} and {opposite[expected]}. Style: {pin._style}"
            )
            # The perpendicular axis must carry no seating offset at all: that
            # is precisely what re-siding a vertical fold onto the horizontal
            # axis produces.
            for cross in {"left", "right"} if expected in ("top", "bottom") else {"top", "bottom"}:
                assert cross not in pin._style, (
                    f"{direction.value}: a {expected}-sided pin also carries a `{cross}` "
                    f"offset — it was seated on the wrong axis. Style: {pin._style}"
                )

    def test_folded_pins_advertise_the_node_s_layout(self, ctx, direction, inlet_side, outlet_side):
        """`data-hw-layout` is what the edge layer reads; a fold that rewrites it
        re-routes every wire on the node."""
        for pin in _pins(_render_folded(ctx, direction)):
            assert pin._props["data-hw-layout"] == direction.value


class TestFoldedCardReservesPinSpace:
    """The card grows rather than letting the stack escape it."""

    @pytest.mark.parametrize("direction", [LayoutDirection.LEFT_TO_RIGHT, LayoutDirection.RIGHT_TO_LEFT])
    def test_horizontal_fold_reserves_height_for_the_taller_column(self, ctx, direction):
        container = _render_folded(ctx, direction)
        rows = [el for el in container.descendants() if "min-height" in el._style]
        assert rows, "no element reserves height — the pin columns will spill"

        pins = _pins(container)
        inlets = [p for p in pins if p._props["data-pin-dir"] == "inlet"]
        outlets = [p for p in pins if p._props["data-pin-dir"] == "outlet"]
        tallest = max(len(inlets), len(outlets))
        reserved = max(int(el._style["min-height"].removesuffix("px")) for el in rows)
        assert reserved >= tallest * 20, (
            f"reserved {reserved}px for {tallest} stacked pins — the taller column spills"
        )

    @pytest.mark.parametrize("direction", [LayoutDirection.TOP_TO_BOTTOM, LayoutDirection.BOTTOM_TO_TOP])
    def test_vertical_fold_reserves_width_for_the_widest_strip(self, ctx, direction):
        """Vertically the pins lay out in a ROW, so it is WIDTH that must grow."""
        container = _render_folded(ctx, direction)
        cards = [el for el in container.descendants() if "min-width" in el._style]
        assert cards, "no element reserves width — the pin strips will spill sideways"

        pins = _pins(container)
        inlets = [p for p in pins if p._props["data-pin-dir"] == "inlet"]
        outlets = [p for p in pins if p._props["data-pin-dir"] == "outlet"]
        widest = max(len(inlets), len(outlets))
        reserved = max(int(el._style["min-width"].removesuffix("px")) for el in cards)
        assert reserved >= widest * 20, (
            f"reserved {reserved}px for {widest} pins in a row — the widest strip spills"
        )
