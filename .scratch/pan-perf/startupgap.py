"""What is not yet wired while a big graph is still arriving, and for how long?

Two symptoms are reported only "out of the box", both gone after ~a minute:

  * the first pan/zoom over a hovered node freezes ~0.5s, then the graph jumps
  * a pan/zoom started too early reaches the BROWSER's zoom instead of the
    canvas, which only View > Actual Size undoes

The second one is the diagnostic: canvas zoom is `@wheel.prevent` on the
zoom-pan container, so a wheel that reaches browser zoom is a wheel that found
no handler. This polls, from first paint, for each thing that has to be true
before a gesture behaves — and dispatches a probe wheel each tick to see
whether anything would have called preventDefault.

    uv run python .scratch/pan-perf/startupgap.py
    uv run python .scratch/pan-perf/startupgap.py --graph 10x300nodes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

PROBE = """
() => {
  const zp = document.querySelector('.zoom-pan-container');
  const gc = document.querySelector('.graph-canvas');
  const out = {
    t: Math.round(performance.now()),
    container: !!zp,
    controls: !!(zp && zp._zoomPanControls),
    canvas: !!gc,
    ready: !!(gc && gc.hasAttribute('data-canvas-ready')),
    arbiter: typeof window.HwInputArbiter !== 'undefined',
    nodes: document.querySelectorAll('.node-container > [data-node-id]').length,
    prevented: null,
    sameArbiter: null,
  };
  if (zp) {
    // Would a real wheel here be stopped from reaching browser zoom? A
    // ctrlKey wheel is the one that zooms the PAGE, so it is the honest probe.
    const ev = new WheelEvent('wheel', {
      bubbles: true, cancelable: true, ctrlKey: true, deltaY: 0,
      clientX: 10, clientY: 10,
    });
    const target = document.elementFromPoint(
      zp.getBoundingClientRect().left + 20,
      zp.getBoundingClientRect().top + 20) || zp;
    target.dispatchEvent(ev);
    out.prevented = ev.defaultPrevented;
    out.target = target.className && target.className.toString().slice(0, 40);
  }
  if (out.arbiter && zp) {
    // The registry's own keys settle it: a `__default__` next to a real id
    // means a consumer asked before it knew its container, and is holding an
    // arbiter nothing else will ever touch.
    out.keys = window.HwInputArbiter.keys();
    out.panId = zp.id;
    out.sameArbiter = out.keys.length === 1 && out.keys[0] === zp.id;
    out.gated = window.HwInputArbiter.for(zp.id).isGated();
  }
  return out;
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default=None)
    ap.add_argument("--ticks", type=int, default=60)
    ap.add_argument("--step-ms", type=int, default=250)
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        if args.graph:
            S.open_graph(page, args.graph)

        # How long is the main thread unavailable? `evaluate` runs ON it, so a
        # trivial one cannot return until the thread is free — the wall clock
        # around it IS the block. That block is what a wheel handler is queued
        # behind, and Chrome does not wait for a slow handler before applying
        # its own default (page zoom).
        import time as _time

        t0 = _time.perf_counter()
        page.evaluate("() => 1")
        blocked_ms = (_time.perf_counter() - t0) * 1000
        print(f"main thread unavailable for {blocked_ms:.0f} ms after the page was handed over")

        rows = []
        for _ in range(args.ticks):
            try:
                rows.append(page.evaluate(PROBE))
            except Exception as exc:  # page still navigating
                rows.append({"t": -1, "error": type(exc).__name__})
            page.wait_for_timeout(args.step_ms)

        context.close()
        browser.close()

    print(
        f"{'t(ms)':>7} {'cont':>5} {'ctrls':>6} {'ready':>6} {'arb':>4} "
        f"{'same':>5} {'nodes':>6} {'wheel prevented':>16}"
    )
    last = None
    for r in rows:
        if "error" in r:
            print(f"{r['t']:>7} (page not ready: {r['error']})")
            continue
        key = (
            r["container"],
            r["controls"],
            r["ready"],
            r["arbiter"],
            r["sameArbiter"],
            r["prevented"],
            r["nodes"] > 0,
        )
        if key == last:
            continue  # only print transitions — the gaps are the finding
        last = key
        print(
            f"{r['t']:>7} {str(r['container']):>5} {str(r['controls']):>6} "
            f"{str(r['ready']):>6} {str(r['arbiter']):>4} "
            f"{str(r['sameArbiter']):>5} {r['nodes']:>6} {str(r['prevented']):>16}"
        )

    unprotected = [r for r in rows if r.get("prevented") is False]
    if unprotected:
        print(
            f"\n⚠ wheel NOT prevented in {len(unprotected)} sample(s), "
            f"latest at t={unprotected[-1]['t']}ms — a real wheel there zooms the BROWSER"
        )
    mismatched = [r for r in rows if r.get("sameArbiter") is False]
    if mismatched:
        print(
            f"⚠ more than one arbiter, or the wrong one: keys="
            f"{mismatched[-1].get('keys')!r} pan id={mismatched[-1].get('panId')!r}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
