"""Group the 512-node load's websocket messages by kind and by the JS they run, with bytes."""
import sys, json, collections, re, time
from playwright.sync_api import sync_playwright
graph, NODES, EDGES = "10x512n_5x448e", 512, 2688
DONE = open("breakdown.py").read().split('DONE = f"""')[1].split('"""')[0].replace("{NODES}", str(NODES)).replace("{EDGES}", str(EDGES)).replace("{{", "{").replace("}}", "}")
engine = sys.argv[1]
with sync_playwright() as p:
    b = getattr(p, engine).launch(); pg = b.new_page(viewport={"width": 1600, "height": 900})
    frames, on = [], {"v": False}
    pg.on("websocket", lambda ws: ws.on("framereceived", lambda m: on["v"] and frames.append((time.perf_counter(), m))))
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.mouse.click(23, 116); pg.wait_for_timeout(1500)
    row = pg.get_by_text(graph, exact=True).first; row.wait_for(state="visible")
    on["v"] = True; t0 = time.perf_counter(); row.click()
    pg.wait_for_function(DONE, timeout=240000, polling=100); on["v"] = False
    b.close()
kinds = collections.defaultdict(lambda: [0, 0])
js = collections.defaultdict(lambda: [0, 0])
for t, m in frames:
    if not isinstance(m, str): continue
    k = m[:40].split(",")[0]
    kinds[k][0] += 1; kinds[k][1] += len(m)
    if "run_javascript" in m[:30]:
        try:
            body = json.loads(m[2:])[1]
            code = body.get("code", "")
        except Exception:
            code = m[30:200]
        key = re.sub(r"\d+", "N", code[:90])
        js[key][0] += 1; js[key][1] += len(m)
print("kinds:"); [print(" ", v, k) for k, v in sorted(kinds.items(), key=lambda kv: -kv[1][1])]
print("run_javascript by code head:")
for k, v in sorted(js.items(), key=lambda kv: -kv[1][1])[:15]: print(" ", v, repr(k))
