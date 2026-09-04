"""What happens to an ALREADY magnified card when a gesture starts?

The magnifier applies after a dwell (hoverEnterDelay, 350ms) and only below
hoverScaleCutoffZoom. The gate suppresses a NEW magnify, but a card magnified
before the gesture began is a different case: raising the shield takes the
cursor off it, which fires mouseleave, which releases the magnify — a transform
transition, mid-pan, plus the edge sweeps its transitionstart schedules.

Reported symptom this is chasing: hover a node, start a pan, get a ~0.5s freeze
and a visible jump, then smooth.

    uv run python .scratch/pan-perf/magnifygate.py --zoom 0.25
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

STATE = """
() => {
  const cards = [...document.querySelectorAll('.zoom-pan-lod0')];
  return {
    magnified: cards.filter(c => c._magnified).length,
    hovered: document.querySelectorAll('[data-node-id]:hover').length,
    gated: window.HwInputArbiter.for(
      document.querySelector('.zoom-pan-container').id).isGated(),
  };
}
"""

COUNT_TRANSITIONS = """
() => {
  window.__mgCount = 0;
  window.__mgFn = (e) => { if (e.propertyName === 'transform') window.__mgCount++; };
  document.addEventListener('transitionstart', window.__mgFn, true);
}
"""

STOP_TRANSITIONS = """
() => {
  document.removeEventListener('transitionstart', window.__mgFn, true);
  return window.__mgCount;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=float, default=0.25, help="must be below hoverScaleCutoffZoom")
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_nodes_settled(page)
        page.bring_to_front()
        page.evaluate("(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)", args.zoom)
        page.wait_for_timeout(1500)

        spot = page.evaluate(
            """() => {
                const c = window.__hwPerfCanvas();
                const r = c.getBoundingClientRect();
                const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
                let best = null, bestD = Infinity;
                for (const el of c.querySelectorAll('.node-container > [data-node-id]')) {
                    const b = el.getBoundingClientRect();
                    if (b.width < 8 || b.height < 8) continue;
                    const d = Math.hypot(b.left + b.width/2 - cx, b.top + b.height/2 - cy);
                    if (d < bestD) { bestD = d; best = b; }
                }
                return best && { x: best.left + best.width/2, y: best.top + best.height/2 };
            }"""
        )
        if not spot:
            raise SystemExit("no card on screen")

        # Dwell on the card until the magnifier fires.
        page.mouse.move(spot["x"], spot["y"])
        page.wait_for_timeout(1200)
        before = page.evaluate(STATE)
        print(f"after dwelling on a card: {before}")
        if before["magnified"] == 0:
            print(
                "  (no magnify — hover_scale_enabled may be off, or this zoom is "
                "at/above hover_scale_cutoff_zoom, so there is nothing to release)"
            )

        # Now start a gesture, exactly as a wheel burst would.
        page.evaluate(COUNT_TRANSITIONS)
        t0 = time.perf_counter()
        page.evaluate(
            """() => window.HwInputArbiter.for(
                 document.querySelector('.zoom-pan-container').id).begin('pan', 'probe')"""
        )
        raise_ms = (time.perf_counter() - t0) * 1000
        page.wait_for_timeout(600)
        during = page.evaluate(STATE)
        transitions = page.evaluate(STOP_TRANSITIONS)
        print(f"raising the gesture took {raise_ms:.0f} ms")
        print(f"during the gesture:       {during}")
        print(f"transform transitions started by raising it: {transitions}")

        page.evaluate(
            """() => window.HwInputArbiter.for(
                 document.querySelector('.zoom-pan-container').id).end('pan')"""
        )
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
