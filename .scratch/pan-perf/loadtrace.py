"""Record a devtools trace of a studio page load, from navigation on.

`panperf.py --trace` traces a pan on a settled page; this traces the load
itself, which is where the multi-second main-thread stalls are
(.insights/project_browser_rendering_cost.md). The JS sampler is on: the
question here is which code runs during a stall, not what a frame costs.

Restore the graph to load as the studio's open tab before running (see that
insight); the page opens whatever the workspace restores.

    uv run python .scratch/pan-perf/loadtrace.py --out /tmp/load.json --seconds 30
    uv run python .scratch/pan-perf/loadtrace_analyze.py /tmp/load.json
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

CATEGORIES = ",".join(
    [
        "-*",
        "devtools.timeline",
        "disabled-by-default-devtools.timeline",
        "v8.execute",
        "disabled-by-default-v8.cpu_profiler",
        "toplevel",
    ]
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=30.0)
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw, engine="chrome")
        context = browser.new_context(**S.context_kwargs("chrome", "1600,1000"))
        context.add_cookies([S.session_cookie()])
        page = context.new_page()
        page.set_default_timeout(240_000)
        cdp = context.new_cdp_session(page)
        state: dict = {"done": False, "stream": None}

        def _complete(event: dict) -> None:
            state["stream"] = event.get("stream")
            state["done"] = True

        cdp.on("Tracing.tracingComplete", _complete)
        cdp.send(
            "Tracing.start",
            {
                "categories": CATEGORIES,
                "transferMode": "ReturnAsStream",
                "options": "sampling-frequency=1000",
            },
        )
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(args.seconds * 1000)
        cdp.send("Tracing.end")
        deadline = time.time() + 120
        while not state["done"] and time.time() < deadline:
            page.wait_for_timeout(200)
        if not state["done"]:
            print("tracingComplete never arrived")
            return 1
        parts: list[str] = []
        while True:
            chunk = cdp.send("IO.read", {"handle": state["stream"], "size": 1 << 20})
            parts.append(chunk.get("data", ""))
            if chunk.get("eof"):
                break
        cdp.send("IO.close", {"handle": state["stream"]})
        Path(args.out).write_text("".join(parts))
        nodes = page.evaluate("() => document.querySelectorAll('[data-node-id]').length")
        print(f"trace: {args.out} ({Path(args.out).stat().st_size / 1e6:.1f} MB), nodes on page: {nodes}")
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
