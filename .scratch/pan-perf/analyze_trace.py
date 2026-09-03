"""Summarize a devtools trace captured by `panperf.py --trace`.

Answers the question a fps number cannot: *what* is the main thread doing for
160 ms a frame. Reports per-thread busy time, then self-time by event name on
the renderer main thread, plus the style/layout/paint counters devtools shows
in its summary pie.

    uv run python .scratch/pan-perf/analyze_trace.py .scratch/pan-perf/trace-chrome.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def load(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    return raw["traceEvents"] if isinstance(raw, dict) else raw


def thread_names(events: list[dict]) -> dict[tuple[int, int], str]:
    names: dict[tuple[int, int], str] = {}
    procs: dict[int, str] = {}
    for e in events:
        if e.get("ph") != "M":
            continue
        if e.get("name") == "thread_name":
            names[(e["pid"], e["tid"])] = e["args"]["name"]
        elif e.get("name") == "process_name":
            procs[e["pid"]] = e["args"]["name"]
    return {k: f"{procs.get(k[0], 'pid ' + str(k[0]))} / {v}" for k, v in names.items()}


def self_times(evts: list[dict]) -> tuple[dict[str, float], dict[str, int], float]:
    """Self time and count per event name for one thread's complete events."""
    # Sorted by start, longer first, so a parent is always seen before the
    # children nested inside it — which is what makes the stack walk correct.
    evts = sorted(evts, key=lambda e: (e["ts"], -e.get("dur", 0)))
    self_ms: dict[str, float] = defaultdict(float)
    count: dict[str, int] = defaultdict(int)
    stack: list[dict] = []
    total = 0.0

    def close(frame: dict) -> None:
        self_ms[frame["name"]] += (frame["dur"] - frame["children"]) / 1000.0

    for e in evts:
        ts, dur = e["ts"], e.get("dur", 0)
        while stack and stack[-1]["end"] <= ts:
            close(stack.pop())
        # An event's whole duration counts against its parent's self time; with
        # no parent it is top-level, and only those sum to the thread's busy time.
        if stack:
            stack[-1]["children"] += dur
        else:
            total += dur
        count[e["name"]] += 1
        stack.append({"name": e["name"], "end": ts + dur, "dur": dur, "children": 0.0})
    while stack:
        close(stack.pop())
    return self_ms, count, total / 1000.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--last", type=float, default=0.0, help="only the last N seconds of the trace")
    args = ap.parse_args()

    events = load(Path(args.trace))
    names = thread_names(events)

    complete = [e for e in events if e.get("ph") == "X" and "dur" in e]
    if args.last:
        end = max(e["ts"] + e["dur"] for e in complete)
        cutoff = end - args.last * 1e6
        complete = [e for e in complete if e["ts"] >= cutoff]

    span_us = max(e["ts"] + e["dur"] for e in complete) - min(e["ts"] for e in complete)
    print(f"{len(events)} events, window {span_us / 1e6:.2f}s\n")

    by_thread: dict[tuple[int, int], list[dict]] = defaultdict(list)
    for e in complete:
        by_thread[(e["pid"], e["tid"])].append(e)

    print("=== busy time per thread (top 12) ===")
    busy: list[tuple[float, str, tuple[int, int]]] = []
    for key, evts in by_thread.items():
        _, _, total = self_times(evts)
        busy.append((total, names.get(key, str(key)), key))
    busy.sort(reverse=True)
    for total, name, _ in busy[:12]:
        print(f"{total / 1000:8.2f}s  {100 * total / (span_us / 1000):5.1f}%  {name}")

    # The renderer main thread is the one this investigation is about.
    main_key = None
    for _, name, key in busy:
        if "CrRendererMain" in name:
            main_key = key
            break
    if main_key is None:
        print("\nno CrRendererMain thread in this trace")
        return 0

    self_ms, count, total = self_times(by_thread[main_key])
    print(f"\n=== CrRendererMain self time — {total / 1000:.2f}s busy of {span_us / 1e6:.2f}s ===")
    for name, ms in sorted(self_ms.items(), key=lambda kv: -kv[1])[: args.top]:
        print(f"{ms / 1000:8.3f}s  {100 * ms / total:5.1f}%  x{count[name]:<6d} {name}")

    # devtools' own counters, for the style/layout/paint story.
    print("\n=== rendering counters (CrRendererMain) ===")
    interesting = [
        "UpdateLayoutTree",
        "Layout",
        "PrePaint",
        "Paint",
        "PaintTree",
        "Layerize",
        "UpdateLayer",
        "UpdateLayerTree",
        "CompositeLayers",
        "Commit",
        "ScheduledAction::execute",
        "FunctionCall",
        "TimerFire",
        "EventDispatch",
        "HitTest",
        "ParseHTML",
        "RunMicrotasks",
        "V8.Execute",
    ]
    inclusive: dict[str, float] = defaultdict(float)
    for e in by_thread[main_key]:
        inclusive[e["name"]] += e["dur"] / 1000.0
    for name in interesting:
        if name in count:
            print(f"{inclusive[name] / 1000:8.3f}s incl   x{count[name]:<6d} {name}")

    # Style recalcs carry the element count they touched — the single most
    # useful number when style is the cost.
    styled = 0
    for e in by_thread[main_key]:
        if e["name"] == "UpdateLayoutTree":
            styled += e.get("args", {}).get("elementCount") or 0
    if styled:
        print(f"\nstyle recalc touched {styled} elements total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
