"""Edge appearance in the browser: width, selection, hit area, state colours and arrow heads.

Everything here lives in canvas.vue's stylesheet and path math, which the
Python tiers cannot see. Colours are compared against fixed token values the
harness page sets on :root.
"""

import pytest
from playwright.sync_api import Page

from haywire.core.edge.arrow_heads import ARROW_HEADS, DEFAULT_HEAD_SIZE, HEAD_SIZES

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.pin_edge import PIN_EDGE_JS

#: The factor every head drawn at the default size takes.
_SIZE = HEAD_SIZES[DEFAULT_HEAD_SIZE]

_PATH = "/graph-edge-appearance"

_DATA = 'path.hw-edge[data-edge-id*="[result]->"]'
_CONTROL = 'path.hw-edge[data-edge-id*="[exec]->"]'
_CALLBACK = 'path.hw-edge[data-edge-id*="[listen_callback]->"]'
_INVALID = 'path.hw-edge[data-edge-id*="[add_out_0]->"]'
_DATA_HIT = 'path.hw-edge-hit[data-edge-id*="[result]->"]'

pytestmark = pytest.mark.ui


def _open(page: Page, harness) -> None:
    goto_ready(page, f"{harness}{_PATH}")
    page.wait_for_selector(_DATA)
    wait_for_canvas_settled(page)


#: What each graph-default button changes: the canvas var it sets on every edge, and that var's value.
_EXPECTED_VAR = {
    "set-width-4": ("--hw-edge-width", "4px"),
    "set-arrow-open": ("--hw-edge-head", f"-open-{DEFAULT_HEAD_SIZE})"),
    "set-arrow-ring": ("--hw-edge-head", f"-circle_hollow-{DEFAULT_HEAD_SIZE})"),
    "set-arrow-none": ("--hw-edge-head", "none"),
    "set-arrow-size-xl": ("--hw-edge-head", "-open-xl)"),
}


def _click(page: Page, testid: str) -> None:
    """Click a graph-default button and wait until the canvas applied it.

    The canvas sets the var and re-lays-out its paths in the same update, so once the
    var reads the new value the paths are drawn with it too.
    """
    var, expected = _EXPECTED_VAR[testid]
    page.click(f'[data-testid="{testid}"]')
    page.wait_for_function(
        """([sel, v, want]) => {
            const value = getComputedStyle(document.querySelector(sel)).getPropertyValue(v).trim();
            return value === want || value.endsWith(want);
        }""",
        arg=[_DATA, var, expected],
        timeout=5000,
    )
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def _computed(page: Page, selector: str, prop: str) -> str:
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) throw new Error('missing ' + sel);
            return getComputedStyle(el)[prop];
        }""",
        [selector, prop],
    )


def _with_class(page: Page, selector: str, cls: str, prop: str) -> str:
    """Add *cls* to the element, read a computed property, then remove the class again."""
    return page.evaluate(
        """([sel, cls, prop]) => {
            const el = document.querySelector(sel);
            el.classList.add(cls);
            const value = getComputedStyle(el)[prop];
            el.classList.remove(cls);
            return value;
        }""",
        [selector, cls, prop],
    )


def test_a_computed_edge_draws_at_the_graph_width(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA, "strokeWidth") == "2px"
    assert page.evaluate("(sel) => document.querySelector(sel).getAttribute('stroke-width')", _DATA) is None

    _click(page, "set-width-4")

    assert _computed(page, _DATA, "strokeWidth") == "4px"


def test_selected_and_active_keep_the_edge_width(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-width-4")

    assert _with_class(page, _DATA, "connection-selected", "strokeWidth") == "4px"
    assert _with_class(page, _DATA, "connection-active", "strokeWidth") == "4px"


def test_the_hit_area_is_the_width_plus_the_canvas_padding(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA_HIT, "strokeWidth") == "22px"


def test_an_invalid_edge_is_drawn_in_the_danger_token(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _INVALID, "stroke") == "rgb(200, 10, 10)"


def test_a_missing_pin_colour_falls_back_to_the_edge_default_token(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, ".connection-svg", "color") == "rgb(10, 120, 200)"


def _end_point(page: Page, selector: str, end: str) -> dict:
    """The path's point at its inlet ('inlet') or outlet ('outlet') end, in SVG coordinates."""
    return page.evaluate(
        """([sel, end]) => {
            const path = document.querySelector(sel);
            const point = path.getPointAtLength(end === 'inlet' ? path.getTotalLength() : 0);
            return { x: point.x, y: point.y };
        }""",
        [selector, end],
    )


def _distance(a: dict, b: dict) -> float:
    return ((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2) ** 0.5


def _pin(page: Page, selector: str, end: str) -> dict:
    """The pin at the edge's inlet or outlet end, in SVG coordinates.

    Its centre (``x``/``y``), its ``edge`` point (where an end without a head
    sits) and ``half``, the distance between the two.
    """
    return page.evaluate(
        """([sel, end]) => {%s
            const path = document.querySelector(sel);
            const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(path.dataset.edgeId);
            const pin = document.getElementById(end === 'inlet' ? `${m[4]}@${m[3]}` : `${m[2]}@${m[1]}`);
            const ctm = path.getScreenCTM();
            const toSvg = (p) => new DOMPoint(p.x, p.y).matrixTransform(ctm.inverse());
            const r = pin.getBoundingClientRect();
            const c = toSvg({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
            const e = toSvg(pinEdge(pin, ctm));
            return {
                x: c.x, y: c.y,
                edge: { x: e.x, y: e.y },
                half: Math.hypot(e.x - c.x, e.y - c.y),
            };
        }"""
        % PIN_EDGE_JS,
        [selector, end],
    )


def test_every_head_has_one_marker_per_size_in_the_canvas(page: Page, harness) -> None:
    _open(page, harness)
    count = page.evaluate("() => document.querySelectorAll('marker.hw-edge-head').length")
    assert count == len(ARROW_HEADS) * len(HEAD_SIZES)
    widths = page.evaluate(
        """(sizes) => sizes.map((size) => Number(document.querySelector(
            `marker.hw-edge-head[id$="-arrow-${size}"]`).getAttribute('markerWidth')))""",
        [DEFAULT_HEAD_SIZE, "xl"],
    )
    assert widths[1] == widths[0] * HEAD_SIZES["xl"] / HEAD_SIZES[DEFAULT_HEAD_SIZE]


def test_no_head_by_default(page: Page, harness) -> None:
    _open(page, harness)
    assert _computed(page, _DATA, "markerEnd") == "none"
    assert _computed(page, _DATA, "markerStart") == "none"


def test_a_graph_head_sits_at_the_inlet_of_data_and_control_edges(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    for selector in (_DATA, _CONTROL):
        assert "-open" in _computed(page, selector, "markerEnd")
        assert _computed(page, selector, "markerStart") == "none"


def test_a_callback_edge_draws_its_head_at_the_outlet(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    assert "-open" in _computed(page, _CALLBACK, "markerStart")
    assert _computed(page, _CALLBACK, "markerEnd") == "none"


def test_the_path_stops_short_of_the_inlet_by_the_head_inset(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-width-4")
    full = _end_point(page, _DATA, "inlet")
    pin = _pin(page, _DATA, "inlet")
    # No head: the end sits on its pin's edge, half the pin's size from its centre.
    assert _distance(full, pin["edge"]) < 0.5

    _click(page, "set-arrow-open")
    end = _end_point(page, _DATA, "inlet")
    # The unheaded (outlet) end of a headed edge sits on its pin's edge.
    assert _distance(_end_point(page, _DATA, "outlet"), _pin(page, _DATA, "outlet")["edge"]) < 0.5
    assert abs(_distance(end, full) - 4.0 * 4 * _SIZE) < 0.5
    # Measured from the pin itself: the head's tip lands on the pin's edge.
    assert abs(_distance(end, pin) - (4.0 * 4 * _SIZE + pin["half"])) < 0.5

    _click(page, "set-arrow-none")
    assert _distance(_end_point(page, _DATA, "inlet"), full) < 0.5


def test_a_graph_head_size_scales_the_inset(page: Page, harness) -> None:
    _open(page, harness)
    full = _end_point(page, _DATA, "inlet")
    _click(page, "set-width-4")
    _click(page, "set-arrow-open")
    _click(page, "set-arrow-size-xl")
    end = _end_point(page, _DATA, "inlet")
    assert abs(_distance(end, full) - 4.0 * 4 * HEAD_SIZES["xl"]) < 0.5


def test_a_callback_head_shortens_the_outlet_end(page: Page, harness) -> None:
    _open(page, harness)
    full = _end_point(page, _CALLBACK, "outlet")
    pin = _pin(page, _CALLBACK, "outlet")
    assert _distance(full, pin["edge"]) < 0.5

    _click(page, "set-arrow-ring")

    end = _end_point(page, _CALLBACK, "outlet")
    assert abs(_distance(end, full) - 4.5 * 2 * _SIZE) < 0.5
    assert abs(_distance(end, pin) - (4.5 * 2 * _SIZE + pin["half"])) < 0.5


def test_a_hollow_head_is_hollow(page: Page, harness) -> None:
    _open(page, harness)
    fill = page.evaluate(
        "() => getComputedStyle(document.querySelector("
        f"'marker.hw-edge-head[id$=\"-circle_hollow-{DEFAULT_HEAD_SIZE}\"] circle')).fill"
    )
    assert fill == "none"


def test_arrow_at_none_draws_no_head(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-arrow-open")
    assert _with_class(page, _DATA, "edge-arrow-none", "markerEnd") == "none"


def test_a_canvas_update_keeps_the_head_markers(page: Page, harness) -> None:
    _open(page, harness)
    page.evaluate("() => { window.__hwHeadMarker = document.querySelector('marker.hw-edge-head'); }")

    _click(page, "set-width-4")

    assert page.evaluate(
        """() => {
            const marker = window.__hwHeadMarker;
            return marker.isConnected && document.getElementById(marker.id) === marker;
        }"""
    )


def test_a_width_change_moves_a_headed_end(page: Page, harness) -> None:
    _open(page, harness)
    full = _end_point(page, _DATA, "inlet")
    assert _distance(full, _pin(page, _DATA, "inlet")["edge"]) < 0.5

    _click(page, "set-arrow-open")
    assert abs(_distance(_end_point(page, _DATA, "inlet"), full) - 4.0 * 2 * _SIZE) < 0.5

    _click(page, "set-width-4")
    assert abs(_distance(_end_point(page, _DATA, "inlet"), full) - 4.0 * 4 * _SIZE) < 0.5


#: Screen px between the callback edge's drawn start and its outlet pin's edge,
#: with the pins resolved the way canvas.vue names them (``pin@node``).
_CALLBACK_START_OFF_PIN = (
    """
(sel) => {%s
    const path = document.querySelector(sel);
    const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(path.dataset.edgeId);
    const ctm = path.getScreenCTM();
    const e = pinEdge(document.getElementById(`${m[2]}@${m[1]}`), ctm);
    const p = path.getPointAtLength(0);
    const dx = p.x * ctm.a + p.y * ctm.c + ctm.e - e.x;
    const dy = p.x * ctm.b + p.y * ctm.d + ctm.f - e.y;
    return Math.sqrt(dx * dx + dy * dy);
}
"""
    % PIN_EDGE_JS
)


def test_an_outlet_head_does_not_read_as_an_edge_off_its_pin(page: Page, harness) -> None:
    _open(page, harness)
    _click(page, "set-width-4")
    _click(page, "set-arrow-ring")
    # Aim setZoom at the callback edge's start. It clamps to the max zoom (1.0), so this is
    # effectively zoom 1; the gap its head leaves before the pin's edge (the 18px inset)
    # still exceeds the canvas's 12px geometry tolerance.
    page.evaluate(
        """(sel) => {
            const p = document.querySelector(sel);
            const ctm = p.getScreenCTM();
            const q = p.getPointAtLength(0);
            const x = q.x * ctm.a + q.y * ctm.c + ctm.e;
            const y = q.x * ctm.b + q.y * ctm.d + ctm.f;
            document.querySelector('.zoom-pan-container')._zoomPanControls.setZoom(1.5, x, y);
        }""",
        _CALLBACK,
    )
    wait_for_canvas_settled(page)
    assert page.evaluate(_CALLBACK_START_OFF_PIN, _CALLBACK) > 12, (
        "the fixture did not push the head past 12px"
    )

    canvas = '.graph-canvas[data-testid="edge-appearance-canvas"]'
    batches = page.evaluate(f"() => Number(document.querySelector('{canvas}').dataset.hwEdgeBatch || 0)")
    page.evaluate(
        """() => {
            window.__hwWarnings = [];
            const warn = console.warn.bind(console);
            console.warn = (...args) => { window.__hwWarnings.push(args.join(' ')); warn(...args); };
        }"""
    )
    page.click('[data-testid="resync-edges"]')
    page.wait_for_function(
        f"() => Number(document.querySelector('{canvas}').dataset.hwEdgeBatch || 0) > {batches}"
    )
    # The check runs one animation frame after the batch is stamped.
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    warnings = page.evaluate("() => window.__hwWarnings.filter(w => w.includes('drawn off their pins'))")
    assert warnings == []


#: Whether the canvas's width watcher re-lays out the edge whose id contains the given fragment.
_RELAID_ON_WIDTH = """(frag) => {
    let canvas = null;
    for (let i = 0; i < 5000 && !canvas; i++) {
        const c = getElement(i);
        if (c && c.$el && c.$el.dataset && c.$el.dataset.testid === 'edge-appearance-canvas') canvas = c;
    }
    for (const [id, info] of canvas.edgePaths) {
        if (id.includes(frag)) return canvas._followsGraphWidth(info) && canvas._isHeaded(info);
    }
    throw new Error('no edge ' + frag);
}"""


def test_a_width_change_re_lays_out_only_headed_edges_at_the_graph_width(page: Page, harness) -> None:
    """F18: an unheaded edge's path does not depend on the width; a styled width ignores the graph's."""
    _open(page, harness)
    assert page.evaluate(_RELAID_ON_WIDTH, "[result]->") is False
    assert page.evaluate(_RELAID_ON_WIDTH, "[note_out]->") is False, "a styled edge has its own width"

    _click(page, "set-arrow-open")
    assert page.evaluate(_RELAID_ON_WIDTH, "[result]->") is True


def test_the_hit_area_covers_the_heads_span(page: Page, harness) -> None:
    """F19: the drawn path stops a head's length short of the pin; its hit area reaches the pin's edge."""
    _open(page, harness)
    _click(page, "set-width-4")
    _click(page, "set-arrow-open")
    pin = _pin(page, _DATA, "inlet")

    assert _distance(_end_point(page, _DATA, "inlet"), pin["edge"]) > 10
    assert _distance(_end_point(page, _DATA_HIT, "inlet"), pin["edge"]) < 0.5


_OFF_CURVE_POINT_JS = """() => {
  for (const path of document.querySelectorAll('path.hw-edge')) {
    const ctm = path.ownerSVGElement.getScreenCTM();
    const box = path.getBBox();
    const toScreen = (x, y) => ({ x: x * ctm.a + ctm.e, y: y * ctm.d + ctm.f });
    const mid = path.getPointAtLength(path.getTotalLength() / 2);
    const total = path.getTotalLength();
    const distance = (p) => {
        let best = Infinity;
        for (let i = 0; i <= 200; i++) {
            const q = path.getPointAtLength((i / 200) * total);
            best = Math.min(best, Math.hypot((q.x - p.x) * ctm.a, (q.y - p.y) * ctm.d));
        }
        return best;
    };
    for (const [x, y] of [[box.x, box.y + box.height], [box.x + box.width, box.y]]) {
        const cx = box.x + box.width / 2, cy = box.y + box.height / 2;
        const inset = { x: x + (cx - x) * 0.1, y: y + (cy - y) * 0.1 };
        const screen = toScreen(inset.x, inset.y);
        const hit = document.elementFromPoint(screen.x, screen.y);
        if (distance(inset) > 25 && hit && !hit.closest('[data-node-id]')) {
            return { off: screen, on: toScreen(mid.x, mid.y) };
        }
    }
  }
  return null;
}"""


def test_a_click_selects_an_edge_only_where_the_curve_is(page: Page, harness) -> None:
    _open(page, harness)
    # The harness edges are a few dozen px across; zoom in until one has room for an empty spot.
    # Zoom about the edge itself so it stays in view.
    anchor = page.evaluate(
        """(sel) => {
            const path = document.querySelector(sel);
            const ctm = path.ownerSVGElement.getScreenCTM();
            const p = path.getPointAtLength(path.getTotalLength() / 2);
            return [p.x * ctm.a + ctm.e, p.y * ctm.d + ctm.f];
        }""",
        _DATA,
    )
    for _ in range(8):
        page.evaluate(
            """([x, y]) => document.querySelector('.graph-canvas').dispatchEvent(new WheelEvent('wheel', {
                deltaY: -100, ctrlKey: true, clientX: x, clientY: y, bubbles: true, cancelable: true,
            }))""",
            anchor,
        )
        _wait_for_frames(page)
    points = page.evaluate(_OFF_CURVE_POINT_JS)
    assert points is not None, "no empty spot inside the edge's bounding box, more than 25px from its curve"

    page.mouse.click(points["off"]["x"], points["off"]["y"])
    _wait_for_frames(page)
    assert page.locator(".connection-selected").count() == 0, "a click in the bounding box's empty corner"

    page.mouse.click(points["on"]["x"], points["on"]["y"])
    page.wait_for_selector(".connection-selected", state="attached", timeout=5000)


def _wait_for_frames(page: Page) -> None:
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


_HANDLES_JS = """(sel) => {
    const path = document.querySelector(sel);
    const id = path.dataset.edgeId;
    const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(id);
    const dot = (end) => document.getElementById(`${id}_handle_${end}`);
    const pin = (key) => document.getElementById(key);
    const [a, b] = [dot('start'), dot('end')];
    if (!a || !b) return null;
    const centre = (el) => {
        const r = el.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
    };
    const off = (dotEl, pinEl) => {
        const [d, p] = [centre(dotEl), centre(pinEl)];
        return Math.hypot(d.x - p.x, d.y - p.y);
    };
    return {
        start: off(a, pin(`${m[2]}@${m[1]}`)),
        end: off(b, pin(`${m[4]}@${m[3]}`)),
    };
}"""


def test_the_active_edge_shows_a_dot_at_each_end_and_keeps_the_selection_glow(page: Page, harness) -> None:
    _open(page, harness)
    mid = page.evaluate(
        """(sel) => {
            const path = document.querySelector(sel);
            const ctm = path.ownerSVGElement.getScreenCTM();
            const p = path.getPointAtLength(path.getTotalLength() / 2);
            return [p.x * ctm.a + ctm.e, p.y * ctm.d + ctm.f];
        }""",
        _DATA,
    )
    page.mouse.click(*mid)
    page.wait_for_selector(f"{_DATA}.connection-active", state="attached", timeout=5000)

    handles = page.evaluate(_HANDLES_JS, _DATA)
    assert handles is not None, "no end dots on the active edge"
    assert handles["start"] < 1.5, "the start dot sits on the outlet pin's centre"
    assert handles["end"] < 1.5, "the end dot sits on the inlet pin's centre"
    glow = page.evaluate(
        """(sel) => {
            const g = document.getElementById(document.querySelector(sel).dataset.edgeId + '_glow');
            return g && { d: g.getAttribute('d'), filter: getComputedStyle(g).filter };
        }""",
        _DATA,
    )
    assert glow is not None, "the active edge is selected, so it glows"
    assert "blur(6px)" in glow["filter"], "the glow takes its 12px size from the theme token's fallback"

    empty = page.evaluate(
        """() => {
            for (let y = 20; y < innerHeight; y += 20) {
                for (let x = 20; x < innerWidth; x += 20) {
                    const el = document.elementFromPoint(x, y);
                    const free = el && el.closest('.graph-canvas') && !el.closest('[data-node-id]');
                    if (free && el.tagName !== 'path') {
                        return [x, y];
                    }
                }
            }
            return null;
        }"""
    )
    assert empty is not None, "no empty canvas spot in view"
    page.mouse.click(*empty)
    page.wait_for_selector(f"{_DATA}.connection-active", state="detached", timeout=5000)
    assert page.evaluate(_HANDLES_JS, _DATA) is None
    assert page.locator(".hw-edge-glow-path").count() == 0
