"""Evaluate JS against the settled studio canvas and print the JSON result.

The escape hatch for every "what does the DOM actually look like" question that
comes up mid-investigation, without writing a new script each time. The page is
loaded, authenticated and settled first, and `__hwPerfCanvas()` /
`__hwPerfOverlay()` are installed, so the snippet can get straight to the point.

    uv run python .scratch/pan-perf/js.py '() => __hwPerfCanvas().children.length'
    uv run python .scratch/pan-perf/js.py --file probe.js
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session as S  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("expr", nargs="?", help="a JS arrow function, e.g. '() => document.title'")
    ap.add_argument("--file", default=None)
    ap.add_argument("--css", action="append", default=[], help="inject before evaluating")
    ap.add_argument("--raw", action="store_true", help="print as text, not JSON")
    args = ap.parse_args()

    source = Path(args.file).read_text() if args.file else args.expr
    if not source:
        ap.error("give an expression or --file")

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw)
        context, page = S.open_studio(browser, url)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        S.wait_for_nodes_settled(page)
        if args.css:
            page.add_style_tag(content="\n".join(args.css))
            page.wait_for_timeout(1000)
        result = page.evaluate(source)
        print(result if args.raw else json.dumps(result, indent=2, default=str))
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
