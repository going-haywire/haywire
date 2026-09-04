"""Generate a large graph WITH edges, from the edgeless 300-node perf graph.

Every graph in the perf corpus is either large with 0 edges (10x200nodes,
10x300nodes) or has edges but only 8-9 nodes (loop, webcam). That gap matters
here: `_scheduleEdgeUpdates` fans out 7 full `edgePaths` sweeps per hover
crossing, and on a 0-edge graph every one of those sweeps iterates an empty map.
So the edgeless graphs cannot show what hover churn costs on a real one.

    uv run python .scratch/pan-perf/make_edge_graph.py --per-node 3

Wires spatially-adjacent nodes (sorted by position, not dict order) so edges
stay short and local, the way a hand-built graph looks — chaining dict order
would draw 300 edges across the whole canvas and measure something else.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "graphs" / "10x300nodes.haywire"
OUT = REPO / "graphs" / "10x300nodes-edges.haywire"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument(
        "--per-node",
        type=int,
        default=1,
        help="FLOAT edge pairs per adjacent node pair (0-9); an exec edge is always added",
    )
    ap.add_argument(
        "--max-nodes",
        type=int,
        default=60,
        help=(
            "Keep at most this many nodes. Edges are FAR more expensive to render than "
            "nodes: 300 nodes x 1044 edges never finished loading inside the studio's "
            "connection timeout, while 300 nodes with 0 edges loads in ~5s. Keep this "
            "small until that is understood."
        ),
    )
    args = ap.parse_args()

    doc = json.loads(Path(args.src).read_text())
    nodes = doc["nodes"]

    # Nearest-neighbour chain by position, so each edge connects nodes that sit
    # next to each other on the canvas.
    items = [(nid, n.get("position", [0, 0])) for nid, n in nodes.items()]
    items.sort(key=lambda it: (round(it[1][0] / 400), it[1][1]))
    if args.max_nodes and len(items) > args.max_nodes:
        items = items[: args.max_nodes]
        keep = {nid for nid, _ in items}
        doc["nodes"] = {nid: n for nid, n in nodes.items() if nid in keep}
        nodes = doc["nodes"]

    edges: dict[str, dict] = {}

    def add(src: str, outlet: str, sink: str, inlet: str, flow: str) -> None:
        key = f"{src}[{outlet}]->{sink}[{inlet}]"
        edges[key] = {
            "source_node_id": src,
            "outlet_port_id": outlet,
            "sink_node_id": sink,
            "inlet_port_id": inlet,
            "edge_type": flow,
            "chain_adapter_keys": [],
            "is_lazy": False,
        }

    for (a, pa), (b, pb) in zip(items, items[1:], strict=False):
        # Skip a jump between layout blocks — an edge spanning the whole canvas
        # is not what a real graph looks like and would dominate raster.
        if math.dist(pa, pb) > 2000:
            continue
        add(a, "trigger", b, "exec", "control")
        for k in range(max(0, min(9, args.per_node))):
            add(a, f"float_outlet_{k}", b, f"float_inlet_{k}", "data")

    doc["edges"] = edges
    doc["name"] = "10x300nodes-edges"
    Path(args.out).write_text(json.dumps(doc))
    print(f"{args.out}: {len(nodes)} nodes, {len(edges)} edges")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
