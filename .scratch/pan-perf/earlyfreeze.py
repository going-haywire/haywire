"""Reproduce "the first pan over a hovered node freezes, then it is fine".

Reported: right after a graph opens, hovering a node and starting a pan freezes
for ~0.5s and the graph jumps; after ~a minute of use the effect is gone.

So: run the SAME short pan twice against one page — once as early as the canvas
allows, once after a settling period — and report the worst main-thread block in
each. Long tasks are attributed by the LongTask observer, and the biggest gap
between animation frames catches blocks the observer misses (style/layout inside
a frame update is not reported as a long task).

    uv run python .scratch/pan-perf/earlyfreeze.py
    uv run python .scratch/pan-perf/earlyfreeze.py --settle 60
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
  window.__ef = { longest: 0, tasks: [], frames: [], last: performance.now() };
  const tick = () => {
    const now = performance.now();
    const gap = now - window.__ef.last;
    window.__ef.last = now;
    if (gap > window.__ef.longest) window.__ef.longest = gap;
    window.__ef.frames.push(Math.round(gap));
    window.__ef.raf = requestAnimationFrame(tick);
  };
  window.__ef.raf = requestAnimationFrame(tick);
  try {
    window.__ef.obs = new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__ef.tasks.push(Math.round(e.duration));
    });
    window.__ef.obs.observe({ entryTypes: ['longtask'] });
  } catch (err) { window.__ef.obsError = String(err); }
}
"""

STOP = """
() => {
  cancelAnimationFrame(window.__ef.raf);
  if (window.__ef.obs) window.__ef.obs.disconnect();
  const f = window.__ef.frames.slice().sort((a, b) => b - a);
  return {
    longestFrameGapMs: Math.round(window.__ef.longest),
    top5FrameGaps: f.slice(0, 5),
    longTasks: window.__ef.tasks.sort((a, b) => b - a).slice(0, 5),
    frames: window.__ef.frames.length,
  };
}
"""

CARD = """
() => {
  const c = window.__hwPerfCanvas();
  if (!c) return null;
  const r = c.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  let best = null, bestD = Infinity;
  for (const el of c.querySelectorAll('.node-container > [data-node-id]')) {
    const b = el.getBoundingClientRect();
    if (b.width < 6 || b.height < 6) continue;
    const d = Math.hypot(b.left + b.width / 2 - cx, b.top + b.height / 2 - cy);
    if (d < bestD) { bestD = d; best = b; }
  }
  return best && { x: best.left + best.width / 2, y: best.top + best.height / 2 };
}
"""


def one_pan(page, label: str) -> None:
    spot = page.evaluate(CARD)
    if not spot:
        print(f"{label}: no card on screen yet")
        return
    page.mouse.move(spot["x"], spot["y"])  # hover a node, as reported
    page.wait_for_timeout(150)
    page.evaluate(INSTALL)
    for i in range(30):
        page.mouse.wheel(0, 40 if (i // 10) % 2 == 0 else -40)
        page.wait_for_timeout(16)
    stats = page.evaluate(STOP)
    print(
        f"{label:>24}: longest frame gap {stats['longestFrameGapMs']:>5} ms | "
        f"top gaps {stats['top5FrameGaps']} | long tasks {stats['longTasks']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--settle", type=float, default=60.0, help="seconds before the second pan")
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        # Deliberately NOT wait_for_nodes_settled: the whole point is to pan
        # while the load is still finishing.
        S.wait_for_canvas(page)
        S.install_helpers(page)
        page.bring_to_front()
        one_pan(page, "EARLY (canvas just up)")

        page.wait_for_timeout(int(args.settle * 1000))
        one_pan(page, f"AFTER {args.settle:.0f}s")

        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
