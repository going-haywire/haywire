import sys, json, time
from playwright.sync_api import sync_playwright
label, mode, runs, graph, engine = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
TRACK = """
window.__t = {first:null, nodes:null, edges:null, done:null, n:0, e:0};
window.__expect = %d;
setInterval(()=>{
  const c = document.querySelector('.graph-canvas'); if(!c) return;
  const t=window.__t; if(t.done) return;
  const now=performance.now();
  const nn=c.querySelectorAll('.node-container > [data-node-id]').length;
  if(nn>0 && t.first===null) t.first=now;
  if(nn>=window.__expectNodes && t.nodes===null) t.nodes=now;
  let e=0; const ps=c.querySelectorAll('.connection-svg path[data-edge-id]');
  for(const p of ps){ if(!p.id.endsWith('_hitarea') && (p.getAttribute('d')||'').length>5) e++; }
  t.n=nn; t.e=e;
  if(t.nodes!==null && e>=window.__expect){ t.edges=now; t.done=now; }
}, 50);
"""

FIND = """()=>{
 const root=document.querySelector('.graph-canvas'); const app=document.querySelector('#app').__vue_app__;
 let found=null;
 const walk=(vn,d)=>{ if(!vn||found||d>400) return;
   if(vn.component){ const c=vn.component; if(c.proxy && c.proxy._relayoutEdges && c.proxy.$el===root){found=c.proxy;return;} walk(c.subTree,d+1); }
   if(Array.isArray(vn.children)) for(const ch of vn.children) walk(ch,d+1);
   if(vn.suspense) walk(vn.suspense.activeBranch,d+1);
 };
 walk(document.querySelector("#app")._vnode||app._container._vnode,0); window.__cv=found; return !!found; }"""
LOOKUPS = """
window.__L = {gebi:{n:0,t:0}, qs:{n:0,t:0}};
const og = document.getElementById.bind(document);
document.getElementById = function(id){ const t=performance.now(); const r=og(id); const L=window.__L.gebi; L.n++; L.t+=performance.now()-t; return r; };
const oq = Element.prototype.querySelector;
Element.prototype.querySelector = function(s){ if(typeof s==='string' && (s.startsWith('[id=')||s.startsWith('[data-node-id='))){ const t=performance.now(); const r=oq.call(this,s); const L=window.__L.qs; L.n++; L.t+=performance.now()-t; return r;} return oq.call(this,s); };
"""
NODES, EDGES = {"10x512n_5x448e":(512,2688),"10x256n_5x224e":(256,1344)}[graph]
res=[]
import os
gf=None
def gate():
    try: return json.load(open(gf))
    except Exception: return None
prev=gate()
with sync_playwright() as p:
    for r in range(runs):
        b=getattr(p, engine).launch(); pg=b.new_page(viewport={"width":1600,"height":900})
        pg.add_init_script(f"window.__expectNodes={NODES};"+TRACK%EDGES + (LOOKUPS if mode=="lookups" else ""))
        pg.goto("http://127.0.0.1:8191"); pg.wait_for_timeout(5000)
        pg.mouse.click(23,116); pg.wait_for_timeout(1500)
        row=pg.get_by_text(graph, exact=True).first
        row.wait_for(state="visible")
        t0=pg.evaluate("performance.now()")
        row.click()
        try:
            pg.wait_for_function("window.__t.done!==null", timeout=240000, polling=100)
            ok=True
        except Exception as ex:
            ok=False
        t=pg.evaluate("window.__t")
        out={"run":r,"ok":ok,"nodes_ms":(t["nodes"]-t0) if t["nodes"] else None,"edges_ms":(t["edges"]-t0) if t["edges"] else None,"first_ms":(t["first"]-t0) if t["first"] else None,"n":t["n"],"e":t["e"]}
        pg.wait_for_timeout(1500)
        if mode=="lookups":
            out["lookups_total"]=pg.evaluate("window.__L")
            pg.evaluate("window.__L={gebi:{n:0,t:0}, qs:{n:0,t:0}}")
        Bs=[]
        if ok:
            print('found vue', pg.evaluate(FIND))
            for i in range(3):
                Bs.append(pg.evaluate("""()=>{const t=performance.now();window.__cv._relayoutEdges();return performance.now()-t;}"""))
        out["B_ms"]=Bs
        if mode=="lookups": out["lookups_B"]=pg.evaluate("window.__L")
        g=gate()
        if g and prev: out['gate']={'calls':g['calls']-prev['calls'],'ms':round((g['total_s']-prev['total_s'])*1000,2)}
        prev=g
        print(label,json.dumps(out),flush=True)
        res.append(out); b.close()
