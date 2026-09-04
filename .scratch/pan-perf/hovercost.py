"""How much of a pan-with-hover frame is the JS hover path vs style/paint?

`_scheduleEdgeUpdates` fires on every mouseenter AND mouseleave, and each call
does one immediate `edgePaths` sweep plus 6 more on setTimeout over the next
300ms — 14 sweeps per node entered-and-left, with overlapping tails. That is the
JS cost. Separately, `:hover` changes a card's computed style, which measured
2.2x on its own with no JS involved at all.

This apportions them: drive a real wheel pan with the cursor over cards, trace
it, and compare main-thread self time in the JS buckets (TimerFire,
FunctionCall, EventDispatch) against the style/paint buckets.

Real wheel events are required — `setPan` fires no pointer events, so hit-testing
never re-runs and no crossing ever happens. That makes the pan itself
uncontrolled, so read the SPLIT, never the absolute times.

    uv run python .scratch/pan-perf/hovercost.py --graph 60nodes-edges
    uv run python .scratch/pan-perf/hovercost.py --graph 60nodes-edges --hover empty
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402
from panperf import finish_trace, start_trace  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default=None)
    ap.add_argument("--hover", choices=["node", "empty"], default="node")
    ap.add_argument("--zoom", type=float, default=0.25)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--trace", default=None)
    ap.add_argument(
        "--select",
        action="store_true",
        help="click a node first, so the resize gadget is visible (node 'selected')",
    )
    ap.add_argument(
        "--jiggle",
        type=int,
        default=0,
        help="px of cursor movement per step, so cards actually cross under it",
    )
    args = ap.parse_args()

    trace_path = Path(args.trace) if args.trace else None
    url = S.ensure_studio()

    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        S.wait_for_canvas(page)
        if args.graph:
            S.open_graph(page, args.graph)
            S.wait_for_canvas(page)
        S.install_helpers(page)
        n = S.wait_for_nodes_settled(page)
        page.bring_to_front()
        page.evaluate("(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)", args.zoom)
        page.wait_for_timeout(1500)

        edges = page.evaluate("() => window.__hwPerfCanvas().querySelectorAll('svg path').length")
        print(f"graph: {n} nodes, {edges} svg paths, zoom {args.zoom}")

        spot = page.evaluate(
            """(mode) => {
                const c = window.__hwPerfCanvas();
                const r = c.getBoundingClientRect();
                if (mode === 'empty') return { x: r.left + 30, y: r.bottom - 30 };
                const cx = r.left + r.width/2, cy = r.top + r.height/2;
                let best = null, bestD = Infinity;
                for (const el of c.querySelectorAll('.node-container > [data-node-id]')) {
                    const b = el.getBoundingClientRect();
                    if (b.width < 3 || b.height < 3) continue;
                    const d = Math.hypot(b.left+b.width/2-cx, b.top+b.height/2-cy);
                    if (d < bestD) { bestD = d; best = b; }
                }
                return best && { x: best.left+best.width/2, y: best.top+best.height/2 };
            }""",
            args.hover,
        )
        if args.select:
            page.mouse.click(spot["x"], spot["y"])
            page.wait_for_timeout(800)
            vis = page.evaluate("() => document.querySelectorAll('.hw-resize-grip').length")
            print(f"selected a node: {vis} resize grips visible")
        page.mouse.move(spot["x"], spot["y"])
        page.wait_for_timeout(400)

        # Count crossings, timer fan-out, and _scheduleEdgeUpdates calls over the
        # same window. The call count is the number that matters here: it is
        # deterministic, unlike fps under a wheel-driven pan, and each call
        # schedules 7 full edgePaths sweeps across the next 300ms.
        page.evaluate(
            """() => {
                window.__hwX = { enter: 0, leave: 0, timers: 0, edgeUpdates: 0, efp: 0 };
                const efp = document.elementFromPoint.bind(document);
                document.elementFromPoint = function (...a) {
                    window.__hwX.efp++; return efp(...a);
                };
                const dbg = console.debug.bind(console);
                window.__hwOrigDebug = console.debug;
                console.debug = function (...a) {
                    if (typeof a[0] === 'string' && a[0].indexOf('_scheduleEdgeUpdates') !== -1)
                        window.__hwX.edgeUpdates++;
                    return dbg(...a);
                };
                const c = window.__hwPerfCanvas();
                c.addEventListener('mouseover', (e) => {
                    if (e.target.closest && e.target.closest('[data-node-id]')) window.__hwX.enter++;
                }, true);
                c.addEventListener('mouseout', (e) => {
                    if (e.target.closest && e.target.closest('[data-node-id]')) window.__hwX.leave++;
                }, true);
                const orig = window.setTimeout;
                window.__hwOrigTimeout = orig;
                window.setTimeout = function (...a) { window.__hwX.timers++; return orig.apply(this, a); };
            }"""
        )

        pan0 = page.evaluate("() => window.__hwPerfCanvas()._zoomPanControls.getPan()")
        cdp = state = None
        if args.trace:
            cdp, state = start_trace(page)
        steps = int(args.seconds * 1000 / 16)
        for i in range(steps):
            page.mouse.wheel(0, 40 if (i // 12) % 2 == 0 else -40)
            if args.jiggle:
                # The missing ingredient. A stationary cursor over a moving
                # canvas produces NO crossings — a JS transform does not make the
                # browser re-run hover. Real panning is done with a hand on the
                # trackpad and a cursor that drifts, so cards cross under it.
                # Panning and hovering are each smooth alone; the reported
                # jerkiness is the combination, which needs both here too.
                page.mouse.move(
                    spot["x"] + args.jiggle * (1 if (i // 3) % 2 == 0 else -1),
                    spot["y"] + args.jiggle * (1 if (i // 5) % 2 == 0 else -1),
                )
            page.wait_for_timeout(16)
        if cdp:
            finish_trace(page, cdp, state, trace_path)
        pan1 = page.evaluate("() => window.__hwPerfCanvas()._zoomPanControls.getPan()")
        print(f"pan moved dx={pan1['x'] - pan0['x']:.0f} dy={pan1['y'] - pan0['y']:.0f} css px")

        counts = page.evaluate("() => { window.setTimeout = window.__hwOrigTimeout; return window.__hwX; }")
        print(
            f"over {args.seconds}s: {counts['enter']} enters, {counts['leave']} leaves, "
            f"{counts['edgeUpdates']} _scheduleEdgeUpdates calls "
            f"(= {counts['edgeUpdates'] * 7} edgePaths sweeps), "
            f"{counts['timers']} setTimeout calls, "
            f"{counts['efp']} elementFromPoint (forced layout)"
        )
        context.close()
        browser.close()

    print(f"\nnow: uv run python .scratch/pan-perf/analyze_trace.py {trace_path} --last {args.seconds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
