"""Does a trackpad pan gesture stay a pan, or does it leak into zoom?

`handleWheel` has to tell a mouse wheel (zoom) from a trackpad swipe (pan) from
the wheel event alone. When it gets that wrong mid-gesture the zoom jumps, which
is what this measures: replay realistic gesture traces and report whether zoom
moved when it should not have — and still moved when it should.

    uv run python .scratch/pan-perf/wheelcheck.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session as S  # noqa: E402

#: Each case is (name, expect_zoom_change, [(deltaX, deltaY, ctrlKey), ...]).
#:
#: The trackpad traces ramp up and down the way a real swipe does — a flick
#: reaches 60-80px per event in its middle, which is the part that gets
#: misread as a mouse wheel. deltaX is exactly 0 on a deliberate vertical
#: swipe, so it cannot be relied on to mark the gesture as a trackpad one.
CASES = [
    (
        "trackpad: fast swipe DOWN (pan to bottom)",
        False,
        [(0, d, False) for d in (6, 18, 38, 62, 78, 71, 55, 34, 17, 6)],
    ),
    (
        "trackpad: fast swipe UP (pan to top)",
        False,
        [(0, -d, False) for d in (6, 18, 38, 62, 78, 71, 55, 34, 17, 6)],
    ),
    (
        "trackpad: slow swipe DOWN (never exceeds 50)",
        False,
        [(0, d, False) for d in (4, 9, 14, 19, 22, 20, 15, 9, 4)],
    ),
    (
        "trackpad: diagonal swipe (deltaX non-zero)",
        False,
        [(x, y, False) for x, y in ((3, 8), (9, 24), (17, 47), (22, 63), (18, 51), (9, 26))],
    ),
    (
        "mouse wheel: discrete 120-steps (SHOULD zoom)",
        True,
        [(0, 120, False), (0, 120, False), (0, 120, False)],
    ),
    (
        "pinch: ctrlKey wheel (SHOULD zoom)",
        True,
        [(0, d, True) for d in (4, 9, 14, 9, 4)],
    ),
]

REPLAY = """
async ([events, gapMs]) => {
  const canvas = window.__hwPerfCanvas();
  const rect = canvas.getBoundingClientRect();
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;
  const before = canvas._zoomPanControls.getZoom();
  const panBefore = canvas._zoomPanControls.getPan();
  for (const [dx, dy, ctrl] of events) {
    canvas.dispatchEvent(new WheelEvent('wheel', {
      deltaX: dx, deltaY: dy, deltaMode: 0,
      clientX: cx, clientY: cy,
      ctrlKey: ctrl, bubbles: true, cancelable: true,
    }));
    await new Promise(r => setTimeout(r, gapMs));
  }
  const after = canvas._zoomPanControls.getZoom();
  const panAfter = canvas._zoomPanControls.getPan();
  return {
    before, after,
    panPx: Math.abs(panAfter.x - panBefore.x) + Math.abs(panAfter.y - panBefore.y),
  };
}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="chrome")
    ap.add_argument("--zoom", type=float, default=0.3, help="start zoom (room to move either way)")
    ap.add_argument("--gap-ms", type=int, default=12, help="ms between events within a gesture")
    args = ap.parse_args()

    url = S.ensure_studio()
    failures = 0
    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine)
        context, page = S.open_studio(browser, url, engine=args.engine)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_nodes_settled(page)

        for name, expect_change, events in CASES:
            page.evaluate("(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)", args.zoom)
            page.wait_for_timeout(250)
            result = page.evaluate(REPLAY, [events, args.gap_ms])
            before, after = result["before"], result["after"]
            drift = abs(after - before) / before
            changed = drift > 0.005
            pan_px = result["panPx"]
            # A pan case that neither zoomed NOR moved has not passed — it did
            # nothing, and "did nothing" would satisfy a zoom-only assertion.
            moved_ok = expect_change or pan_px > 20
            ok = (changed == expect_change) and moved_ok
            failures += 0 if ok else 1
            verdict = "ok  " if ok else "FAIL"
            print(
                f"{verdict} {name}\n"
                f"       zoom {before:.4f} → {after:.4f}  ({drift * 100:+.1f}%)  "
                f"pan {pan_px:.0f}px  "
                f"expected {'zoom' if expect_change else 'pan, no zoom'}"
            )

        context.close()
        browser.close()

    print(f"\n{len(CASES) - failures}/{len(CASES)} cases correct")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
