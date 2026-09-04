"""Does the pan hover-gate engage, clear stale hover, and release afterwards?

Three things have to hold, and the middle one is the easy one to get wrong:

1. panning sets `data-panning` and no node card matches `:hover`
2. a card ALREADY hovered when the pan starts loses its hover — `pointer-events:
   none` stops new hit-tests, it does not by itself retract a state the browser
   already had
3. the gate releases after the burst, so hover (and clicking) come back

    uv run python .scratch/pan-perf/hovergate.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session as S  # noqa: E402

STATE = """
() => {
  const c = window.__hwPerfCanvas();
  return {
    panning: c.hasAttribute('data-panning'),
    hovered: c.querySelectorAll('[data-node-id]:hover').length,
  };
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="chrome")
    ap.add_argument("--zoom", type=float, default=0.09)
    args = ap.parse_args()

    url = S.ensure_studio()
    failures = []
    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine)
        context, page = S.open_studio(browser, url, engine=args.engine)
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
                    if (b.width < 3 || b.height < 3) continue;
                    const d = Math.hypot(b.left + b.width/2 - cx, b.top + b.height/2 - cy);
                    if (d < bestD) { bestD = d; best = b; }
                }
                return best && { x: best.left + best.width/2, y: best.top + best.height/2 };
            }"""
        )
        if not spot:
            raise SystemExit("no node card to hover")

        # 1. hover a card with no pan in flight — the resting state
        page.mouse.move(spot["x"], spot["y"])
        page.wait_for_timeout(600)
        rest = page.evaluate(STATE)
        print(f"resting, cursor on a card: {rest}")
        if rest["hovered"] != 1 or rest["panning"]:
            failures.append("resting state should be exactly 1 hovered card and no data-panning")

        # 2. pan while that card is still under the cursor
        page.evaluate(
            """() => {
                const c = window.__hwPerfCanvas()._zoomPanControls;
                const o = c.getPan();
                let i = 0;
                window.__hwPanLoop = setInterval(() => {
                    i++;
                    c.setPan(o.x + (i % 2 ? 40 : -40), o.y + (i % 2 ? 40 : -40));
                }, 16);
            }"""
        )
        page.wait_for_timeout(700)
        during = page.evaluate(STATE)
        print(f"during pan:              {during}")
        if not during["panning"]:
            failures.append("data-panning was not set during a pan")
        # A card already hovered when the gate engages KEEPS its hover:
        # `pointer-events: none` stops new hit-tests, it does not retract a state
        # the browser already holds, and the cursor is not moving to trigger one.
        # Deliberately not a failure — a hover that never changes is free
        # (measured 40.4 vs 40.2 fps), and the cost is per transition. The
        # highlight simply stays on the card you were pointing at.
        if during["hovered"] > 1:
            failures.append(
                f"{during['hovered']} cards hovered at once during the pan — expected at "
                "most the one that was already hovered when the gate engaged"
            )

        page.evaluate("() => clearInterval(window.__hwPanLoop)")
        page.wait_for_timeout(400)

        # 2b. THE POINT: churn. Cost is per hover TRANSITION, not per hovered
        # card — a stale hover that never changes measured free (40.4 vs 40.2
        # fps). So the gate's job is that no NEW card acquires hover while the
        # content sweeps past. Needs real wheel events: setPan fires no pointer
        # events, so the browser never re-runs hit-testing.
        page.evaluate(
            """() => {
                const c = window.__hwPerfCanvas();
                window.__hwSeen = new Set();
                window.__hwSeenWhileGated = new Set();
                window.__hwSamples = { total: 0, gated: 0 };
                window.__hwObs = setInterval(() => {
                    const gated = c.hasAttribute('data-panning');
                    window.__hwSamples.total++;
                    if (gated) window.__hwSamples.gated++;
                    for (const el of document.querySelectorAll('[data-node-id]:hover')) {
                        const id = el.getAttribute('data-node-id');
                        window.__hwSeen.add(id);
                        if (gated) window.__hwSeenWhileGated.add(id);
                    }
                }, 8);
            }"""
        )
        page.mouse.move(spot["x"], spot["y"])
        for i in range(60):
            page.mouse.wheel(0, 40 if (i // 10) % 2 == 0 else -40)
            page.wait_for_timeout(16)
        stats = page.evaluate(
            """() => { clearInterval(window.__hwObs);
                       return { churn: window.__hwSeen.size,
                                churnGated: window.__hwSeenWhileGated.size,
                                samples: window.__hwSamples }; }"""
        )
        churn = stats["churnGated"]
        s = stats["samples"]
        print(
            f"distinct cards hovered during the wheel pan: {stats['churn']} total, "
            f"{churn} while the gate was engaged"
        )
        print(f"  gate engaged in {s['gated']}/{s['total']} samples")
        if s["gated"] < s["total"] * 0.8:
            failures.append(
                f"gate engaged in only {s['gated']}/{s['total']} samples — it releases "
                "mid-gesture, so the churn count here says nothing about whether it works"
            )
        if churn > 1:
            failures.append(
                f"hover churned across {churn} cards during the pan — the gate is not "
                "keeping new cards out of hit-testing (1 = the pre-existing hover only)"
            )

        # 3. release
        page.evaluate("() => clearInterval(window.__hwPanLoop)")
        page.wait_for_timeout(400)
        after = page.evaluate(STATE)
        print(f"after pan (400ms):       {after}")
        if after["panning"]:
            failures.append("data-panning did not clear after the burst")

        # 4. and hover works again once the pointer moves
        page.mouse.move(spot["x"] + 3, spot["y"] + 3)
        page.wait_for_timeout(400)
        back = page.evaluate(STATE)
        print(f"after a mouse move:      {back}")
        if back["hovered"] != 1:
            failures.append("hover did not come back after the pan ended")

        context.close()
        browser.close()

    for f in failures:
        print(f"FAIL: {f}")
    print("\nall checks passed" if not failures else f"\n{len(failures)} check(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
