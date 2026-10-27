"""Where the 512-node load's time goes, in Chromium: CPU by script and by stack, and the server messages.

usage: breakdown.py <out.json>   (studio on 8191 with the graph in the Haystack, as for measure.py)
"""

import sys, json, collections, time
from playwright.sync_api import sync_playwright

graph, NODES, EDGES = "10x512n_5x448e", 512, 2688
out = sys.argv[1]
DONE = f"""() => {{ const c=document.querySelector('.graph-canvas'); if(!c) return false;
  if (c.querySelectorAll('.node-container > [data-node-id]').length < {NODES}) return false;
  let e=0; for (const p of c.querySelectorAll('.connection-svg path[data-edge-id]'))
    if(!p.id.endsWith('_hitarea') && (p.getAttribute('d')||'').length>5) e++;
  return e >= {EDGES}; }}"""
# Functions whose inclusive time says what kind of work a sample is part of.
MARKERS = (
    "renderRecursively",
    "render",
    "patch",
    "patchElement",
    "patchChildren",
    "patchKeyedChildren",
    "mountElement",
    "mountChildren",
    "flushJobs",
    "_relayoutEdges",
    "handleMessage",
    "onmessage",
    "applyUpdates",
    "update",
    "JSON.parse",
)
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1600, "height": 900})
    frames = []
    state = {"on": False}

    def on_ws(ws):
        ws.on(
            "framereceived",
            lambda payload: state["on"]
            and frames.append(
                (
                    time.perf_counter(),
                    len(payload) if isinstance(payload, (str, bytes)) else 0,
                    payload[:120] if isinstance(payload, str) else "",
                )
            ),
        )

    pg.on("websocket", on_ws)
    cdp = pg.context.new_cdp_session(pg)
    cdp.send("Profiler.enable")
    cdp.send("Profiler.setSamplingInterval", {"interval": 500})
    pg.goto("http://127.0.0.1:8191")
    pg.wait_for_timeout(5000)
    pg.mouse.click(23, 116)
    pg.wait_for_timeout(1500)
    row = pg.get_by_text(graph, exact=True).first
    row.wait_for(state="visible")
    cdp.send("Profiler.start")
    state["on"] = True
    w0 = time.perf_counter()
    row.click()
    pg.wait_for_function(DONE, timeout=240000, polling=100)
    wall = (time.perf_counter() - w0) * 1000
    state["on"] = False
    prof = cdp.send("Profiler.stop")["profile"]

    nodes = {n["id"]: n for n in prof["nodes"]}
    parent = {}
    for n in prof["nodes"]:
        for c in n.get("children", []):
            parent[c] = n["id"]
    by_file = collections.Counter()
    by_fn = collections.Counter()
    inclusive = collections.Counter()
    for sid, delta in zip(prof["samples"], prof["timeDeltas"]):
        ms = delta / 1000.0
        cf = nodes[sid]["callFrame"]
        url = cf["url"].split("/")[-1].split("?")[0] or cf["functionName"]
        by_file[url] += ms
        by_fn[f"{cf['functionName'] or '(anon)'} {url}:{cf['lineNumber']}"] += ms
        seen, cur = set(), sid
        while cur is not None:
            name = nodes[cur]["callFrame"]["functionName"]
            if name in MARKERS and name not in seen:
                seen.add(name)
                inclusive[name] += ms
            cur = parent.get(cur)
    total = sum(by_file.values())
    t_frames = [round((t - w0) * 1000) for t, _, _ in frames]
    per_s = collections.Counter(t // 1000 for t in t_frames)
    kinds = collections.Counter(s.split(",")[0][:60] for _, _, s in frames)
    res = {
        "wall_ms": round(wall),
        "profiled_ms": round(total),
        "by_file_ms": {k: round(v) for k, v in by_file.most_common(15)},
        "inclusive_ms": {k: round(v) for k, v in inclusive.most_common()},
        "top_self_ms": [[k, round(v)] for k, v in by_fn.most_common(30)],
        "ws_frames": len(frames),
        "ws_bytes": sum(n for _, n, _ in frames),
        "ws_frames_per_s": dict(sorted(per_s.items())),
        "ws_first_last_ms": [t_frames[0], t_frames[-1]] if t_frames else None,
        "ws_frame_heads": kinds.most_common(12),
    }
    json.dump(res, open(out, "w"), indent=1)
    print(
        json.dumps(
            {
                k: res[k]
                for k in (
                    "wall_ms",
                    "profiled_ms",
                    "by_file_ms",
                    "inclusive_ms",
                    "ws_frames",
                    "ws_bytes",
                    "ws_first_last_ms",
                )
            },
            indent=1,
        )
    )
    b.close()
