"""Time DOM calls during the edge phase of the 512-node load, in firefox or chromium."""
import sys, json
from playwright.sync_api import sync_playwright

engine, out = sys.argv[1], sys.argv[2]
graph = "10x512n_5x448e"
PROBE = """
(() => {
  const S = window.__S = {on: false, calls: {}, firstEdge: null, edgePhase0: null};
  const wrap = (proto, name, label) => {
    const f = proto[name];
    proto[name] = function (...a) {
      if (!S.on) return f.apply(this, a);
      const t = performance.now();
      try { return f.apply(this, a); }
      finally { const c = S.calls[label] || (S.calls[label] = {n: 0, ms: 0}); c.n++; c.ms += performance.now() - t; }
    };
  };
  wrap(Element.prototype, 'querySelector', 'querySelector');
  wrap(Element.prototype, 'querySelectorAll', 'querySelectorAll');
  wrap(Document.prototype, 'getElementById', 'getElementById');
  wrap(Element.prototype, 'getBoundingClientRect', 'getBoundingClientRect');
  wrap(SVGGraphicsElement.prototype, 'getScreenCTM', 'getScreenCTM');
  wrap(Element.prototype, 'setAttribute', 'setAttribute');
  wrap(Node.prototype, 'appendChild', 'appendChild');
  const ow = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {get() {
    if (!S.on) return ow.get.call(this);
    const t = performance.now(); try { return ow.get.call(this); }
    finally { const c = S.calls.offsetWidth || (S.calls.offsetWidth = {n: 0, ms: 0}); c.n++; c.ms += performance.now() - t; } }});
  // Frame gaps: the longest stretch without an animation frame during the edge phase.
  let last = null; S.maxGap = 0;
  const tick = (now) => { if (S.on && last !== null) S.maxGap = Math.max(S.maxGap, now - last); last = now; requestAnimationFrame(tick); };
  requestAnimationFrame(tick);
})();
"""
EDGES_DRAWN = """() => { let e=0; for (const p of document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]'))
  if(!p.id.endsWith('_hitarea') && (p.getAttribute('d')||'').length>5) e++; return e; }"""
with sync_playwright() as p:
    b = getattr(p, engine).launch()
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.add_init_script(PROBE)
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.mouse.click(23, 116); pg.wait_for_timeout(1500)
    row = pg.get_by_text(graph, exact=True).first
    row.wait_for(state="visible")
    t0 = pg.evaluate("performance.now()")
    pg.evaluate("window.__S.on = true"); row.click()
    pg.wait_for_function("document.querySelectorAll('.graph-canvas .node-container > [data-node-id]').length >= 512", timeout=180000, polling=100)
    t_nodes = pg.evaluate("performance.now()") - t0
    pg.evaluate("window.__S.on = true")
    samples = []
    while True:
        n = pg.evaluate(EDGES_DRAWN)
        samples.append([round(pg.evaluate("performance.now()") - t0), n])
        if n >= 2688 or samples[-1][0] > 200000: break
        pg.wait_for_timeout(250)
    t_edges = samples[-1][0]
    S = pg.evaluate("window.__S")
    first = next((t for t, n in samples if n > 0), None)
    res = {"engine": engine, "nodes_ms": round(t_nodes), "first_edge_ms": first, "edges_ms": t_edges,
           "max_frame_gap_ms": round(S["maxGap"]),
           "calls": {k: {"n": v["n"], "ms": round(v["ms"])} for k, v in sorted(S["calls"].items(), key=lambda kv: -kv[1]["ms"])},
           "samples": samples[::4]}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("engine", "nodes_ms", "first_edge_ms", "edges_ms", "max_frame_gap_ms", "calls")}))
    b.close()
