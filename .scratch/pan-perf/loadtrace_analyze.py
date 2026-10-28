"""Attribute the long main-thread tasks in a `loadtrace.py` trace.

Lists every renderer main-thread task over --min-ms, then, over all of them
together: timeline self time by event name, and JS sampler time by function,
both as self time and as time on the stack (inclusive). Inclusive time is what
names the application code a stall runs under; self time names the leaf work.

    uv run python .scratch/pan-perf/loadtrace_analyze.py /tmp/load.json --min-ms 200
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def frame_label(call_frame: dict) -> str:
    fn = call_frame.get("functionName") or "(anonymous)"
    url = call_frame.get("url") or ""
    base = url.rsplit("/", 1)[-1].split("?")[0] if url else ""
    return f"{fn} [{base}:{call_frame.get('lineNumber', -1) + 1}]" if base else fn


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--min-ms", type=float, default=200.0)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--app-only", action="store_true", help="inclusive list without library frames")
    args = ap.parse_args()

    raw = json.loads(Path(args.trace).read_text())
    events = raw["traceEvents"] if isinstance(raw, dict) else raw

    names: dict[tuple, str] = {}
    for e in events:
        if e.get("ph") == "M" and e.get("name") == "thread_name":
            names[(e["pid"], e["tid"])] = e["args"]["name"]

    # The page's main thread is the busiest CrRendererMain.
    busy: dict[tuple, float] = defaultdict(float)
    for e in events:
        key = (e.get("pid"), e.get("tid"))
        if e.get("ph") == "X" and names.get(key) == "CrRendererMain" and e.get("name") == "RunTask":
            busy[key] += e.get("dur", 0)
    if not busy:
        print("no CrRendererMain RunTask events")
        return 1
    main_key = max(busy, key=busy.get)
    t0 = min(e["ts"] for e in events if e.get("ts") and e.get("ph") == "X")

    tasks = sorted(
        (
            e
            for e in events
            if (e.get("pid"), e.get("tid")) == main_key
            and e.get("ph") == "X"
            and e.get("name") == "RunTask"
            and e.get("dur", 0) >= args.min_ms * 1000
        ),
        key=lambda e: e["ts"],
    )
    total_long = sum(e["dur"] for e in tasks) / 1000
    print(
        f"main thread {main_key}: {len(tasks)} tasks >= {args.min_ms:.0f} ms, {total_long:.0f} ms in total"
    )
    for e in tasks:
        print(f"  t={(e['ts'] - t0) / 1e6:7.2f}s  {e['dur'] / 1000:7.0f} ms")
    windows = [(e["ts"], e["ts"] + e["dur"]) for e in tasks]

    def inside(ts: float) -> bool:
        return any(a <= ts < b for a, b in windows)

    # Timeline self time by event name, within the long tasks.
    complete = sorted(
        (
            e
            for e in events
            if (e.get("pid"), e.get("tid")) == main_key
            and e.get("ph") == "X"
            and "dur" in e
            and inside(e["ts"])
        ),
        key=lambda e: (e["ts"], -e["dur"]),
    )
    self_us: dict[str, float] = defaultdict(float)
    stack: list[list] = []
    for e in complete:
        while stack and e["ts"] >= stack[-1][0]["ts"] + stack[-1][0]["dur"]:
            frame = stack.pop()
            self_us[frame[0]["name"]] += frame[1]
        if stack:
            stack[-1][1] -= e["dur"]
        stack.append([e, e["dur"]])
    while stack:
        frame = stack.pop()
        self_us[frame[0]["name"]] += frame[1]
    print("\n=== timeline self time inside long tasks ===")
    for name, us in sorted(self_us.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {us / 1000:8.0f} ms  {name}")

    # JS sampler: Profile + ProfileChunk events on the main thread's process.
    nodes: dict[int, dict] = {}
    samples: list[tuple[float, int]] = []
    start_ts: dict[str, float] = {}
    clock: dict[str, float] = {}
    for e in events:
        if e.get("pid") != main_key[0]:
            continue
        if e.get("name") == "Profile":
            pid_ = e.get("id")
            start_ts[pid_] = e["args"]["data"]["startTime"]
            clock[pid_] = start_ts[pid_]
        elif e.get("name") == "ProfileChunk":
            pid_ = e.get("id")
            data = e["args"]["data"]
            prof = data.get("cpuProfile", {})
            for n in prof.get("nodes", []):
                nodes[n["id"]] = n
            ts = clock.get(pid_, 0.0)
            for sid, delta in zip(prof.get("samples", []), data.get("timeDeltas", []), strict=False):
                ts += delta
                samples.append((ts, sid))
            clock[pid_] = ts
    if not samples:
        print("\nno JS samples in this trace")
        return 0

    intervals = sorted(samples)
    js_self: dict[str, float] = defaultdict(float)
    js_incl: dict[str, float] = defaultdict(float)
    for (ts, sid), nxt in zip(intervals, intervals[1:] + [(intervals[-1][0], 0)], strict=True):
        if not inside(ts):
            continue
        dt = max(0.0, nxt[0] - ts)
        node = nodes.get(sid)
        if node is None:
            continue
        js_self[frame_label(node["callFrame"])] += dt
        seen: set[str] = set()
        cur: dict | None = node
        while cur is not None:
            label = frame_label(cur["callFrame"])
            if label not in seen:
                js_incl[label] += dt
                seen.add(label)
            cur = nodes.get(cur.get("parent")) if cur.get("parent") else None
    # Parent links are given as `children` on the parent; rebuild if absent.
    if not any("parent" in n for n in nodes.values()):
        print("\n(sampler nodes carry no parent links; inclusive time unavailable)")

    print("\n=== JS self time inside long tasks ===")
    for label, us in sorted(js_self.items(), key=lambda kv: -kv[1])[: args.top]:
        print(f"  {us / 1000:8.0f} ms  {label}")
    print("\n=== JS time on the stack (inclusive) inside long tasks ===")
    libs = ("vue.esm", "quasar.", "nicegui.js", "socket.io", "tailwindcss", "(root)", "(program)")

    def is_lib(label: str) -> bool:
        return any(m in label for m in libs) or "[" not in label

    shown = {k: v for k, v in js_incl.items() if not (args.app_only and is_lib(k))}
    for label, us in sorted(shown.items(), key=lambda kv: -kv[1])[: args.top]:
        print(f"  {us / 1000:8.0f} ms  {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
