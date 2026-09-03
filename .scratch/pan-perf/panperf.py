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


def wait_for_run(page, before: int, timeout_s: float = 120.0, on_poll=None) -> dict:
    """Block until the overlay pushes another finished run, then return it."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if on_poll is not None:
            on_poll()
        count = page.evaluate("() => (window.__hwPerfRuns || []).length")
        if count > before:
            return page.evaluate("() => window.__hwPerfRuns[window.__hwPerfRuns.length - 1]")
        page.wait_for_timeout(250)
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

            before = page.evaluate("() => (window.__hwPerfRuns || []).length")
            S.click_overlay_button(page, "record")

            shooter = None
            if args.shots:
                shooter = make_shooter(page, Path(args.shots), args.shot_interval, i + 1)

            run = wait_for_run(page, before, on_poll=shooter)

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
