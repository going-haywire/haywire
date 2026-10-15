"""A Save-As keeps the canvas: a re-payloaded document keeps its tab panel.

``Slot.repayload_binding`` used to rename the document's ``q-tab-panel``. The client caches a panel
by name, so the rename mounted a fresh canvas while the editor's ``$refs`` entry still pointed at
the old, detached instance — the edges of the re-mount went to the stale one and never drew. The
panel's name is now independent of the binding id. Asserted in a browser: the mount, the refs and
the edge geometry are Vue's and the layout engine's.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready, wait_for_canvas_settled
from tests.ui.harness.pin_edge import PIN_EDGE_JS

pytestmark = pytest.mark.ui

_EDGES = 4
_MAX_ENDPOINT_ERROR_PX = 12.0

_PATH_COUNT = """
() => Array.from(document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]'))
    .filter(p => !p.id.endsWith('_hitarea')).length
"""

_ENDPOINTS = (
    """
() => {%s
    const out = [];
    document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]').forEach(p => {
        if (p.id.endsWith('_hitarea')) return;
        const ctm = p.getScreenCTM();
        const m = /^(.*)\\[(.*)\\]->(.*)\\[(.*)\\]$/.exec(p.id);
        if (!ctm || !m) return;
        const at = (len) => {
            const q = p.getPointAtLength(len);
            return { x: q.x * ctm.a + q.y * ctm.c + ctm.e, y: q.x * ctm.b + q.y * ctm.d + ctm.f };
        };
        const outlet = document.getElementById(`${m[2]}@${m[1]}`);
        const inlet = document.getElementById(`${m[4]}@${m[3]}`);
        out.push({
            start: at(0), end: at(p.getTotalLength()),
            outlet: outlet ? pinEdge(outlet, ctm) : null,
            inlet: inlet ? pinEdge(inlet, ctm) : null,
        });
    });
    return out;
}
"""
    % PIN_EDGE_JS
)

_TRANSFORM = "() => getComputedStyle(document.querySelector('.zoom-pan-content')).transform"

#: Whether the canvas component the page's root instance holds a ref to is the one in the DOM.
_REF_IS_LIVE = """
() => {
    const canvas = document.querySelector('.graph-canvas');
    if (!canvas) return false;
    const id = canvas.id.replace(/^c/, '');
    const app = typeof mounted_app !== 'undefined' ? mounted_app : null;
    const refs = app && app.$refs;
    if (!refs) return false;
    const ref = refs['r' + id];
    const inst = Array.isArray(ref) ? ref[0] : ref;
    return !!(inst && inst.$el && inst.$el.isConnected);
}
"""


def _errors(page: Page) -> list[float]:
    out: list[float] = []
    for row in page.evaluate(_ENDPOINTS):
        for drawn, pin in ((row["start"], row["outlet"]), (row["end"], row["inlet"])):
            assert pin is not None, "an edge's pin is not in the DOM"
            out.append(((drawn["x"] - pin["x"]) ** 2 + (drawn["y"] - pin["y"]) ** 2) ** 0.5)
    return out


def _wait_on_pins(page: Page, timeout_ms: int = 8000) -> list[float]:
    waited = 0
    while True:
        errors = _errors(page) if page.evaluate(_PATH_COUNT) == _EDGES else []
        if (errors and max(errors) < _MAX_ENDPOINT_ERROR_PX) or waited >= timeout_ms:
            return errors
        page.wait_for_timeout(100)
        waited += 100


def test_save_as_keeps_every_edge_on_its_pins_and_the_viewport(page: Page, harness):
    goto_ready(page, f"{harness}/graph-slot?edges={_EDGES}")
    page.wait_for_function("() => document.querySelectorAll('.graph-canvas').length === 1", timeout=10_000)
    wait_for_canvas_settled(page)
    assert _wait_on_pins(page), "the fixture drew no edges"
    before = page.evaluate(_TRANSFORM)
    canvas_before = page.evaluate("() => document.querySelector('.graph-canvas').id")

    page.click('[data-testid="slot-repayload"]')
    page.wait_for_timeout(1000)

    assert page.evaluate("() => document.querySelector('.graph-canvas').id") == canvas_before, (
        "the canvas was re-mounted"
    )
    errors = _wait_on_pins(page)
    assert errors, "no edges drawn after the re-payload"
    assert max(errors) < _MAX_ENDPOINT_ERROR_PX
    assert page.evaluate(_REF_IS_LIVE), "the editor's ref points at a detached canvas"
    assert page.evaluate(_TRANSFORM) == before
