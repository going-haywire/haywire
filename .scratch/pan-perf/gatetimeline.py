"""Timeline of the first pan frame when a card is hovered.

Question: does the hover EXIT the gate forces (the shield becomes hit-testable,
so the browser takes the cursor off the card) stall the start of the gesture?

Records, on one timeline, from a real wheel pan with the cursor parked on a card:

  gate      the shield's pointer-events flipping to 'auto'
  out/over  mouseout / mouseover crossing a [data-node-id]
  ws        a websocket send (pin tooltip hide is a SERVER round trip)
  frame     every animation frame, with its gap

Then prints the events in order with the frame gaps interleaved, so a stall can
be attributed to what happened immediately before it.

    uv run python .scratch/pan-perf/gatetimeline.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

INSTALL = """
() => {
  const T = window.__tl = { t0: performance.now(), ev: [], last: performance.now() };
  const at = () => Math.round(performance.now() - T.t0);
  const log = (kind, detail) => T.ev.push({ t: at(), kind, detail });

  T.raf = requestAnimationFrame(function tick() {
    const now = performance.now();
    const gap = Math.round(now - T.last);
    T.last = now;
    if (gap > 25) log('SLOW FRAME', gap + ' ms');
    T.raf = requestAnimationFrame(tick);
  });

  T.onOut = (e) => { if (e.target.closest && e.target.closest('[data-node-id]')) log('mouseout', ''); };
  T.onOver = (e) => { if (e.target.closest && e.target.closest('[data-node-id]')) log('mouseover', ''); };
  document.addEventListener('mouseout', T.onOut, true);
  document.addEventListener('mouseover', T.onOver, true);

  // The gate flipping is a style write on one element — watch it directly.
  const shield = document.querySelector('[data-hw-gesture-shield]');
  if (shield) {
    T.mo = new MutationObserver(() => log('gate', shield.style.pointerEvents));
    T.mo.observe(shield, { attributes: true, attributeFilter: ['style'] });
  }

  if (!window.__tlWs) {
    window.__tlWs = true;
    const orig = WebSocket.prototype.send;
    WebSocket.prototype.send = function (d) {
      if (window.__tl && window.__tlOn) {
        const s = typeof d === 'string' ? d.slice(0, 60) : '(binary)';
        window.__tl.ev.push({ t: Math.round(performance.now() - window.__tl.t0),
                              kind: 'ws send', detail: s });
      }
      return orig.call(this, d);
    };
  }
  window.__tlOn = true;
}
"""

STOP = """
() => {
  window.__tlOn = false;
  const T = window.__tl;
  cancelAnimationFrame(T.raf);
  document.removeEventListener('mouseout', T.onOut, true);
  document.removeEventListener('mouseover', T.onOver, true);
  if (T.mo) T.mo.disconnect();
  return T.ev;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=float, default=0.25)
    ap.add_argument("--ticks", type=int, default=12)
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
        page.wait_for_timeout(2000)

        spot = page.evaluate(
            """() => {
                const c = window.__hwPerfCanvas();
                const r = c.getBoundingClientRect();
                const cx = r.left + r.width/2, cy = r.top + r.height/2;
                let best=null,bestD=Infinity;
                for (const el of c.querySelectorAll('.node-container > [data-node-id]')) {
                    const b = el.getBoundingClientRect();
                    if (b.width < 8 || b.height < 8) continue;
                    const d = Math.hypot(b.left+b.width/2-cx, b.top+b.height/2-cy);
                    if (d < bestD) { bestD=d; best=b; }
                }
                return best && {x: best.left+best.width/2, y: best.top+best.height/2};
            }"""
        )
        page.mouse.move(spot["x"], spot["y"])
        page.wait_for_timeout(900)
        hovered = page.evaluate("() => document.querySelectorAll('[data-node-id]:hover').length")
        print(f"parked on a card, hovered={hovered} (must be 1 or this measures nothing)")

        page.evaluate(INSTALL)
        page.wait_for_timeout(120)
        for _ in range(args.ticks):
            page.mouse.wheel(0, 40)
            page.wait_for_timeout(16)
        page.wait_for_timeout(500)
        events = page.evaluate(STOP)

        print(f"\n{'t(ms)':>6}  {'what':<12} detail")
        for e in events:
            print(f"{e['t']:>6}  {e['kind']:<12} {e['detail']}")

        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
