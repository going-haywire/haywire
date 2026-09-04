"""A NodeDetail rank change must repaint the edges of pins it moved.

NodeDetail is a CSS filter: the rank is one attribute
(``data-node-props-detail``, stamped by ``UINode._apply_detail_attr``) and
canvas.vue's ``display: none`` rules do the rest. No card rebuild, no sync
event — so nothing carries an edge repaint along with it, and canvas.vue's own
attribute observer is the only thing that notices.

It has to notice, because hiding elements moves the ones that stay: at PINS
every unlinked pin leaves the layout, so a linked pin below one slides up while
its edge stays behind until some incidental trigger (a hover, a drag) refreshes
it.

The fixture puts ``int_inlet`` (the only wired one) below three unlinked pins,
so the rank flip is guaranteed to move it. Each test asserts that movement
before asserting anything about the edge — a pin that did not move would make
the edge check vacuous.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-detail"

pytestmark = pytest.mark.ui


def _pin(page: Page, pin_id: str) -> dict:
    """Centre of one pin in the SVG space edge paths are authored in.

    Mirrors ``_getPinPosition`` → ``_transformScreenToSVG`` exactly, so the
    result is directly comparable to a path's coordinates; raw
    ``getBoundingClientRect`` values are not.

    The zoom comes from ``_zoomPanControls``, the same source canvas.vue reads.
    Trap: deriving it from a computed ``transform`` reads the wrong element —
    the transform lives on ``.zoom-pan-content``, not on the canvas — and the
    mismatch is invisible at zoom 1, then shows up as coordinates off by a
    constant RATIO (not an offset) anywhere else.
    """
    return page.evaluate(
        """(pinId) => {
            const pin = [...document.querySelectorAll('.connection-pin')]
                .find(e => e.dataset.pinId === pinId && e.dataset.pinDir === 'inlet');
            if (!pin) throw new Error('pin not found: ' + pinId);
            const r = pin.getBoundingClientRect();
            const s = document.querySelector('#connection-svg').getBoundingClientRect();
            const zp = document.querySelector('.zoom-pan-container');
            const zoom = zp && zp._zoomPanControls ? zp._zoomPanControls.getZoom() : 1;
            return {
                x: (r.left + r.width / 2 - s.left) / zoom,
                y: (r.top + r.height / 2 - s.top) / zoom,
                visible: r.width > 0 && r.height > 0,
            };
        }""",
        pin_id,
    )


def _edge_end(page: Page) -> dict:
    """The inlet end of the visible edge path, in the same SVG space.

    Parsed off the `d` attribute's final coordinate pair rather than read with
    ``getPointAtLength``. Trap: the canvas authors `d` in the space
    ``_getPinPosition`` produces, which is not the path's own user space, so the
    SVG geometry APIs answer in different units — silently, and by a wide
    margin. ``test_graph_layout_direction.py`` parses `M x y` for the same
    reason.
    """
    return page.evaluate(
        """() => {
            const path = document.querySelector(
                "#connection-svg path[data-edge-id]:not([id$='_hitarea'])");
            if (!path) throw new Error('no edge path');
            const d = path.getAttribute('d');
            const m = d.match(/([\\d.-]+)\\s+([\\d.-]+)\\s*$/);
            if (!m) throw new Error('unparsable path: ' + d);
            return { x: parseFloat(m[1]), y: parseFloat(m[2]) };
        }"""
    )


def _visible_inlet_count(page: Page) -> int:
    return page.evaluate(
        """() => [...document.querySelectorAll('.connection-pin')]
            .filter(p => p.dataset.pinDir === 'inlet'
                      && p.getBoundingClientRect().height > 0).length"""
    )


def _open(page: Page) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector("path[data-edge-id]")
    page.wait_for_timeout(1200)  # let the graph sync + center


def _switch(page: Page, testid: str) -> None:
    page.click(f'[data-testid="{testid}"]')
    # A rank flip is an attribute write plus one rAF-deferred repaint. No hover,
    # no drag, no other incidental trigger — that is the point of the test.
    page.wait_for_timeout(900)


def test_detail_pins_hides_the_unlinked_inlets(page: Page, harness) -> None:
    """The fixture's premise: PINS actually removes pins from the layout."""
    _open(page)
    before = _visible_inlet_count(page)

    _switch(page, "set-pins")

    after = _visible_inlet_count(page)
    assert after < before, (
        f"PINS should hide the unlinked inlets ({before} visible before, {after} after) — "
        "without that the edge assertions below prove nothing"
    )
    assert _pin(page, "int_inlet")["visible"], "the LINKED pin must survive PINS"


def test_edge_end_follows_the_pin_that_detail_moved(page: Page, harness) -> None:
    _open(page)
    before = _pin(page, "int_inlet")

    _switch(page, "set-pins")

    after = _pin(page, "int_inlet")
    assert abs(after["y"] - before["y"]) > 8, (
        f"the linked pin should have moved when the unlinked ones above it were "
        f"hidden (y {before['y']:.1f} -> {after['y']:.1f}); it did not, so this "
        "test would pass whether or not the edge tracked it"
    )

    end = _edge_end(page)
    assert abs(end["y"] - after["y"]) < 12, (
        f"edge end {end['y']:.1f} should track the pin's new centre {after['y']:.1f} "
        f"(it was at {before['y']:.1f} before the rank change) — a stale edge means "
        "the detail attribute change never reached _updateEdgesForNode"
    )
    assert abs(end["x"] - after["x"]) < 12


def test_edge_end_follows_the_pin_back_at_full(page: Page, harness) -> None:
    """And back again — the return trip re-shows the pins and moves it down."""
    _open(page)
    _switch(page, "set-pins")
    lifted = _pin(page, "int_inlet")

    # Checked on the way out as well, and not only for symmetry: the round trip
    # puts the pin back exactly where a STALE edge is already drawn, so without
    # this the test would pass against the very defect it is here to catch.
    assert abs(_edge_end(page)["y"] - lifted["y"]) < 12, "edge must track on the way down"

    _switch(page, "set-full")

    restored = _pin(page, "int_inlet")
    assert abs(restored["y"] - lifted["y"]) > 8, "returning to FULL must move the pin back"

    end = _edge_end(page)
    assert abs(end["y"] - restored["y"]) < 12, (
        f"edge end {end['y']:.1f} should track the restored pin {restored['y']:.1f}"
    )
