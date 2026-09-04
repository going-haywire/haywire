"""An open edge drag must do bounded work per mouse move.

The edge drag is MODAL — click a pin, move, click again — so it stays open
across pans and zooms and its move handler runs on every mousemove for as long
as the user is wiring. Anything O(pins) in there is multiplied by every mouse
movement on the canvas, and a pin's position can only be read with
``getBoundingClientRect``, which forces layout.

That is exactly what it used to do: two ``querySelectorAll('.connection-pin')``
sweeps plus a ``getBoundingClientRect`` per pin, per move. Measured at 35% of
the framerate with no pan and no hover churn involved at all. It is now a
cached index in canvas-space coordinates, rebuilt only when node geometry
actually changes — pan and zoom deliberately do not invalidate it, because
canvas coords are invariant under both.

Counting forced layouts rather than timing anything: on a canvas this size a
timing threshold flakes (three runs of one identical pan config have measured
16/56/67 fps), while the count is deterministic and its regression signature is
unmistakable — it goes from a handful to a multiple of the pin count.
"""

import pytest
from playwright.sync_api import Page

from tests.ui.harness.nav import goto_ready

_URL = "http://localhost:8090/graph-dynamic"

pytestmark = pytest.mark.ui

#: Mouse moves to drive. Enough that a per-pin sweep is unmistakable, few
#: enough that the test stays quick.
_MOVES = 20

COUNTER = """
() => {
  window.__rects = 0;
  if (!Element.prototype.__hwCounted) {
    const orig = Element.prototype.getBoundingClientRect;
    Element.prototype.getBoundingClientRect = function () {
      if (window.__rectsOn) window.__rects++;
      return orig.call(this);
    };
    Element.prototype.__hwCounted = true;
  }
  window.__rectsOn = true;
  return document.querySelectorAll('.connection-pin').length;
}
"""


def _pin_centre(page: Page) -> dict:
    return page.evaluate(
        """() => {
            const pins = [...document.querySelectorAll('.connection-pin')]
                .filter(p => p.dataset.pinFlowType !== 'ghost');
            for (const p of pins) {
                const r = p.getBoundingClientRect();
                if (r.width < 2) continue;
                const x = r.left + r.width / 2, y = r.top + r.height / 2;
                const hit = document.elementFromPoint(x, y);
                if (hit && hit.closest('.connection-pin')) return { x, y };
            }
            return null;
        }"""
    )


def test_an_open_edge_drag_does_not_measure_every_pin_per_move(page: Page, harness) -> None:
    goto_ready(page, _URL)
    page.wait_for_selector("[data-node-id]")
    page.wait_for_selector("path[data-edge-id]")
    page.wait_for_timeout(1200)

    pin_count = page.evaluate(COUNTER)
    assert pin_count > 4, f"fixture has only {pin_count} pins — cannot tell O(pins) from O(1)"

    spot = _pin_centre(page)
    assert spot, "no hit-testable pin to start a wire from"

    # Open the wire. It is click-move-click, so one press is the whole gesture.
    page.mouse.move(spot["x"], spot["y"])
    page.mouse.down()
    page.mouse.up()
    page.wait_for_timeout(300)
    assert page.evaluate(
        "() => !![...document.querySelectorAll('#connection-svg path')]"
        ".find(p => p.getAttribute('stroke-dasharray'))"
    ), "clicking the pin opened no preview path — there is no wire to measure"

    page.evaluate("() => { window.__rects = 0; }")
    for i in range(_MOVES):
        page.mouse.move(spot["x"] + 30 + i, spot["y"] + 30 + (i % 5))
        page.wait_for_timeout(16)
    rects = page.evaluate("() => { window.__rectsOn = false; return window.__rects; }")

    page.keyboard.press("Escape")  # leave the canvas idle for the next test

    per_move = rects / _MOVES
    # The invariant is O(1) per move, NOT O(pins) — so the budget is a
    # constant and stays valid however many pins the fixture grows.
    # Measured 6.1/move with 36 pins on the canvas; the per-pin sweep this
    # guards against costs ~2 rects per pin, i.e. ~72/move on the same
    # fixture. 20 sits clear of both.
    budget = 20.0
    assert per_move < budget, (
        f"{per_move:.1f} forced layouts per mouse move with a wire open "
        f"({rects} over {_MOVES} moves, {pin_count} pins on the canvas). "
        f"Budget is {budget:.0f} and the cost must not scale with pin count. "
        f"This is the signature of the pin index being rebuilt — or bypassed "
        f"— on every move instead of once per gesture."
    )
