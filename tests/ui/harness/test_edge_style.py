"""A styled edge in the browser: its own width, heads, colour and dash, set as inline vars and strokes."""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.test_edge_appearance import _computed, _distance, _end_point, _pin

_PATH = "/graph-edge-appearance"
_STYLED = 'path.hw-edge[data-edge-id*="[note_out]->"]'
_STYLED_HIT = 'path.hw-edge-hit[data-edge-id*="[note_out]->"]'
_DATA = 'path.hw-edge[data-edge-id*="[result]->"]'
_CANVAS = '.graph-canvas[data-testid="edge-appearance-canvas"]'

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_STYLED)
    wait_for_canvas_settled(page)


def _click_until(page: Page, testid: str, selector: str, prop: str, predicate: str) -> str:
    """Click, then wait until *predicate*, a JS expression of `v`, holds for *selector*'s computed *prop*."""
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_function(
        """([sel, prop, src]) => {
            const el = document.querySelector(sel);
            return !!el && (new Function('v', 'return ' + src))(getComputedStyle(el)[prop]);
        }""",
        arg=[selector, prop, predicate],
        timeout=5000,
    )
    return _computed(page, selector, prop)


def _wait_for_layout(page: Page) -> None:
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def test_the_bag_defaults_draw_an_end_head_and_no_start_head(page: Page, harness) -> None:
    _open(page, harness)
    assert "-arrow" in _computed(page, _STYLED, "markerEnd")
    assert _computed(page, _STYLED, "markerStart") == "none"


def test_a_styled_width_is_the_edges_own_and_widens_its_hit_area(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-width-6", _STYLED, "strokeWidth", "v === '6px'")
    assert _computed(page, _STYLED_HIT, "strokeWidth") == "14px"
    assert _computed(page, _DATA, "strokeWidth") == "2px", "a computed edge keeps the graph width"


def test_a_styled_width_wins_over_the_graph_width(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-width-6", _STYLED, "strokeWidth", "v === '6px'")
    _click_until(page, "set-width-4", _DATA, "strokeWidth", "v === '4px'")
    assert _computed(page, _STYLED, "strokeWidth") == "6px"


def test_heads_at_both_ends_shorten_both_ends(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-end-none", _STYLED, "markerEnd", "v === 'none'")
    _wait_for_layout(page)
    bare_out = _end_point(page, _STYLED, "outlet")
    bare_in = _end_point(page, _STYLED, "inlet")
    _click_until(page, "style-start-open", _STYLED, "markerStart", "v.includes('-open')")
    _click_until(page, "style-end-open", _STYLED, "markerEnd", "v.includes('-open')")
    _wait_for_layout(page)
    # "open" has inset 4; the bag's width is 2.
    assert abs(_distance(_end_point(page, _STYLED, "outlet"), bare_out) - 4.0 * 2) < 0.5
    assert abs(_distance(_end_point(page, _STYLED, "inlet"), bare_in) - 4.0 * 2) < 0.5
    pin = _pin(page, _STYLED, "inlet")
    assert abs(_distance(_end_point(page, _STYLED, "inlet"), pin) - (4.0 * 2 + pin["half"])) < 0.5


def test_a_declared_colour_and_dash_are_drawn(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-color-red", _STYLED, "stroke", "v === 'rgb(255, 0, 0)'")
    _click_until(page, "style-dash-dotted", _STYLED, "strokeDasharray", "v.startsWith('2')")


def test_an_undeclared_start_head_falls_through_to_the_graph_head(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "set-arrow-open", _DATA, "markerEnd", "v.includes('-open')")
    # The partial payload declares only the end head; the test visual wire's arrow_at is INLET,
    # so the start falls through to no head.
    _click_until(page, "style-partial", _STYLED, "markerEnd", "v.includes('-open')")
    assert _computed(page, _STYLED, "markerStart") == "none"


def test_the_geometry_check_accepts_an_edge_headed_at_both_ends(page: Page, harness) -> None:
    _open(page, harness)
    _click_until(page, "style-start-open", _STYLED, "markerStart", "v.includes('-open')")
    batches = page.evaluate(f"() => Number(document.querySelector('{_CANVAS}').dataset.hwEdgeBatch || 0)")
    page.evaluate(
        """() => {
            window.__hwWarnings = [];
            const warn = console.warn.bind(console);
            console.warn = (...args) => { window.__hwWarnings.push(args.join(' ')); warn(...args); };
        }"""
    )
    page.click('[data-testid="resync-edges"]')
    page.wait_for_function(
        f"() => Number(document.querySelector('{_CANVAS}').dataset.hwEdgeBatch || 0) > {batches}"
    )
    _wait_for_layout(page)
    warnings = page.evaluate("() => window.__hwWarnings.filter(w => w.includes('drawn off their pins'))")
    assert warnings == []
