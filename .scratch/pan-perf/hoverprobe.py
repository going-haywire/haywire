"""Does parking the cursor on a card actually produce `:hover`, and at what zoom?

Sanity check for the other probes: several of them assert on hover counts, and a
count of 0 is ambiguous between "the gate suppressed it" and "the cursor was
never on a card in the first place".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zoom", type=float, default=0.25)
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
                return best && {x: best.left+best.width/2, y: best.top+best.height/2,
                                w: Math.round(best.width), h: Math.round(best.height)};
            }"""
        )
        print(f"target card: {spot}")
        for label, dx in (("move", 0), ("jiggle +1px", 1), ("jiggle -1px", -1)):
            page.mouse.move(spot["x"] + dx, spot["y"] + dx)
            page.wait_for_timeout(500)
            state = page.evaluate(
                """(pt) => {
                    const sh = document.querySelector('[data-hw-gesture-shield]');
                    const el = document.elementFromPoint(pt.x, pt.y);
                    return {
                        hovered: document.querySelectorAll('[data-node-id]:hover').length,
                        shieldPE: sh && sh.style.pointerEvents,
                        under: el ? String(el.className).slice(0, 40) : null,
                        inCard: !!(el && el.closest('[data-node-id]')),
                    };
                }""",
                {"x": spot["x"] + dx, "y": spot["y"] + dx},
            )
            print(
                f"  after {label:>12}: hovered={state['hovered']} "
                f"shieldPE={state['shieldPE']} inCard={state['inCard']} under={state['under']!r}"
            )

        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
