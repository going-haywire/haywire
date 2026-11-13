"""Shared plumbing for the automated pan-perf harness.

Everything here exists so a measurement run needs no human: minting the session
cookie instead of typing a password into /login, waiting for a 300-node graph to
finish arriving over the websocket, and finding the debug overlay's buttons.

Kept separate from `panperf.py` so a one-off probe (screenshot, DOM census,
devtools trace) can reuse the same login + readiness path without duplicating it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDIOCTL = REPO / ".claude" / "skills" / "haywire-live-studio" / "scripts" / "studioctl"
SIDECAR = REPO / ".haywire" / "studio.json"

# The studio's own package is not installed into the harness's interpreter path
# by default; it is a workspace member, so add its src/ rather than depending on
# an editable install being present.
sys.path.insert(0, str(REPO / "packages" / "haywire-studio" / "src"))


def studio_url() -> str:
    """Base URL of the running studio, from the sidecar it writes on startup."""
    if SIDECAR.exists():
        data = json.loads(SIDECAR.read_text())
        url = data.get("url")
        if url:
            return str(url)
    return "http://127.0.0.1:8124"


def ensure_studio(timeout: float = 180.0) -> str:
    """Start the studio if it is down; return its URL.

    `studioctl start` is idempotent and refuses to spawn a second instance, so
    this is safe to call in front of every run — including one where the user
    has their own studio open.
    """
    subprocess.run(
        [sys.executable, str(STUDIOCTL), "start", "--timeout", str(timeout)],
        cwd=str(REPO),
        check=True,
    )
    return studio_url()


def session_cookie(principal: str | None = None) -> dict:
    """Mint a signed session cookie for a Playwright context.

    The gate accepts a cookie or an agent bearer token, but a browser cannot
    attach an Authorization header to its own websocket handshake, so the cookie
    is the only credential that gets a *page* through. Signing one directly
    beats scripting the /login form: no password has to live in this repo, and
    the harness cannot be broken by a change to the form's markup.

    `principal` defaults to the first admin-tier human in the roster.
    """
    from haywire_studio.auth.cookies import COOKIE_NAME, load_or_create_secret, sign_session
    from haywire_studio.security.document import load_document

    roster = load_document().auth
    if principal is None:
        humans = [p for p in roster.principals if p.is_user and p.tier.value == "admin"]
        if not humans:
            raise SystemExit(
                "No admin-tier user in the roster to sign in as. "
                "Add one with `haywire user add <name> --tier admin`."
            )
        principal = humans[0].name

    token = sign_session(principal, secret=load_or_create_secret(), days=1)
    return {
        "name": COOKIE_NAME,
        "value": token,
        "domain": "127.0.0.1",
        "path": "/",
        "httpOnly": True,
        "sameSite": "Lax",
    }


# ── Browser ──────────────────────────────────────────────────────────────────


def launch(playwright, engine: str = "chrome", window: str = "1600,1000", headless: bool = False):
    """Launch a browser configured for honest frame timings.

    Two deliberate choices:

    * **Headed, no Playwright viewport.** `viewport=` drives
      `Emulation.setDeviceMetricsOverride`, which forces a device scale factor
      and can move the page onto a different compositing path than the one the
      user sees. `no_viewport=True` keeps the native window and native DPR —
      and raster cost scales with DPR, so faking it would measure a different
      workload. Headless likewise rasters differently; it is available behind a
      flag for CI, never for a comparison against a hand-observed symptom.
    * **`channel="chrome"` by default**, because the reported symptom is in
      Google Chrome, not in Playwright's bundled Chromium build.
    """
    if engine in ("chrome", "chromium"):
        kwargs = {"headless": headless, "args": [f"--window-size={window}"]}
        if engine == "chrome":
            kwargs["channel"] = "chrome"
        return playwright.chromium.launch(**kwargs)
    if engine == "firefox":
        # Firefox takes no --window-size; its window is sized by the context's
        # viewport instead (see context_kwargs), which Playwright implements as
        # a real window resize rather than a metrics override — so the DPR and
        # compositing path stay native there too.
        return playwright.firefox.launch(headless=headless)
    raise SystemExit(f"unknown engine {engine!r} (chrome | chromium | firefox)")


def context_kwargs(engine: str, window: str) -> dict:
    """How to size the page for `engine`, matching `window` across both."""
    if engine == "firefox":
        width, _, height = window.partition(",")
        return {"viewport": {"width": int(width), "height": int(height)}}
    return {"no_viewport": True}


def open_studio(
    browser,
    url: str,
    principal: str | None = None,
    timeout_ms: int = 240_000,
    engine: str = "chrome",
    window: str = "1600,1000",
    early_css: str | None = None,
):
    """New context + page, authenticated, parked on the studio's canvas.

    `early_css` lands before any page script runs, which matters more than it
    sounds: a rule injected after load cannot reproduce a bug that depends on
    what the compositor did during load. Injecting `will-change` late promotes
    a *fresh* layer, which paints correctly — so the late-injected "control"
    silently shows no bug at all.
    """
    context = browser.new_context(**context_kwargs(engine, window))
    context.add_cookies([session_cookie(principal)])
    if early_css:
        context.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => {}); "
            "(() => { const s = document.createElement('style');"
            f"  s.textContent = {early_css!r};"
            "   (document.head || document.documentElement).appendChild(s); })();"
        )
    page = context.new_page()
    page.set_default_timeout(timeout_ms)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    return context, page


def open_graph(page, name: str, timeout_ms: int = 240_000) -> None:
    """Open a graph by clicking its row in the haystack sidebar.

    Deliberately driven through the UI rather than by repointing
    `.haywire/workspace_state.json`: that file is the developer's restored
    session, and a measurement run has no business rewriting it. The graph must
    be listed in `haystacks/haystack.toml` to appear in the sidebar.
    """
    row = page.locator(f"text={name}").first
    row.wait_for(state="visible", timeout=timeout_ms)
    row.click()
    page.wait_for_timeout(1500)


def wait_for_canvas(page, timeout_ms: int = 240_000) -> None:
    """Block until a zoom-pan canvas exists and its pan controls are attached."""
    page.wait_for_selector(".zoom-pan-container", state="attached", timeout=timeout_ms)
    page.wait_for_function(
        """() => {
            const els = document.querySelectorAll('.zoom-pan-container');
            for (const el of els) if (el._zoomPanControls) return true;
            return false;
        }""",
        timeout=timeout_ms,
    )


def wait_for_nodes_settled(page, quiet_ms: int = 2500, timeout_ms: int = 240_000) -> int:
    """Block until the visible canvas's node count stops changing.

    A 300-node graph arrives over the websocket in batches, and nodes keep
    being measured and re-laid-out after the last one lands. Measuring during
    that is measuring the load, not the pan.
    """
    page.wait_for_function(
        """(quiet) => {
            const el = window.__hwPerfCanvas && window.__hwPerfCanvas();
            if (!el) return false;
            const host = el.querySelector('.node-container');
            if (!host) return false;
            const n = host.querySelectorAll(':scope > [data-node-id]').length;
            const s = window.__hwSettle || (window.__hwSettle = { n: -1, t: 0 });
            const now = performance.now();
            if (n !== s.n) { s.n = n; s.t = now; return false; }
            return n > 0 && (now - s.t) >= quiet;
        }""",
        arg=quiet_ms,
        timeout=timeout_ms,
    )
    return page.evaluate(
        """() => {
            const el = window.__hwPerfCanvas();
            return el.querySelector('.node-container')
                     .querySelectorAll(':scope > [data-node-id]').length;
        }"""
    )


#: Installed into the page so every helper agrees on "the canvas under test" —
#: the studio keeps one canvas per open graph tab, and the hidden ones must
#: never be the thing a run measures.
CANVAS_HELPER = """
window.__hwPerfCanvas = function () {
  const all = document.querySelectorAll('.zoom-pan-container');
  for (const el of all) {
    if (!el._zoomPanControls) continue;
    if (el.getClientRects().length === 0) continue;   // hidden tab
    return el;
  }
  return null;
};
window.__hwPerfOverlay = function () {
  const canvas = window.__hwPerfCanvas();
  if (!canvas) return null;
  // The overlay is a sibling of the canvas inside the editor's frame, not a
  // descendant of it, so walk up until an overlay is in scope.
  let scope = canvas;
  for (let i = 0; i < 6 && scope; i++) {
    const found = scope.querySelector('.debug-overlay');
    if (found && found.getClientRects().length) return found;
    scope = scope.parentElement;
  }
  const any = document.querySelectorAll('.debug-overlay');
  for (const el of any) if (el.getClientRects().length) return el;
  return null;
};
"""


def install_helpers(page) -> None:
    page.evaluate(CANVAS_HELPER)


def wait_for_overlay(page, timeout_ms: int = 20_000) -> None:
    """Wait for the debug HUD, which is the recorder `panperf.py` drives.

    It is settings-gated (`ui.debug_overlay.enabled`), and that setting has been
    observed flipping to false on its own — a bare Playwright timeout here reads
    as "the harness is broken" when the real answer is one boolean, so say so.
    """
    try:
        page.wait_for_function("() => !!window.__hwPerfOverlay()", timeout=timeout_ms)
    except Exception as exc:
        raise SystemExit(
            "The debug overlay never appeared, so there is no recorder to drive.\n"
            "It is gated on ui.debug_overlay.enabled in .haywire/settings.json — "
            "check that it is true, then restart the studio (studioctl restart).\n"
            "Checks that do not need the HUD (paintcheck.py, stacking.py, js.py) "
            "work regardless.\n"
            f"({type(exc).__name__})"
        ) from exc


def overlay_scene(page) -> dict:
    """Whatever the harness can learn about the scene without recording."""
    return page.evaluate(
        """() => {
            const canvas = window.__hwPerfCanvas();
            const overlay = window.__hwPerfOverlay();
            const host = canvas && canvas.querySelector('.node-container');
            return {
                url: location.href,
                dpr: window.devicePixelRatio,
                viewport: [window.innerWidth, window.innerHeight],
                canvases: document.querySelectorAll('.zoom-pan-container').length,
                overlays: document.querySelectorAll('.debug-overlay').length,
                zoom: canvas && canvas._zoomPanControls
                        ? canvas._zoomPanControls.getZoom() : null,
                lod: canvas ? canvas.getAttribute('data-lod-level') : null,
                nodes: host ? host.querySelectorAll(':scope > [data-node-id]').length : 0,
                pins: canvas ? canvas.querySelectorAll('.connection-pin').length : 0,
                totalEls: canvas ? canvas.querySelectorAll('*').length : 0,
                overlayText: overlay ? overlay.textContent.slice(0, 400) : null,
                buttons: overlay
                    ? Array.from(overlay.querySelectorAll('.hw-perf-btn')).map(b => b.textContent)
                    : [],
            };
        }"""
    )


def click_overlay_button(page, needle: str, timeout_ms: int = 30_000) -> str:
    """Click the overlay button whose label contains `needle`; return its label.

    By label rather than index because the bar's contents change — `copy row`
    only appears after a run — so an index silently drifts to another button.
    """
    label = page.evaluate(
        """(needle) => {
            const overlay = window.__hwPerfOverlay();
            if (!overlay) return null;
            for (const b of overlay.querySelectorAll('.hw-perf-btn')) {
                if (b.textContent.indexOf(needle) !== -1) { b.click(); return b.textContent; }
            }
            return null;
        }""",
        needle,
    )
    if label is None:
        raise RuntimeError(f"no overlay button matching {needle!r}")
    return label


def wait_for_settled_idle(page, seconds: float) -> None:
    time.sleep(seconds)
