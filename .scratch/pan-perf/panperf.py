"""Automated pan-perf runs — the RESULTS.md protocol with the human taken out.

    uv run python .scratch/pan-perf/panperf.py --runs 3 --branch perf/whatever

Drives the debug overlay's own recorder (`zoom` then `record`, with auto-pan on)
so the numbers are produced by exactly the instrument RESULTS.md documents, and
reads the finished run objects back out of `window.__hwPerfRuns`. Prints the
markdown rows, a median line, and appends every run to `runs.jsonl`.

Why this exists: RESULTS.md's own "⚠ Hand-panned single runs cannot resolve
anything at this scale" section. Auto-pan fixed the gesture; this fixes the rest
of the protocol — same window size, same zoom, same settle wait, same engine
flags, every time, with no operator in the loop.

Two flags matter for honesty, both off by default:

* `--silence-console` — Playwright keeps CDP's Runtime domain enabled, so
  `console.debug` in a hot path is *serialized* on every call, exactly as if
  devtools were open. That is a real cost the user does not pay with devtools
  closed. Use this flag to no-op console before app scripts run and measure the
  difference; a large gap is itself the finding.
* `--trace` — capture a devtools performance trace for one run, for when the
  question stops being "how slow" and becomes "doing what".
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

RUNS_JSONL = HERE / "runs.jsonl"

#: Injected before any page script when --silence-console is set.
SILENCE_CONSOLE = """
for (const k of ['log', 'debug', 'info', 'warn', 'trace', 'dir', 'group', 'groupEnd']) {
  console[k] = function () {};
}
"""

#: Categories for --trace. Enough to separate main thread, compositor, raster
#: and GPU; deliberately without the JS-stack sampler, which distorts the very
#: frames being measured.
TRACE_CATEGORIES = ",".join(
    [
        "-*",
        "devtools.timeline",
        "disabled-by-default-devtools.timeline",
        "disabled-by-default-devtools.timeline.frame",
        "disabled-by-default-devtools.timeline.invalidationTracking",
        "blink.user_timing",
        "latencyInfo",
        "cc",
        "gpu",
        "viz",
        "benchmark",
        "rail",
        "toplevel",
    ]
)


def wait_for_run(page, before: int, timeout_s: float = 120.0, on_poll=None, poll_ms: int = 250) -> dict:
    """Block until the overlay pushes another finished run, then return it."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if on_poll is not None:
            on_poll()
        count = page.evaluate("() => (window.__hwPerfRuns || []).length")
        if count > before:
            return page.evaluate("() => window.__hwPerfRuns[window.__hwPerfRuns.length - 1]")
        page.wait_for_timeout(poll_ms)
    raise RuntimeError(f"no run finished within {timeout_s}s")


def make_shooter(page, shot_dir: Path, interval: float, run_index: int):
    """A poll callback that screenshots at most every `interval` seconds."""
    shot_dir.mkdir(parents=True, exist_ok=True)
    state = {"n": 0, "last": 0.0}

    def shoot() -> None:
        now = time.time()
        if now - state["last"] < interval:
            return
        state["last"] = now
        state["n"] += 1
        page.screenshot(path=str(shot_dir / f"run{run_index}-{state['n']:02d}.png"))

    return shoot


def make_wheel_panner(page, delta: int):
    """A poll callback that sweeps the canvas with real wheel events.

    NOT an instrument — see the --wheel-pan help. It exists only to produce real
    hover churn, which `setPan` cannot; judge nothing by the fps it yields.
    """
    state = {"n": 0, "dir": 1}

    def sweep() -> None:
        # Small deltas so handleWheel's gesture latch reads a trackpad and pans
        # rather than zooms — the same classification a real swipe gets.
        state["n"] += 1
        if state["n"] % 20 == 0:
            state["dir"] *= -1
        page.mouse.wheel(0, delta * state["dir"])

    return sweep


def start_trace(page):
    cdp = page.context.new_cdp_session(page)
    state = {"chunks": [], "done": False, "stream": None}

    def _complete(event):
        state["stream"] = event.get("stream")
        state["done"] = True

    cdp.on("Tracing.tracingComplete", _complete)
    cdp.send(
        "Tracing.start",
        {
            "categories": TRACE_CATEGORIES,
            "transferMode": "ReturnAsStream",
            "options": "sampling-frequency=10000",
        },
    )
    return cdp, state


def finish_trace(page, cdp, state, path: Path) -> None:
    cdp.send("Tracing.end")
    deadline = time.time() + 60
    while not state["done"] and time.time() < deadline:
        page.wait_for_timeout(200)
    if not state["done"]:
        print("  trace: tracingComplete never arrived — nothing written")
        return

    handle = state["stream"]
    parts: list[str] = []
    while True:
        chunk = cdp.send("IO.read", {"handle": handle, "size": 1 << 20})
        parts.append(chunk.get("data", ""))
        if chunk.get("eof"):
            break
    cdp.send("IO.close", {"handle": handle})
    path.write_text("".join(parts))
    print(f"  trace: {path} ({path.stat().st_size / 1e6:.1f} MB)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--branch", default=None, help="tag for the rows (default: current git branch)")
    ap.add_argument("--engine", default="chrome", choices=["chrome", "chromium", "firefox"])
    ap.add_argument("--window", default="1600,1000")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--silence-console", action="store_true")
    ap.add_argument("--trace", default=None, help="write a devtools trace for the LAST run here")
    ap.add_argument("--note", default="", help="free-text tag stored with every run")
    ap.add_argument("--settle", type=float, default=3.0, help="idle seconds after zoom, before record")
    ap.add_argument("--no-jsonl", action="store_true")
    ap.add_argument(
        "--css",
        action="append",
        default=[],
        help=(
            "CSS injected into the page before the runs (repeatable). The whole point of "
            "the harness: a paint-property hypothesis can be A/B'd in seconds without "
            "editing source, restarting the studio, or reloading the 300-node graph."
        ),
    )
    ap.add_argument("--css-file", default=None, help="same, read from a file")
    ap.add_argument(
        "--shots",
        default=None,
        help=(
            "Capture screenshots mid-pan into this directory, for the 'half the cards "
            "are missing / it flickers' symptom. Screenshots are captured from the "
            "compositor surface, so a card absent from a shot was genuinely not on "
            "screen. NOTE: capturing costs frame time — fps from a --shots run is "
            "diagnostic only and must not be compared against a clean run."
        ),
    )
    ap.add_argument("--shot-interval", type=float, default=0.7)
    ap.add_argument(
        "--zoom",
        type=float,
        default=None,
        help="set this zoom directly instead of clicking the overlay's fixed 0.09 button",
    )
    ap.add_argument(
        "--wheel-pan",
        action="store_true",
        help=(
            "pan with REAL wheel events from the harness instead of the recorder's "
            "setPan sweep. Slower and less precisely controlled, but it is the only "
            "way to reproduce hover churn: setPan fires no pointer events, so the "
            "browser never re-runs hit-testing and the node under a stationary cursor "
            "never changes. Switches the overlay to hand-pan for the run."
        ),
    )
    ap.add_argument("--wheel-delta", type=int, default=30, help="px per wheel event")
    ap.add_argument(
        "--fake-hover",
        default=None,
        metavar="CSS",
        help=(
            "Rotate a class carrying CSS through one node card per frame, to model "
            "hover churn under the CONTROLLED per-frame auto-pan. --wheel-pan can "
            "produce real hover churn but is not an instrument: its wheel events are "
            "driven on a wall clock, so a slow frame gets fewer of them and pan travel "
            "swings 4x between identical runs. This moves exactly one card per frame, "
            "so every engine and every branch is handed the same work. "
            "Example: 'z-index: 1001 !important; outline: 1px solid #4f8ef7;'"
        ),
    )
    ap.add_argument(
        "--hover",
        choices=["node", "empty"],
        default=None,
        help=(
            "park the cursor over a node card (hover highlight active) or over bare "
            "canvas, for the reported 'panning is 3-4x slower while a node is "
            "highlighted'. With `node`, a mousemove is redispatched at the same point "
            "every frame: the auto-pan moves content via setPan, which fires no "
            "pointer events, so without this the browser never re-evaluates :hover "
            "and the effect under test cannot appear."
        ),
    )
    args = ap.parse_args()

    if args.trace and args.engine == "firefox":
        ap.error("--trace is a Chrome DevTools Protocol feature; Firefox cannot produce one")

    branch = args.branch
    if branch is None:
        import subprocess

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(S.REPO),
            capture_output=True,
            text=True,
        ).stdout.strip()

    url = S.ensure_studio()
    print(f"studio {url}   branch {branch}   engine {args.engine}   runs {args.runs}")

    rows: list[str] = []
    runs: list[dict] = []

    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine, window=args.window, headless=args.headless)
        context = browser.new_context(**S.context_kwargs(args.engine, args.window))
        context.add_cookies([S.session_cookie()])
        if args.silence_console:
            context.add_init_script(SILENCE_CONSOLE)
        page = context.new_page()
        page.set_default_timeout(240_000)
        page.goto(url, wait_until="domcontentloaded", timeout=240_000)

        t0 = time.time()
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_overlay(page)
        nodes = S.wait_for_nodes_settled(page)
        print(f"scene ready: {nodes} nodes, {time.time() - t0:.1f}s to settle")

        page.bring_to_front()
        page.evaluate("(b) => { window.__hwPerfBranch = b; }", branch)

        css = list(args.css)
        if args.css_file:
            css.append(Path(args.css_file).read_text())
        if css:
            # After the graph has settled, deliberately: injecting before load
            # would also change how the nodes were laid out and measured, which
            # is a different experiment from "does this property cost frame time".
            page.add_style_tag(content="\n".join(css))
            page.wait_for_timeout(1500)
            print(f"injected {len(css)} css block(s)")

        if args.wheel_pan:
            # The recorder must not also drive the sweep, or the run measures both.
            label = page.evaluate(
                """() => {
                    const o = window.__hwPerfOverlay();
                    for (const b of o.querySelectorAll('.hw-perf-btn'))
                        if (b.textContent.indexOf('auto-pan') !== -1) { b.click(); return 'toggled'; }
                    return 'already hand-pan';
                }"""
            )
            print(f"wheel-pan: overlay {label}")

        scene = S.overlay_scene(page)
        print(
            f"dpr {scene['dpr']}  viewport {scene['viewport']}  "
            f"els {scene['totalEls']}  pins {scene['pins']}"
        )

        for i in range(args.runs):
            print(f"run {i + 1}/{args.runs}")
            if args.zoom is None:
                print("  " + S.click_overlay_button(page, "zoom"))
            else:
                page.evaluate("(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)", args.zoom)
                got = page.evaluate("() => window.__hwPerfCanvas()._zoomPanControls.getZoom()")
                print(f"  zoom {got:.4f} (asked {args.zoom})")
            page.wait_for_timeout(int(args.settle * 1000))

            tracing = None
            if args.trace and i == args.runs - 1:
                tracing = start_trace(page)

            if args.hover:
                spot = page.evaluate(
                    """(mode) => {
                        const canvas = window.__hwPerfCanvas();
                        const r = canvas.getBoundingClientRect();
                        if (mode === 'empty') {
                            // Bare canvas: bottom-right corner is past the content
                            // on this graph, and clear of the HUD and minimap.
                            return { x: r.left + r.width * 0.5, y: r.bottom - 40 };
                        }
                        const host = canvas.querySelector('.node-container');
                        // A card near the middle of the viewport, so the sweep keeps
                        // cards passing under the cursor rather than running out.
                        let best = null, bestD = Infinity;
                        const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
                        for (const el of host.querySelectorAll(':scope > [data-node-id]')) {
                            const b = el.getBoundingClientRect();
                            if (b.width < 2 || b.height < 2) continue;
                            const d = Math.hypot(b.left + b.width / 2 - cx,
                                                 b.top + b.height / 2 - cy);
                            if (d < bestD) { bestD = d; best = b; }
                        }
                        return best
                            ? { x: best.left + best.width / 2, y: best.top + best.height / 2 }
                            : null;
                    }""",
                    args.hover,
                )
                if spot is None:
                    raise SystemExit("--hover node: found no node card to hover")
                page.mouse.move(spot["x"], spot["y"])
                page.wait_for_timeout(500)
                hovered = page.evaluate(
                    "() => !!window.__hwPerfCanvas().querySelector('[data-node-id]:hover')"
                )
                print(f"  hover {args.hover}: node under cursor = {hovered}")
                if args.hover == "node" and not args.wheel_pan:
                    # Keep hover live while setPan moves the content beneath it.
                    # Unnecessary under --wheel-pan: real wheel events make the
                    # browser re-run hit-testing on its own, which is the point.
                    page.evaluate(
                        """([x, y]) => {
                            window.__hwHoverKick && cancelAnimationFrame(window.__hwHoverKick);
                            const tick = () => {
                                document.elementFromPoint(x, y)?.dispatchEvent(
                                    new MouseEvent('mousemove', {
                                        clientX: x, clientY: y, bubbles: true,
                                    }));
                                window.__hwHoverKick = requestAnimationFrame(tick);
                            };
                            tick();
                        }""",
                        [spot["x"], spot["y"]],
                    )

            if args.fake_hover:
                page.evaluate(
                    """([css]) => {
                        if (window.__hwFakeHoverStop) window.__hwFakeHoverStop();
                        let style = document.getElementById('hw-fake-hover-style');
                        if (!style) {
                            style = document.createElement('style');
                            style.id = 'hw-fake-hover-style';
                            document.head.appendChild(style);
                        }
                        style.textContent = '.hw-fake-hover {' + css + '}';
                        const host = window.__hwPerfCanvas().querySelector('.node-container');
                        const cards = Array.from(
                            host.querySelectorAll(':scope > [data-node-id]'));
                        let i = 0, prev = null, raf = null;
                        const tick = () => {
                            if (prev) prev.classList.remove('hw-fake-hover');
                            const el = cards[i % cards.length];
                            el.classList.add('hw-fake-hover');
                            prev = el; i++;
                            raf = requestAnimationFrame(tick);
                        };
                        tick();
                        window.__hwFakeHoverStop = () => {
                            if (raf) cancelAnimationFrame(raf);
                            if (prev) prev.classList.remove('hw-fake-hover');
                            window.__hwFakeHoverStop = null;
                        };
                    }""",
                    [args.fake_hover],
                )

            before = page.evaluate("() => (window.__hwPerfRuns || []).length")
            S.click_overlay_button(page, "record")

            shooter = None
            if args.shots:
                shooter = make_shooter(page, Path(args.shots), args.shot_interval, i + 1)

            if args.wheel_pan:
                shooter = make_wheel_panner(page, args.wheel_delta)

            run = wait_for_run(page, before, on_poll=shooter, poll_ms=8 if args.wheel_pan else 250)
            if args.hover == "node":
                page.evaluate(
                    "() => { if (window.__hwHoverKick) cancelAnimationFrame(window.__hwHoverKick); }"
                )
            if args.fake_hover:
                page.evaluate("() => window.__hwFakeHoverStop && window.__hwFakeHoverStop()")

            if tracing:
                finish_trace(page, tracing[0], tracing[1], Path(args.trace))

            run["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            run["engineChannel"] = args.engine
            run["silencedConsole"] = args.silence_console
            run["headless"] = args.headless
            run["window"] = args.window
            run["dpr"] = scene["dpr"]
            run["note"] = args.note
            run["css"] = css
            runs.append(run)
            rows.append(run["row"])
            print(
                f"  fps {run['fps']}  mean {run['meanFrameMs']}ms  p99 {run['p99FrameMs']}ms  "
                f"main {run['mainMs']}ms  pan {run['panPx']}px  zoom {run['zoom']}  LOD {run['lod']}"
            )

        context.close()
        browser.close()

    print("\n--- rows (paste into RESULTS.md) ---")
    for row in rows:
        print(row)

    if len(runs) > 1:
        med = lambda key: round(statistics.median(r[key] for r in runs), 2)  # noqa: E731
        print(
            f"\nmedian of {len(runs)}: fps {med('fps')}  mean {med('meanFrameMs')}ms  "
            f"p99 {med('p99FrameMs')}ms  main {med('mainMs')}ms  pan {med('panPx')}px"
        )

    if not args.no_jsonl:
        with RUNS_JSONL.open("a") as fh:
            for run in runs:
                fh.write(json.dumps(run) + "\n")
        print(f"appended {len(runs)} run(s) to {RUNS_JSONL}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
