"""After the 512-node load: how many NiceGUI elements the page holds, by tag, and their JSON size."""
import json, sys
from playwright.sync_api import sync_playwright
graph = "10x512n_5x448e"
DONE = open("breakdown.py").read().split('DONE = f"""')[1].split('"""')[0].replace("{NODES}", "512").replace("{EDGES}", "2688").replace("{{", "{").replace("}}", "}")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 1600, "height": 900})
    pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
    pg.mouse.click(23, 116); pg.wait_for_timeout(1500)
    row = pg.get_by_text(graph, exact=True).first; row.wait_for(state="visible"); row.click()
    pg.wait_for_function(DONE, timeout=240000, polling=100); pg.wait_for_timeout(2000)
    r = pg.evaluate("""() => {
      const els = document.querySelector("#app")._vnode.component.proxy.elements;
      const ids = Object.keys(els);
      const by = {};
      let total = 0;
      for (const id of ids) { const e = els[id]; const s = JSON.stringify(e).length; total += s;
        const k = e.component ? (e.component.name || e.tag) : e.tag; const b = by[k] || (by[k] = {n:0, bytes:0}); b.n++; b.bytes += s; }
      // one node card's subtree
      const card = document.querySelector('.graph-canvas .node-container > [data-node-id]');
      let cardEls = 0; if (card) cardEls = card.querySelectorAll('[id^="c"]').length + 1;
      const sample = {}; for (const [k, v] of Object.entries(els)) { if (Object.keys(sample).length > 3) break; if (JSON.stringify(v).length > 400) sample[k] = v; }
      return {n: ids.length, bytes: total, cardDomIds: cardEls,
              top: Object.entries(by).sort((a,b)=>b[1].bytes-a[1].bytes).slice(0,20), sample};
    }""")
    print(json.dumps({k: r[k] for k in ("n", "bytes", "cardDomIds", "top")}, indent=0))
    json.dump(r, open("elements.json", "w"), indent=1)
    b.close()
