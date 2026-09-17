"""A canvas that was not on screen must come back with its edges.

A ``q-tab-panel`` that is not the active one is NOT rendered — not hidden with
CSS, not kept in the DOM by ``keep-alive``. So a canvas inside a background
level does not exist, every message addressed to it is dropped, and the
component that appears on first reveal is brand new. Its nodes come back with
it, because they are server-side NiceGUI elements re-rendered into the new
panel; its edges do not, because the canvas builds those itself out of messages
that went to a component that is gone.

That is one bug with three faces: a Group edited while another level was on
screen came back without the edges that changed, a save-as re-keyed the panel
and redrew the graph without any edges at all, and both needed the tab closed
and reopened to recover.

Asserted in a real browser because none of it is visible from Python: the
panel's render strategy is Quasar's, and the edges are DOM geometry only a
layout engine produces.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-hidden-level"

pytestmark = pytest.mark.ui

_EDGES = 6

#: A drawn endpoint should sit on its pin. The slack covers the pin's own radius
#: and sub-pixel rounding; the failure mode is tens to hundreds of pixels out.
_MAX_ENDPOINT_ERROR_PX = 12.0

#: Every edge path of the canvas, by its `d` attribute (hit areas excluded).
_CANVAS = '.graph-canvas[data-testid="hidden-canvas"]'

_PATH_DS = f"""
() => Array.from(
    document.querySelectorAll('{_CANVAS} .connection-svg path[data-edge-id]')
).filter(p => !p.id.endsWith('_hitarea')).map(p => p.getAttribute('d') || '')
"""


def _degenerate(d: str) -> bool:
    """A path drawn from zero-size pin rects: every coordinate collapses to 0."""
    numbers = [n for n in d.replace(",", " ").split() if n.replace(".", "").replace("-", "").isdigit()]
    return not numbers or all(float(n) == 0.0 for n in numbers)


def _wait_for_all_edges(page: Page) -> list[str]:
    page.wait_for_function(f"() => ({_PATH_DS})().length === {_EDGES}", timeout=10_000)
    return page.evaluate(_PATH_DS)


#: Each edge's drawn endpoints in SCREEN pixels, via the browser's own CTM, next
#: to the screen centres of the two pins it claims to join. Comparing those two
#: needs none of the canvas's coordinate maths, which is the thing under test.
_ENDPOINTS_VS_PINS = (
    """
() => {
    const root = document.querySelector('%s');
    if (!root) return [];
    const out = [];
    root.querySelectorAll('.connection-svg path[data-edge-id]').forEach(p => {
        if (p.id.endsWith('_hitarea')) return;
        const ctm = p.getScreenCTM();
        if (!ctm) return;
        const at = (len) => {
            const q = p.getPointAtLength(len);
            return { x: q.x * ctm.a + q.y * ctm.c + ctm.e, y: q.x * ctm.b + q.y * ctm.d + ctm.f };
        };
        const centre = (el) => {
            const r = el.getBoundingClientRect();
            return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
        };
        const info = window.__hwEdgeInfo ? window.__hwEdgeInfo(p.id) : null;
        out.push({
            id: p.id,
            start: at(0),
            end: at(p.getTotalLength()),
            outlet: info && info.outlet ? centre(info.outlet) : null,
            inlet: info && info.inlet ? centre(info.inlet) : null,
        });
    });
    return out;
}
"""
    % _CANVAS
)

#: Resolves an edge's two pin elements the way canvas.vue names them, so the
#: comparison above has something to compare against.
_INSTALL_EDGE_INFO = """
() => {
    window.__hwEdgeInfo = (edgeId) => {
        const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(edgeId);
        if (!m) return null;
        return {
            outlet: document.getElementById(`${m[2]}@${m[1]}`),
            inlet: document.getElementById(`${m[4]}@${m[3]}`),
        };
    };
}
"""


def _wait_until_on_pins(page: Page, timeout_s: float = 5.0) -> list[float]:
    """Poll until every drawn endpoint sits on its pin, or the budget runs out.

    Polled rather than slept on: the repair lands a frame after the panel is
    re-attached, and a fixed wait either flakes under load or is dead time.
    """
    import time

    deadline = time.monotonic() + timeout_s
    while True:
        errors = _endpoint_errors(page)
        settled = bool(errors) and max(errors) < _MAX_ENDPOINT_ERROR_PX
        if settled or time.monotonic() > deadline:
            return errors
        page.wait_for_timeout(100)


def _endpoint_errors(page: Page) -> list[float]:
    """Distance in screen px between each drawn endpoint and the pin it joins."""
    page.evaluate(_INSTALL_EDGE_INFO)
    rows = page.evaluate(_ENDPOINTS_VS_PINS)
    errors = []
    for row in rows:
        for drawn, pin in ((row["start"], row["outlet"]), (row["end"], row["inlet"])):
            if pin is None:
                continue
            errors.append(((drawn["x"] - pin["x"]) ** 2 + (drawn["y"] - pin["y"]) ** 2) ** 0.5)
    return errors


def test_a_background_level_is_not_in_the_dom_at_all(page: Page, harness):
    """The fact the rest of this file rests on. If this changes, the fix can too."""
    goto_ready(page, f"{_URL}?edges={_EDGES}")

    assert page.evaluate("() => document.querySelectorAll('.graph-canvas').length") == 0


def test_edges_are_drawn_once_the_canvas_is_revealed(page: Page, harness):
    goto_ready(page, f"{_URL}?edges={_EDGES}")

    page.click('[data-testid="reveal"]')

    assert len(_wait_for_all_edges(page)) == _EDGES


def test_the_revealed_edges_have_real_geometry(page: Page, harness):
    """Drawn is not enough — an edge measured before layout is a path of zeros."""
    goto_ready(page, f"{_URL}?edges={_EDGES}")

    page.click('[data-testid="reveal"]')

    collapsed = [d for d in _wait_for_all_edges(page) if _degenerate(d)]
    assert collapsed == [], f"{len(collapsed)} edge(s) drawn from zero-size pin rects"


def test_re_keying_the_panel_brings_the_edges_back(page: Page, harness):
    """What a save-as does: the tab panel is renamed, which re-MOUNTS the canvas.

    Verified by console trace: the component logs its mount, emits
    ``canvasMounted`` and receives a fresh batch. The teardown itself is too
    brief to catch from here, so the assertion is on the outcome — the edges are
    all there, and on their pins — rather than on observing the gap.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)

    page.click('[data-testid="rekey"]')
    page.wait_for_timeout(500)

    assert len(_wait_for_all_edges(page)) == _EDGES
    errors = _endpoint_errors(page)
    assert errors
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX, f"worst endpoint {max(errors):.0f}px from its pin"


def test_the_canvas_reports_the_batch_it_drew(page: Page, harness):
    """What the load overlay waits on, instead of counting paths against a total."""
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)

    stamped = page.evaluate(
        """() => {
            const root = document.querySelector('.graph-canvas[data-testid="hidden-canvas"]');
            return {
                batches: Number(root.dataset.hwEdgeBatch || 0),
                drawn: Number(root.dataset.hwEdgeDrawn || 0),
                parked: Number(root.dataset.hwEdgeParked || 0),
            };
        }"""
    )

    assert stamped["batches"] >= 1
    assert stamped["drawn"] == _EDGES
    assert stamped["parked"] == 0


def test_edges_re_measure_after_a_re_mount_at_another_zoom(page: Page, harness):
    """A canvas mounts believing zoom is 1, and divides screen pixels by it.

    Hide, zoom, reveal: the canvas is rebuilt and its edges re-sent while the
    transform is already 0.35, so anything measured before the ZoomPanContainer
    reports in is drawn at ~3x too small, bunched towards the canvas origin.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)
    page.click('[data-testid="zoom-out"]')
    page.wait_for_timeout(300)

    page.click('[data-testid="hide"]')
    page.wait_for_function(f"() => ({_PATH_DS})().length === 0", timeout=10_000)
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)
    page.wait_for_timeout(500)

    errors = _endpoint_errors(page)
    assert errors, "no edge endpoints could be compared against their pins"
    assert max(errors) < 12.0, (
        f"edges are drawn away from their pins (worst {max(errors):.0f}px) — measured against the wrong zoom"
    )


def test_an_edge_added_while_off_screen_is_drawn_on_its_pins(page: Page, harness):
    """The undo-in-a-background-level case, and the one the others miss.

    Quasar caches a deselected panel with <keep-alive>: the component stays
    alive with its DOM detached. An edge that arrives in that window IS created
    — the pins are reachable through the detached tree — but every
    ``getBoundingClientRect`` in it returns zeros, so the edge is drawn at the
    canvas origin. Re-attaching does not re-measure anything by itself.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)

    page.click('[data-testid="hide"]')
    page.wait_for_timeout(300)
    page.click('[data-testid="add-edge"]')
    page.wait_for_timeout(500)
    page.click('[data-testid="reveal"]')
    page.wait_for_function(f"() => ({_PATH_DS})().length === {_EDGES + 1}", timeout=10_000)
    page.wait_for_timeout(500)

    errors = _endpoint_errors(page)
    assert len(errors) == (_EDGES + 1) * 2
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX, (
        f"an edge added off screen is {max(errors):.0f}px from its pin — "
        "measured against a detached DOM and never re-measured"
    )


def test_a_re_mount_at_another_zoom_draws_on_the_pins(page: Page, harness):
    """``zoomState`` starts at 1 on every mount, and pin coords divide by it.

    Re-keying the panel rebuilds the canvas while the transform is already
    0.35, so an edge batch arriving before the ZoomPanContainer reports in is
    measured at 1 and drawn at ~3x too small, bunched towards the origin.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)
    page.click('[data-testid="zoom-out"]')
    page.wait_for_timeout(400)

    page.click('[data-testid="rekey"]')
    page.wait_for_timeout(800)
    _wait_for_all_edges(page)

    errors = _endpoint_errors(page)
    assert errors
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX, (
        f"edges are {max(errors):.0f}px from their pins after a re-mount at zoom 0.35 — "
        "measured before the canvas knew its transform"
    )


#: Move every edge path far from its pins, the way a measurement against the
#: wrong zoom or a detached DOM does. Only the drawing is corrupted — the model
#: behind it is untouched, so a re-measure restores the correct geometry.
_DISPLACE_EDGES = (
    """
() => {
    const root = document.querySelector('%s');
    if (!root) return 0;
    let n = 0;
    root.querySelectorAll('.connection-svg path[data-edge-id]').forEach(p => {
        p.setAttribute('d', 'M 0 0 C 10 10, 20 20, 30 30');
        n++;
    });
    return n;
}
"""
    % _CANVAS
)


def test_edges_drawn_off_their_pins_are_repaired_on_re_attach(page: Page, harness):
    """The automatic form of the user's remedy — select every node, deselect again.

    Which race displaced them is not the point: the canvas checks the result
    against the pins, through the browser's own CTM, and re-measures when they
    disagree. The check shares no arithmetic with the code that drew the edge,
    so a canvas that measured wrongly cannot confirm itself.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)

    assert page.evaluate(_DISPLACE_EDGES) == _EDGES * 2
    assert max(_endpoint_errors(page)) > _MAX_ENDPOINT_ERROR_PX, "the fixture did not displace anything"

    page.click('[data-testid="hide"]')
    page.wait_for_timeout(300)
    page.click('[data-testid="reveal"]')

    errors = _wait_until_on_pins(page)
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX, (
        f"edges left {max(errors):.0f}px from their pins — the canvas did not check its own geometry"
    )


def test_an_edge_drawn_at_a_non_default_zoom_lands_on_its_pins(page: Page, harness):
    """Pin coordinates are read from the SVG's live screen matrix.

    They used to come from ``zoomState.zoom``, which starts at 1 on every mount
    and is only corrected when this canvas's ZoomPanContainer reports in.
    Anything measured in that window came out scaled by the ratio between the
    two — measured in the field at 2.3x, over 850px of displacement, and mixed
    with correctly-drawn edges in the same graph.
    """
    goto_ready(page, f"{_URL}?edges={_EDGES}")
    page.click('[data-testid="reveal"]')
    _wait_for_all_edges(page)
    page.click('[data-testid="zoom-out"]')
    page.wait_for_timeout(400)

    page.click('[data-testid="add-edge"]')
    page.wait_for_function(f"() => ({_PATH_DS})().length === {_EDGES + 1}", timeout=10_000)
    page.wait_for_timeout(400)

    errors = _endpoint_errors(page)
    assert len(errors) == (_EDGES + 1) * 2
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX, (
        f"an edge drawn at zoom 0.35 is {max(errors):.0f}px from its pin"
    )
