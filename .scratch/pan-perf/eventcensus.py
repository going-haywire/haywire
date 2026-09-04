"""WHICH mouse callbacks fire during a pan, and how many times.

The pan-hover symptom has been sized (RESULTS.md: ~2.2x) but never attributed.
This counts every consumer that can fire on a hover crossing, under an identical
wheel pan run twice — cursor parked ON a card, then over EMPTY canvas. The
control matters: only the difference between the two columns is hover work.

Counted, all as capture-phase listeners on document so nothing is missed:

  mouseover/mouseenter   browser hit-test churn, split by card vs pin
  transitionstart        `.connection-pin` has `transition: all .2s`, so a pin
                         hover animates `transform` — and transitionstart
                         BUBBLES to the card's own listener in canvas.vue,
                         which cannot tell it apart from the magnifier's and
                         calls _scheduleEdgeUpdates (7 edge sweeps) for it
  _scheduleEdgeUpdates   patched on the Vue instance — the real count, not a proxy
  ws send                pin_render.py attaches SERVER-side mouseenter/mouseleave
                         to every pin, so each crossing is a websocket round trip

Read the counts per second of pan, not the absolutes: the wheel stream is
wall-clock driven, so a slow frame gets fewer events (RESULTS.md, retracted A/B).

    uv run python .scratch/pan-perf/eventcensus.py
    uv run python .scratch/pan-perf/eventcensus.py --zoom 0.09 --graph 10x300nodes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import session as S  # noqa: E402

INSTALL = """
() => {
  const c = window.__hwPerfCanvas();
  const canvasEl = c.querySelector('.graph-canvas');
  const R = window.__hwCensus = {
    mousemove: 0, mouseover: 0, mouseout: 0,
    enterCard: 0, enterPin: 0, leaveCard: 0, leavePin: 0,
    transStart: 0, transStartTransform: 0, transStartFromPin: 0,
    schedEdge: 0, schedEdgePatched: false,
    wsSend: 0, wsSendHover: 0, wsBytes: 0,
    frames: 0,
  };
  const isPin = (t) => t && t.classList && t.classList.contains('connection-pin');
  const isCard = (t) => t && t.classList && t.classList.contains('zoom-pan-lod0') && !isPin(t);

  R._l = [];
  const on = (type, fn) => { document.addEventListener(type, fn, true); R._l.push([type, fn]); };
  on('mousemove', () => R.mousemove++);
  on('mouseover', () => R.mouseover++);
  on('mouseout',  () => R.mouseout++);
  on('mouseenter', (e) => { if (isPin(e.target)) R.enterPin++; else if (isCard(e.target)) R.enterCard++; });
  on('mouseleave', (e) => { if (isPin(e.target)) R.leavePin++; else if (isCard(e.target)) R.leaveCard++; });
  const sig = (el) => {
    if (!el || !el.tagName) return '?';
    const cls = (el.className && el.className.baseVal !== undefined)
        ? el.className.baseVal : (el.className || '');
    return el.tagName.toLowerCase() + '.' + String(cls).split(/\\s+/).slice(0, 3).join('.');
  };
  const bump = (bag, key) => { bag[key] = (bag[key] || 0) + 1; };
  R.byProp = {}; R.byTransTarget = {}; R.byOverTarget = {};
  on('mouseover', (e) => bump(R.byOverTarget, sig(e.target)));
  on('transitionstart', (e) => {
    R.transStart++;
    bump(R.byProp, e.propertyName);
    bump(R.byTransTarget, sig(e.target));
    if (e.propertyName !== 'transform') return;
    R.transStartTransform++;
    // Does it reach a card listener? canvas.vue listens on the card element and
    // filters only on propertyName, so any transform transition below a card
    // counts as a _scheduleEdgeUpdates trigger.
    if (isPin(e.target) && e.target.closest('.node-container > [data-node-id]')) R.transStartFromPin++;
  });

  // The real _scheduleEdgeUpdates count, straight off the component instance.
  const inst = canvasEl && canvasEl.__vueParentComponent;
  const proxy = inst && inst.proxy;
  if (proxy && typeof proxy._scheduleEdgeUpdates === 'function') {
    const orig = proxy._scheduleEdgeUpdates.bind(proxy);
    proxy._scheduleEdgeUpdates = function (...a) { R.schedEdge++; return orig(...a); };
    R.schedEdgePatched = true;
    R._unpatchSched = () => { delete proxy._scheduleEdgeUpdates; };
  }

  // Websocket traffic. Patching the prototype catches the live socket too.
  if (!window.__hwWsPatched) {
    window.__hwWsPatched = true;
    const orig = WebSocket.prototype.send;
    WebSocket.prototype.send = function (data) {
      const R2 = window.__hwCensus;
      if (R2 && window.__hwCensusOn) {
        R2.wsSend++;
        if (typeof data === 'string') {
          R2.wsBytes += data.length;
          if (data.includes('mouseenter') || data.includes('mouseleave')) R2.wsSendHover++;
        }
      }
      return orig.call(this, data);
    };
  }

  // Frames, and the pan PATH length — a scenario whose content never moved is
  // not measuring a pan (RESULTS.md §5).
  R.panPath = 0;
  const ctl = c._zoomPanControls;
  let last = ctl.getPan();
  const tick = () => {
    R.frames++;
    const p = ctl.getPan();
    R.panPath += Math.abs(p.x - last.x) + Math.abs(p.y - last.y);
    last = p;
    R._raf = requestAnimationFrame(tick);
  };
  R._raf = requestAnimationFrame(tick);
  window.__hwCensusOn = true;
  R.t0 = performance.now();
  return R.schedEdgePatched;
}
"""

STOP = """
() => {
  const R = window.__hwCensus;
  window.__hwCensusOn = false;
  cancelAnimationFrame(R._raf);
  for (const [t, fn] of R._l) document.removeEventListener(t, fn, true);
  if (R._unpatchSched) R._unpatchSched();
  const out = Object.assign({}, R);
  delete out._l; delete out._unpatchSched;
  out.seconds = (performance.now() - R.t0) / 1000;
  return out;
}
"""

SPOT = """
(mode) => {
  const c = window.__hwPerfCanvas();
  const r = c.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const cards = [...c.querySelectorAll('.node-container > [data-node-id]')]
      .map(el => el.getBoundingClientRect())
      .filter(b => b.width > 3 && b.height > 3 && b.left > r.left && b.right < r.right
                                && b.top > r.top && b.bottom < r.bottom);
  if (mode === 'node') {
    let best = null, bestD = Infinity;
    for (const b of cards) {
      const d = Math.hypot(b.left + b.width/2 - cx, b.top + b.height/2 - cy);
      if (d < bestD) { bestD = d; best = b; }
    }
    return best && { x: best.left + best.width/2, y: best.top + best.height/2, cards: cards.length };
  }
  if (mode === 'pin') {
    // A pin whose centre actually hit-tests to itself — a pin buried under a
    // sibling would open no wire and the run would silently measure nothing.
    let best = null, bestD = Infinity;
    for (const p of c.querySelectorAll('.connection-pin')) {
      if (p.dataset.pinFlowType === 'ghost') continue;
      const b = p.getBoundingClientRect();
      if (b.width < 2 || b.left < r.left || b.right > r.right) continue;
      if (b.top < r.top || b.bottom > r.bottom) continue;
      const x = b.left + b.width / 2, y = b.top + b.height / 2;
      const hit = document.elementFromPoint(x, y);
      if (!hit || !hit.closest('.connection-pin')) continue;
      const d = Math.hypot(x - cx, y - cy);
      if (d < bestD) { bestD = d; best = { x, y }; }
    }
    return best && { x: best.x, y: best.y, cards: cards.length };
  }
  // 'empty': a point in the canvas that no card covers
  for (let dy = 0; dy < r.height / 2 - 20; dy += 17) {
    for (let dx = 0; dx < r.width / 2 - 20; dx += 23) {
      const x = cx + dx, y = cy + dy;
      const hit = document.elementFromPoint(x, y);
      if (hit && !hit.closest('[data-node-id]')) return { x, y, cards: cards.length };
    }
  }
  return null;
}
"""


#: The candidate gate, and what it costs to engage. `pointer-events` is
#: INHERITED, so writing it on the node layer invalidates every descendant's
#: computed value — the reason to time the flush rather than assume it is free.
#: NOT settable on the node layer alone: `[data-node-id] { pointer-events: auto }`
#: (canvas.vue) re-enables it per card, and `.connection-pin` uses `!important`,
#: so inheritance from an ancestor is overridden. The gate has to out-specify
#: both, which means a rule keyed on an attribute, not an inline style.
GATE = """
(on) => {
  const canvas = window.__hwPerfCanvas().querySelector('.graph-canvas');
  if (!window.__hwGateStyle) {
    const s = document.createElement('style');
    // Has to be the universal selector: pointer-events is re-enabled
    // explicitly at FIVE layers below the canvas — [data-node-id] and
    // .connection-pin (canvas.vue), and .q-card / [data-port-name] /
    // .clickable / [data-interactive] / .no-pan (pan.vue) — so nothing
    // narrower survives the cascade.
    s.textContent = `
      [data-hw-gesture] .node-container,
      [data-hw-gesture] .node-container * { pointer-events: none !important; }`;
    document.head.appendChild(s);
    window.__hwGateStyle = s;
  }
  const t0 = performance.now();
  if (on) canvas.setAttribute('data-hw-gesture', '');
  else canvas.removeAttribute('data-hw-gesture');
  document.elementFromPoint(10, 10);      // force style + layout to flush now
  return performance.now() - t0;
}
"""


#: The other candidate: one transparent element on top, so the topmost hit-test
#: result under the cursor is never a card. O(1) — it changes no card's style.
SHIELD = """
(on) => {
  let el = window.__hwShield;
  const t0 = performance.now();
  if (on) {
    if (!el) {
      el = document.createElement('div');
      el.id = 'hw-gesture-shield';
      // Inside the zoom-pan container (position: relative), NOT on body: a
      // shield over the whole viewport also swallows the wheel events that
      // drive the pan, and the run then measures a canvas that never moved.
      el.style.cssText = 'position:absolute;inset:0;z-index:2147483000;background:transparent';
      window.__hwShield = el;
    }
    window.__hwPerfCanvas().appendChild(el);
  } else if (el && el.parentNode) {
    el.remove();
  }
  document.elementFromPoint(10, 10);      // force style + layout to flush now
  return performance.now() - t0;
}
"""


def run(
    page,
    spot,
    ticks: int,
    step_ms: int,
    *,
    pan: bool,
    jiggle: int,
    gate: bool = False,
    shield: bool = False,
    wire: tuple | None = None,
) -> dict:
    """One scenario: `ticks` steps of optional wheel-pan and optional cursor jiggle.

    The jiggle is what makes cards cross under the cursor — a transform pan does
    NOT re-run hit-testing in Chrome (measured: 0 mouseover over a 480px wheel
    pan with the cursor parked on a card), so a hover-churn scenario needs the
    pointer to move for real.
    """
    if wire:
        # Open a live edge-drag BEFORE counting: one mousedown on a pin puts the
        # canvas in `active` mode, which is modal — it stays open across
        # everything below, exactly as it does for a user.
        page.mouse.move(wire["x"], wire["y"])
        page.wait_for_timeout(200)
        page.mouse.down()
        page.mouse.up()
        page.wait_for_timeout(300)
        opened = page.evaluate(
            "() => !![...document.querySelectorAll('#connection-svg path')]"
            ".find(p => p.getAttribute('stroke-dasharray'))"
        )
        if not opened:
            raise SystemExit("clicking the pin did not open a preview path — no wire to measure")
    page.mouse.move(spot["x"], spot["y"])
    page.wait_for_timeout(400)
    page.evaluate(INSTALL)
    gate_on_ms = page.evaluate(GATE, True) if gate else 0.0
    if shield:
        gate_on_ms = page.evaluate(SHIELD, True)
    for i in range(ticks):
        if pan:
            page.mouse.wheel(0, 40 if (i // 12) % 2 == 0 else -40)
        if jiggle:
            page.mouse.move(
                spot["x"] + (jiggle if i % 2 else -jiggle),
                spot["y"] + (jiggle if (i // 2) % 2 else -jiggle),
            )
        page.wait_for_timeout(step_ms)
    page.wait_for_timeout(400)  # let the 200ms pin transitions and tails land
    out = page.evaluate(STOP)
    out["gateOnMs"] = gate_on_ms
    out["gateOffMs"] = page.evaluate(GATE, False) if gate else 0.0
    if shield:
        out["gateOffMs"] = page.evaluate(SHIELD, False)
    out["magnified"] = page.evaluate(
        "() => document.querySelectorAll('.zoom-pan-lod0').length && "
        "[...document.querySelectorAll('.zoom-pan-lod0')].filter(e => e._magnified).length"
    )
    if wire:
        page.keyboard.press("Escape")  # back to idle, or the next run inherits the mode
        page.wait_for_timeout(300)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--graph", default=None, help="open this graph first (haystack row text)")
    ap.add_argument("--zoom", type=float, default=0.25)
    ap.add_argument("--ticks", type=int, default=72)
    ap.add_argument("--step-ms", type=int, default=16)
    ap.add_argument("--jiggle", type=int, default=6, help="px of cursor movement per step")
    ap.add_argument("--engine", default="chrome")
    args = ap.parse_args()

    url = S.ensure_studio()
    with sync_playwright() as pw:
        browser = S.launch(pw, engine=args.engine)
        context, page = S.open_studio(browser, url, engine=args.engine)
        S.wait_for_canvas(page)
        S.install_helpers(page)
        if args.graph:
            S.open_graph(page, args.graph)
            S.wait_for_canvas(page)
            S.install_helpers(page)
        n = S.wait_for_nodes_settled(page)
        page.bring_to_front()
        page.evaluate("(z) => window.__hwPerfCanvas()._zoomPanControls.setZoom(z)", args.zoom)
        page.wait_for_timeout(1500)
        print(f"{n} nodes, zoom {args.zoom}")

        # (label, spot mode, wheel-pan?, jiggle px, css gate?, shield?, open a wire?)
        scenarios = [
            ("pan, cursor off cards", "empty", True, 0, False, False, False),
            ("pan, cursor RESTING on a card", "node", True, 0, False, False, False),
            ("pan + cursor MOVING over cards", "node", True, args.jiggle, False, False, False),
            ("cursor MOVING over cards, no pan", "node", False, args.jiggle, False, False, False),
            ("pan + cursor MOVING, css GATE", "node", True, args.jiggle, True, False, False),
            ("pan + cursor MOVING, SHIELD", "node", True, args.jiggle, False, True, False),
            ("pan, RESTING on a card, SHIELD", "node", True, 0, False, True, False),
            # The modal edge drag: same input, but with a wire open the whole time.
            ("WIRE open, cursor MOVING, no pan", "node", False, args.jiggle, False, False, True),
            ("WIRE open + pan + cursor MOVING", "node", True, args.jiggle, False, False, True),
        ]
        results = []
        wire_spot = None
        for label, mode, pan, jiggle, gate, shield, wire in scenarios:
            spot = page.evaluate(SPOT, mode)
            if not spot:
                raise SystemExit(f"no {mode!r} spot found on screen")
            if wire and wire_spot is None:
                wire_spot = page.evaluate(SPOT, "pin")
                if not wire_spot:
                    raise SystemExit("no hit-testable pin on screen — raise --zoom")
            print(
                f"  {label}: cursor at ({spot['x']:.0f}, {spot['y']:.0f}), "
                f"{spot['cards']} cards fully on screen"
            )
            results.append(
                (
                    label,
                    run(
                        page,
                        spot,
                        args.ticks,
                        args.step_ms,
                        pan=pan,
                        jiggle=jiggle,
                        gate=gate,
                        shield=shield,
                        wire=wire_spot if wire else None,
                    ),
                )
            )

        context.close()
        browser.close()

    keys = [
        ("mousemove", "mousemove (document)"),
        ("mouseover", "mouseover"),
        ("enterCard", "mouseenter on a card"),
        ("leaveCard", "mouseleave on a card"),
        ("enterPin", "mouseenter on a PIN (server round trip)"),
        ("leavePin", "mouseleave on a PIN (server round trip)"),
        ("transStart", "transitionstart (any property)"),
        ("transStartTransform", "  ... propertyName=transform"),
        ("transStartFromPin", "  ... from a pin, reaching the card listener"),
        ("schedEdge", "_scheduleEdgeUpdates calls (x7 sweeps each)"),
        ("wsSend", "websocket sends"),
        ("wsSendHover", "  ... carrying mouseenter/mouseleave"),
        ("frames", "rAF frames"),
    ]
    keys += [
        ("magnified", "cards left magnified at the end"),
    ]
    cols = [r for _, r in results]
    print(f"\npatched _scheduleEdgeUpdates: {cols[0]['schedEdgePatched']}")
    head = "".join(f"{i + 1:>10}" for i in range(len(cols)))
    for i, (label, _) in enumerate(results):
        print(f"  {i + 1}. {label}")
    print(f"\n{'':46}{head}")
    for k, label in keys:
        print(f"{label:46}" + "".join(f"{c.get(k, 0):>10}" for c in cols))
    print(f"{'seconds':46}" + "".join(f"{c['seconds']:>10.2f}" for c in cols))
    print(f"{'pan path px':46}" + "".join(f"{c['panPath']:>10.0f}" for c in cols))
    print(f"{'fps':46}" + "".join(f"{c['frames'] / c['seconds']:>10.1f}" for c in cols))
    print(
        f"{'gate engage / release ms':46}"
        + "".join(f"{c['gateOnMs']:>4.0f}/{c['gateOffMs']:<5.0f}" for c in cols)
    )

    def top(bag: dict, n: int = 8) -> str:
        items = sorted(bag.items(), key=lambda kv: -kv[1])[:n]
        return ", ".join(f"{k}={v}" for k, v in items) or "-"

    for i, (label, c) in enumerate(results):
        print(f"\n{i + 1}. {label}")
        print(f"   transition properties: {top(c['byProp'])}")
        print(f"   transition targets:    {top(c['byTransTarget'])}")
        print(f"   mouseover targets:     {top(c['byOverTarget'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
