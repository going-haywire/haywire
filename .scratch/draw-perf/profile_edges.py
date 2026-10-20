"""Profile the browser's edge phase of the 512-node load with the CDP sampling profiler."""
import sys, json, collections
from playwright.sync_api import sync_playwright

graph = "10x512n_5x448e"
out = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    logs = collections.Counter()
    pg.on("console", lambda m: logs.update([m.type]))
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.setSamplingInterval", {"interval": 200})
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.mouse.click(23, 116); pg.wait_for_timeout(1500)
    row = pg.get_by_text(graph, exact=True).first
    row.wait_for(state="visible")
    t0 = pg.evaluate("performance.now()")
    row.click()
    # Wait for all 512 cards, then profile until every edge path has a d.
    pg.wait_for_function("document.querySelectorAll('.graph-canvas .node-container > [data-node-id]').length >= 512", timeout=120000, polling=100)
    t_nodes = pg.evaluate("performance.now()") - t0
    logs_at_nodes = sum(logs.values())
    cdp.send("Profiler.start")
    pg.wait_for_function("""() => { let e=0; for (const p of document.querySelectorAll('.graph-canvas .connection-svg path[data-edge-id]'))
        if(!p.id.endsWith('_hitarea') && (p.getAttribute('d')||'').length>5) e++; return e>=2688; }""", timeout=240000, polling=200)
    t_edges = pg.evaluate("performance.now()") - t0
    prof = cdp.send("Profiler.stop")["profile"]
    # Self time per function from samples.
    nodes = {n["id"]: n for n in prof["nodes"]}
    dt = collections.Counter()
    for sid, delta in zip(prof["samples"], prof["timeDeltas"]):
        cf = nodes[sid]["callFrame"]
        dt[(cf["functionName"] or "(anon)", cf["url"].split("/")[-1], cf["lineNumber"])] += delta / 1000.0
    total = sum(dt.values())
    res = {"nodes_ms": t_nodes, "edges_ms": t_edges, "edge_phase_ms": t_edges - t_nodes,
           "console_during_edges": sum(logs.values()) - logs_at_nodes, "console_types": dict(logs),
           "profiled_ms": total, "top": [[f"{k[0]} {k[1]}:{k[2]}", round(v, 1)] for k, v in dt.most_common(25)]}
    json.dump(res, open(out, "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("nodes_ms", "edges_ms", "edge_phase_ms", "console_during_edges")}))
    b.close()
