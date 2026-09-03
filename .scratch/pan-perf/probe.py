"""One-shot look at the studio under automation: scene census + screenshot.

Answers "did the harness actually land on the graph under test, with the overlay
up" before any measurement is trusted. Run it whenever a run comes back strange.

    uv run python .scratch/pan-perf/probe.py [--engine chrome] [--shot out.png]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import session as S  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="chrome")
    ap.add_argument("--window", default="1600,1000")
    ap.add_argument("--shot", default=".scratch/pan-perf/probe.png")
    ap.add_argument("--hold", type=float, default=0.0, help="seconds to leave the window open")
    args = ap.parse_args()

    url = S.ensure_studio()
    print(f"studio: {url}")

    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine, window=args.window)
        context, page = S.open_studio(browser, url)

        console: list[str] = []
        page.on("console", lambda m: console.append(f"{m.type}: {m.text[:200]}"))
        page.on("pageerror", lambda e: console.append(f"pageerror: {str(e)[:300]}"))

        t0 = time.time()
        S.wait_for_canvas(page)
        print(f"canvas attached after {time.time() - t0:.1f}s")
        S.install_helpers(page)
        S.wait_for_overlay(page)
        n = S.wait_for_nodes_settled(page)
        print(f"nodes settled at {n} after {time.time() - t0:.1f}s")

        print(json.dumps(S.overlay_scene(page), indent=2))

        # Which graph tabs the studio opened, and which one is on screen.
        tabs = page.evaluate(
            """() => Array.from(document.querySelectorAll('.q-tab, [role="tab"]'))
                        .map(t => t.textContent.trim()).filter(Boolean)"""
        )
        print("tabs:", tabs)

        page.screenshot(path=args.shot)
        print(f"screenshot: {args.shot}")

        if console:
            print("--- console (first 40) ---")
            for line in console[:40]:
                print(" ", line)

        if args.hold:
            time.sleep(args.hold)
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
