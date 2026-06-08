"""Cost attribution for the 200-node / 2200-widget graph.

Answers "which part of the widget actually costs the time" for
``graphs/10x200nodes.haywire`` (200 PerformanceTester nodes, **0 edges**, 11
NumberWidgets each → 2200 widgets, all unlinked → all rendered).

It renders every node through the *real* SkinFactory under a headless NiceGUI
client and counts three things, mapped to the cost centers from the review
discussion:

  center 1+2  render_widget calls + element constructions
              (build + mount the NumberDrag elements — base-class-independent)
  center 3    outbox.enqueue_update calls during render vs. during a
              simulated value-change pass (the only place SimpleWidget vs
              BaseWidget differs — and it only fires on value churn)

The hypothesis under test: with 0 edges, cost is dominated by centers 1+2
(construction/mounting), and center 3 barely fires because nothing propagates —
so the SimpleWidget-vs-BaseWidget decision is performance-irrelevant here.

This is instrumentation, not a pass/fail gate. It prints a table and asserts
only the structural facts (2200 widgets rendered, 0 edges) so the numbers can't
be silently measuring the wrong graph. Run::

    uv run pytest -m perf tests/ui/widget/test_widget_cost_attribution.py -s
"""

from __future__ import annotations

# editor import first to avoid circular import (see CLAUDE.md / test conventions)
import haywire.core.graph.editor  # noqa: F401

import time
from pathlib import Path

import pytest
from nicegui import ui

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.base import BaseSkin
from haywire.ui.skin.factory import SkinFactory

pytestmark = pytest.mark.perf

_GRAPH = Path(__file__).resolve().parents[3] / "graphs" / "10x200nodes.haywire"


class _Counter:
    """Wraps a bound method, counting calls and (optionally) summing wall-time."""

    def __init__(self, owner, attr: str, *, time_it: bool = False):
        self.owner, self.attr = owner, attr
        self._orig = getattr(owner, attr)
        self.calls = 0
        self.seconds = 0.0
        self.time_it = time_it

    def __enter__(self):
        def wrapper(*a, **k):
            self.calls += 1
            if self.time_it:
                t0 = time.perf_counter()
                try:
                    return self._orig(*a, **k)
                finally:
                    self.seconds += time.perf_counter() - t0
            return self._orig(*a, **k)

        setattr(self.owner, self.attr, wrapper)
        return self

    def __exit__(self, *exc):
        setattr(self.owner, self.attr, self._orig)


def test_widget_cost_attribution(library_system):
    injector = library_system.injector
    skin_factory = injector.get(SkinFactory)

    graph = BaseGraph(graph_id="perf", name="perf", validation_scheduler=SyncScheduler())
    assert _GRAPH.exists(), f"graph fixture missing: {_GRAPH}"
    assert graph.load_from_file(str(_GRAPH)), "graph failed to load"

    wrappers = list(graph.node_wrappers.values())
    assert len(wrappers) == 200, f"expected 200 nodes, got {len(wrappers)}"
    assert len(graph.edge_wrappers) == 0, "fixture is meant to be edge-free (all widgets render)"

    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()

    # Count: every render_widget = one center-1+2 build; enqueue_update = center-3
    # browser sync. We patch the class methods so all 200 renders are captured.
    from nicegui.outbox import Outbox

    render_counter = _Counter(BaseSkin, "render_widget", time_it=True)
    enqueue_counter = _Counter(Outbox, "enqueue_update")

    # --- Phase A: render all 200 cards (centers 1+2, plus any center-3 from
    # initial sync writes during render) ---
    with ui.card():  # a parent slot so node cards have somewhere to mount
        with render_counter, enqueue_counter:
            t0 = time.perf_counter()
            for w in wrappers:
                skin_factory.render(skin_registry_key=skin_key, wrapper=w)
            render_wall = time.perf_counter() - t0

    render_widget_calls = render_counter.calls
    render_widget_seconds = render_counter.seconds
    enqueue_during_render = enqueue_counter.calls

    print(
        "\n--- widget cost attribution: graphs/10x200nodes.haywire ---\n"
        f"  nodes                         : {len(wrappers)}\n"
        f"  edges                         : {len(graph.edge_wrappers)} (all widgets render)\n"
        f"  render_widget calls           : {render_widget_calls}  "
        f"(center 1+2: build+mount elements)\n"
        f"  time inside render_widget     : {render_widget_seconds:.3f}s "
        f"({100 * render_widget_seconds / render_wall:.0f}% of render wall {render_wall:.3f}s)\n"
        f"  enqueue_update during render  : {enqueue_during_render}  "
        f"(center 3 calls — NOTE idempotent per element id: "
        f"self.updates[id]=element overwrites, so this COUNT overstates real cost; "
        f"it collapses to <=1 queued update per element per flush)\n"
        f"  --> per widget                : "
        f"{render_widget_seconds / max(render_widget_calls, 1) * 1e6:.1f}µs build, "
        f"{enqueue_during_render / max(render_widget_calls, 1):.2f} enqueue/widget\n"
    )

    # Structural guards — fail loudly if we measured the wrong thing.
    assert render_widget_calls == 2200, (
        f"expected 2200 widget renders (200 nodes x 11 NumberWidgets), "
        f"got {render_widget_calls} — graph or node shape changed"
    )
