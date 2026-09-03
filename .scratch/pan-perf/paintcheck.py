"""Measure how many on-screen node cards Chrome actually painted.

The framerate cliff and the "nodes don't render completely" symptom are two
different failures, and fps cannot see the second one. This screenshots the
canvas, walks every node card's client rect, and asks whether that rectangle
carries any structure at all.

Method: a painted card has internal contrast — border, title text, coloured
pins — so the pixel extrema across its rect span a wide range. An unpainted
region is the flat canvas background. So `spread = max - min` over the card's
pixels separates them without needing to know the theme's colours.

    uv run python .scratch/pan-perf/paintcheck.py --window 2200,1400
    uv run python .scratch/pan-perf/paintcheck.py --zoom 0.05 --pan
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

#: Below this max-min spread (0-255, greyscale) a card's rect is indistinguishable
#: from flat background. Cards carry white-ish title text on a dark card, so a
#: painted one clears this by a wide margin; the threshold is not delicate.
FLAT_SPREAD = 18


def node_rects(page) -> list[dict]:
    """Every node card's viewport rect, plus whether it is on screen at all."""
    return page.evaluate(
        """() => {
            const canvas = window.__hwPerfCanvas();
            const host = canvas.querySelector('.node-container');
            const canvasRect = canvas.getBoundingClientRect();
            // Anything drawn OVER the canvas hides the cards beneath it, and a
            // flat HUD panel reads exactly like an unpainted card. Collect the
            // occluders so those cards can be excluded rather than counted as
            // paint failures — two cards behind the debug overlay is otherwise
            // a permanent 0.7% false-positive floor.
            const occluders = [];
            for (const sel of ['.debug-overlay', '.minimap-container']) {
                for (const el of document.querySelectorAll(sel)) {
                    const r = el.getBoundingClientRect();
                    if (r.width && r.height) occluders.push(r);
                }
            }
            const hidden = (r) => occluders.some(o =>
                r.right > o.left && r.left < o.right && r.bottom > o.top && r.top < o.bottom);

            const out = [];
            for (const el of host.querySelectorAll(':scope > [data-node-id]')) {
                const r = el.getBoundingClientRect();
                const onScreen =
                    r.right > canvasRect.left && r.left < canvasRect.right &&
                    r.bottom > canvasRect.top && r.top < canvasRect.bottom &&
                    r.width > 0 && r.height > 0 && !hidden(r);
                out.push({
                    id: el.getAttribute('data-node-id'),
                    x: r.left, y: r.top, w: r.width, h: r.height,
                    onScreen,
                });
            }
            return { canvas: canvasRect.toJSON(), nodes: out, dpr: window.devicePixelRatio };
        }"""
    )


def check(shot: Path, data: dict, annotated: Path | None) -> dict:
    img = Image.open(shot).convert("L")
    dpr = data["dpr"]
    painted, blank, offscreen = [], [], []

    for node in data["nodes"]:
        if not node["onScreen"]:
            offscreen.append(node)
            continue
        box = (
            max(0, int(node["x"] * dpr)),
            max(0, int(node["y"] * dpr)),
            min(img.width, int((node["x"] + node["w"]) * dpr)),
            min(img.height, int((node["y"] + node["h"]) * dpr)),
        )
        if box[2] - box[0] < 2 or box[3] - box[1] < 2:
            offscreen.append(node)
            continue
        lo, hi = img.crop(box).getextrema()
        node["spread"] = hi - lo
        (painted if (hi - lo) >= FLAT_SPREAD else blank).append(node)

    if annotated:
        colour = Image.open(shot).convert("RGB")
        draw = ImageDraw.Draw(colour)
        for node in blank:
            draw.rectangle(
                [
                    int(node["x"] * dpr),
                    int(node["y"] * dpr),
                    int((node["x"] + node["w"]) * dpr),
                    int((node["y"] + node["h"]) * dpr),
                ],
                outline=(255, 60, 60),
                width=3,
            )
        colour.save(annotated)

    return {"painted": painted, "blank": blank, "offscreen": offscreen}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", default="1600,1000")
    ap.add_argument("--engine", default="chrome")
    ap.add_argument("--zoom", type=float, default=None, help="set this zoom before checking")
    ap.add_argument(
        "--as-loaded",
        action="store_true",
        help="touch nothing — check the zoom the graph loaded at, without calling setZoom",
    )
    ap.add_argument(
        "--wheel-to",
        type=float,
        default=None,
        help="reach this zoom with real wheel events instead of setZoom",
    )
    ap.add_argument("--pan", action="store_true", help="sweep the canvas, then check mid-motion")
    ap.add_argument("--pan-frames", type=int, default=60)
    ap.add_argument("--settle", type=float, default=3.0)
    ap.add_argument("--css", action="append", default=[], help="inject before checking")
    ap.add_argument("--label", default="", help="printed with the result")
    ap.add_argument("--shot", default=".scratch/pan-perf/paintcheck.png")
    ap.add_argument("--annotate", default=".scratch/pan-perf/paintcheck-annotated.png")
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine, window=args.window)
        context, page = S.open_studio(browser, url, engine=args.engine, window=args.window)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_nodes_settled(page)
        page.bring_to_front()

        if args.css:
            page.add_style_tag(content="\n".join(args.css))
            page.wait_for_timeout(1500)

        # Deliberately independent of the debug overlay: this check is about
        # what the compositor painted, and it must keep working when the HUD is
        # switched off (DebugOverlaySettings.enabled) or absent entirely.
        if args.as_loaded:
            pass  # the whole point: observe the state the graph arrived in
        elif args.wheel_to is not None:
            # Real wheel events, so the zoom goes through the same handler a
            # user's trackpad does — a programmatic setZoom may leave the
            # compositor in a state a genuine gesture never produces.
            box = page.evaluate(
                "() => { const r = window.__hwPerfCanvas().getBoundingClientRect();"
                "        return {x: r.left + r.width / 2, y: r.top + r.height / 2}; }"
            )
            page.mouse.move(box["x"], box["y"])
            for _ in range(200):
                zoom = page.evaluate("() => window.__hwPerfCanvas()._zoomPanControls.getZoom()")
                if abs(zoom - args.wheel_to) / args.wheel_to < 0.03:
                    break
                page.mouse.wheel(0, 60 if zoom > args.wheel_to else -60)
                page.wait_for_timeout(30)
        else:
            page.evaluate(
                "(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)",
                args.zoom if args.zoom is not None else 0.09,
            )
        page.wait_for_timeout(int(args.settle * 1000))

        if args.pan:
            # Drive the same triangle sweep the overlay's recorder uses, at the
            # same 40px/frame, so a paint check and a fps run describe the same
            # motion. Screenshot mid-sweep: that is when the symptom shows.
            page.evaluate(
                """async (frames) => {
                    const c = window.__hwPerfCanvas()._zoomPanControls;
                    const o = c.getPan();
                    let off = 0, dir = 1;
                    for (let i = 0; i < frames; i++) {
                        off += 40 * dir;
                        if (off >= 600) dir = -1;
                        if (off <= -600) dir = 1;
                        c.setPan(o.x + off, o.y + off);
                        await new Promise(requestAnimationFrame);
                    }
                }""",
                args.pan_frames,
            )

        shot = Path(args.shot)
        page.screenshot(path=str(shot))
        data = node_rects(page)
        zoom = page.evaluate("() => window.__hwPerfCanvas()._zoomPanControls.getZoom()")

        result = check(shot, data, Path(args.annotate) if args.annotate else None)
        on = len(result["painted"]) + len(result["blank"])
        print(f"{args.label or '(baseline)'}")
        print(f"window {args.window}  dpr {data['dpr']}  zoom {zoom:.4f}")
        print(f"canvas {data['canvas']['width']:.0f}x{data['canvas']['height']:.0f} css px")
        print(f"nodes on screen: {on}   painted: {len(result['painted'])}   BLANK: {len(result['blank'])}")
        if result["blank"]:
            pct = 100 * len(result["blank"]) / on
            print(f"  → {pct:.1f}% of on-screen cards were not painted")
            print(f"  annotated: {args.annotate}")
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
