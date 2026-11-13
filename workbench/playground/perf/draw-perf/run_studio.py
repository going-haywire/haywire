import sys, threading, time, json, os, atexit
STATS = {"calls": 0, "total_s": 0.0, "patched": False}
OUT = os.environ["GATE_OUT"]
def dump():
    open(OUT, "w").write(json.dumps(STATS))
def patcher():
    while True:
        m = sys.modules.get("haybale_graph_editor.editors.graph_canvas.ui_node")
        if m is not None:
            cls = getattr(m, "UINode", None)
            f = getattr(cls, "_apply_write_gates", None) if cls else None
            if f is not None and not getattr(f, "_timed", False):
                def wrap(self, *a, _f=f, **k):
                    t = time.perf_counter()
                    try:
                        return _f(self, *a, **k)
                    finally:
                        STATS["calls"] += 1
                        STATS["total_s"] += time.perf_counter() - t
                wrap._timed = True
                cls._apply_write_gates = wrap
                STATS["patched"] = True
        dump()
        time.sleep(0.05)
threading.Thread(target=patcher, daemon=True).start()
import haywire_studio
sys.argv = ["haywire"]
haywire_studio.main()
