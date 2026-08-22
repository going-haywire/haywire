"""LayoutDirection changes must re-aim AND repaint existing edges.

Two defects this file locks down, both invisible to the Python tiers because
they live entirely in canvas.vue's edge cache:

1. ``_createEdge`` captured each pin's direction vector once and ``_updateEdge``
   refreshed position and colour but not the vector. That was safe only while
   every node was left-to-right; after a switch to r2l an outlet's edge left the
   pin pointing back into its own node.
2. ``_syncNodeRedraw`` re-attached the hover observer but never redrew the
   node's edges. The redraw replaces the pin elements, so edges kept describing
   DOM that no longer existed until some incidental trigger — a hover, a drag —
   refreshed them.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-layout"

pytestmark = pytest.mark.ui


def _pin(page: Page, node_fragment: str, pin_id: str) -> dict:
    """Direction vector + centre of one pin, read from the live DOM.

    ``x``/``y`` are in the SVG space the edge path is authored in (screen coords
    divided by zoom, relative to the svg rect) — the same transform
    ``_getPinPosition`` applies — so they are directly comparable to the `M x y`
    of a path `d` attribute. Raw ``getBoundingClientRect`` values are NOT.
    """
    return page.evaluate(
        """([frag, pinId]) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.id.includes(frag) && e.dataset.pinId === pinId);
            if (!pin) throw new Error('pin not found: ' + frag + '/' + pinId);
            const r = pin.getBoundingClientRect();
            const svg = document.querySelector('.connection-svg');
            const s = svg.getBoundingClientRect();
            const canvas = document.querySelector('.graph-canvas');
            // Mirror _transformScreenToSVG: undo the pan/zoom transform.
            const t = canvas ? getComputedStyle(canvas).transform : 'none';
            const zoom = t && t !== 'none' ? new DOMMatrix(t).a : 1;
            return {
                dirX: parseFloat(pin.dataset.pinDirX),
                dirY: parseFloat(pin.dataset.pinDirY),
                layout: pin.dataset.hwLayout,
                x: (r.left + r.width / 2 - s.left) / zoom,
                y: (r.top + r.height / 2 - s.top) / zoom,
            };
        }""",
        [node_fragment, pin_id],
    )


def _edge_first_control_point(page: Page) -> dict:
    """Parse `M x y C c1x c1y, ...` off the single edge path."""
    return page.evaluate(
        """() => {
            const path = document.querySelector('path[data-edge-id]');
            if (!path) throw new Error('no edge path');
            const d = path.getAttribute('d');
            const m = d.match(/M ([\\d.-]+) ([\\d.-]+) C ([\\d.-]+) ([\\d.-]+)/);
            if (!m) throw new Error('unparsable path: ' + d);
            return {
                startX: parseFloat(m[1]), startY: parseFloat(m[2]),
                c1x: parseFloat(m[3]), c1y: parseFloat(m[4]),
            };
        }"""
    )


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector("path[data-edge-id]")
    page.wait_for_timeout(1200)  # let the graph sync + center


def _switch(page: Page, testid: str) -> None:
    page.click(f'[data-testid="{testid}"]')
    # Redraw + the scheduled edge updates settle within ~300ms; no hover, no
    # drag, no other incidental trigger — that is the point of the test.
    page.wait_for_timeout(900)


def test_outlet_vector_flips_with_the_graph_direction(page: Page, harness) -> None:
    _open(page)
    before = _pin(page, "TestBeginPlayNode", "exec")
    assert before["dirX"] == 1, "outlet should point +X under the default l2r"

    _switch(page, "set-r2l")

    after = _pin(page, "TestBeginPlayNode", "exec")
    assert after["layout"] == "r2l"
    assert after["dirX"] == -1, "outlet must point -X under r2l"


def test_edge_control_point_follows_the_flipped_outlet(page: Page, harness) -> None:
    """The regression: a cached vector leaves the curve aiming the old way."""
    _open(page)
    start = _edge_first_control_point(page)
    assert start["c1x"] > start["startX"], "l2r: first control point extends +X"

    _switch(page, "set-r2l")

    flipped = _edge_first_control_point(page)
    assert flipped["c1x"] < flipped["startX"], (
        "r2l: the outlet's control point must extend -X — a stale cached vector "
        "leaves the edge doubling back into its own node"
    )


def test_edge_endpoint_tracks_the_moved_pin_without_a_hover(page: Page, harness) -> None:
    """Wrinkle 2: the redraw sync must repaint edges by itself."""
    _open(page)
    _switch(page, "set-r2l")

    pin = _pin(page, "TestBeginPlayNode", "exec")
    path = _edge_first_control_point(page)
    # The edge must start at the pin's CURRENT screen position. Without the
    # redraw-triggered update it still starts where the pin used to be, which
    # after an l2r->r2l flip is the far side of the card.
    assert abs(path["startX"] - pin["x"]) < 12, (
        f"edge start {path['startX']:.1f} should track pin centre {pin['x']:.1f}"
    )
    assert abs(path["startY"] - pin["y"]) < 12


def test_vertical_switch_reaims_both_ends(page: Page, harness) -> None:
    _open(page)
    _switch(page, "set-t2b")

    outlet = _pin(page, "TestBeginPlayNode", "exec")
    inlet = _pin(page, "TestPrintNode", "exec")
    assert outlet["layout"] == "t2b"
    assert (outlet["dirX"], outlet["dirY"]) == (0, 1), "t2b outlet points +Y"
    assert (inlet["dirX"], inlet["dirY"]) == (0, -1), "t2b inlet points -Y"

    path = _edge_first_control_point(page)
    assert abs(path["c1x"] - path["startX"]) < 1e-6, "vertical: control point must not extend on X"
    assert path["c1y"] > path["startY"], "t2b: outlet control point extends +Y"


def _card_box(page: Page, node_fragment: str) -> dict:
    return page.evaluate(
        """(frag) => {
            const card = [...document.querySelectorAll('.node-card')]
                .find(c => c.closest('[data-node-id]')?.id.includes(frag));
            if (!card) throw new Error('card not found: ' + frag);
            const r = card.getBoundingClientRect();
            return { top: r.top, bottom: r.bottom, left: r.left, right: r.right };
        }""",
        node_fragment,
    )


def _pin_screen_box(page: Page, node_fragment: str, pin_id: str) -> dict:
    return page.evaluate(
        """([frag, pinId]) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.id.includes(frag) && e.dataset.pinId === pinId);
            if (!pin) throw new Error('pin not found: ' + frag + '/' + pinId);
            const r = pin.getBoundingClientRect();
            return { top: r.top, bottom: r.bottom, cy: r.top + r.height / 2 };
        }""",
        [node_fragment, pin_id],
    )


@pytest.mark.parametrize(
    ("testid", "outlet_edge"),
    [("set-t2b", "bottom"), ("set-b2t", "top")],
)
def test_vertical_pins_sit_on_the_card_edge_not_inside(page: Page, harness, testid, outlet_edge) -> None:
    """Wrinkle 3: B2T sided its strips the wrong way and pins landed inside."""
    _open(page)
    _switch(page, testid)

    card = _card_box(page, "TestBeginPlayNode")
    pin = _pin_screen_box(page, "TestBeginPlayNode", "exec")

    if outlet_edge == "bottom":
        assert pin["cy"] > card["bottom"] - 4, (
            f"t2b outlet centre {pin['cy']:.1f} must sit at/below the card bottom "
            f"{card['bottom']:.1f}, not inside the card"
        )
    else:
        assert pin["cy"] < card["top"] + 4, (
            f"b2t outlet centre {pin['cy']:.1f} must sit at/above the card top "
            f"{card['top']:.1f}, not inside the card"
        )


@pytest.mark.parametrize("testid", ["set-t2b", "set-b2t"])
def test_root_ghost_pins_leave_the_card_body(page: Page, harness, testid) -> None:
    """Wrinkle 1: ghosts inline in a mid-card header row offset inward."""
    _open(page)
    _switch(page, testid)

    card = _card_box(page, "TestBeginPlayNode")
    for pin_id in ("root_in", "root_out"):
        ghost = _pin_screen_box(page, "TestBeginPlayNode", pin_id)
        on_top = ghost["cy"] < card["top"] + 4
        on_bottom = ghost["cy"] > card["bottom"] - 4
        assert on_top or on_bottom, (
            f"{pin_id} centre {ghost['cy']:.1f} is inside the card "
            f"({card['top']:.1f}..{card['bottom']:.1f}) — it must sit on an edge"
        )


def _title_box(page: Page, node_fragment: str) -> dict:
    return page.evaluate(
        """(frag) => {
            const card = [...document.querySelectorAll('.node-card')]
                .find(c => c.closest('[data-node-id]')?.id.includes(frag));
            const title = card.querySelector('.text-h6');
            if (!title) throw new Error('title not found: ' + frag);
            const r = title.getBoundingClientRect();
            return { top: r.top, bottom: r.bottom };
        }""",
        node_fragment,
    )


@pytest.mark.parametrize("testid", ["set-t2b", "set-b2t"])
def test_vertical_title_gap_matches_horizontal(page: Page, harness, testid) -> None:
    """A pin strip must reserve NO vertical space above the title.

    Its pins are pushed outside the border by `position: relative`, which leaves
    them in flow, so an in-flow strip reserves a whole pin row inside the card.
    Collapsing that with a negative margin is not enough either — the strip
    stays a flex item, so the card's row-gap still allocates a slot beside it.
    Only taking it out of flow entirely gets the title back against the border.

    Asserted against the horizontal layout rather than a magic number: the
    budget is "whatever the card's own padding is", which is the real contract.
    """
    _open(page)

    _switch(page, "set-l2r")
    card = _card_box(page, "TestBeginPlayNode")
    baseline = _title_box(page, "TestBeginPlayNode")["top"] - card["top"]

    _switch(page, testid)
    card = _card_box(page, "TestBeginPlayNode")
    gap = _title_box(page, "TestBeginPlayNode")["top"] - card["top"]

    assert abs(gap - baseline) < 2, (
        f"{testid}: title sits {gap:.1f}px below the card top vs {baseline:.1f}px "
        f"horizontally — the pin strip is still taking up layout space"
    )


def test_vertical_pin_keeps_its_rotation_while_hovered(page: Page, harness) -> None:
    """Wrinkle 2: canvas.vue scales pins by writing the whole transform."""
    _open(page)
    _switch(page, "set-t2b")

    def rotation_of() -> float:
        return page.evaluate(
            """() => {
                const pin = [...document.querySelectorAll('.connection-pin')]
                    .find(e => e.id.includes('TestBeginPlayNode') && e.dataset.pinId === 'exec');
                const m = new DOMMatrix(getComputedStyle(pin).transform);
                return Math.round(Math.atan2(m.b, m.a) * 180 / Math.PI);
            }"""
        )

    assert abs(rotation_of()) == 90, "vertical pin should be rotated at rest"

    box = _pin_screen_box(page, "TestBeginPlayNode", "exec")
    centre = page.evaluate(
        """() => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.id.includes('TestBeginPlayNode') && e.dataset.pinId === 'exec');
            const r = pin.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        }"""
    )
    assert box  # keep the helper's assertion path exercised
    page.mouse.move(centre["x"], centre["y"])
    page.wait_for_timeout(300)

    assert abs(rotation_of()) == 90, (
        "hovering must not un-rotate the pin — the :hover scale has to compose "
        "with --hw-pin-rotate rather than replace the transform"
    )


def test_switching_back_restores_the_original_orientation(page: Page, harness) -> None:
    _open(page)
    original = _edge_first_control_point(page)

    _switch(page, "set-r2l")
    _switch(page, "set-l2r")

    restored = _edge_first_control_point(page)
    assert _pin(page, "TestBeginPlayNode", "exec")["dirX"] == 1
    assert restored["c1x"] > restored["startX"]
    # Same geometry as before the round trip — the flip is not cumulative.
    assert abs(restored["startX"] - original["startX"]) < 12
