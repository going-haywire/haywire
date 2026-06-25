"""Profile the skin render path — attribute the "87% non-widget" node-card cost.

The widget cost-attribution test (``test_widget_cost_attribution.py``) showed
``render_widget`` is only ~13% of render wall time; the other ~87% is the rest
of the node card built by the default skin (``DefaultNodeSkin`` /
``NodeSkin.render_port`` / ``_render_pin`` / tooltips). This test attributes
*that* 87% two ways, so the next optimization is aimed by data, not hypothesis:

  1. cProfile a single node-card render → top cumulative frames. Tells us whether
     the cost is OUR skin Python (pin/tooltip/type-resolution) or NiceGUI
     ``Element.__init__`` itself (which we can't micro-opt — the lever there is
     rendering fewer cards, i.e. culling).
  2. Element-construction census bucketed by call site (pin / tooltip / label /
     structural div / widget) → the per-node element budget and where to cut.

Instrumentation, not a gate. Prints two tables; asserts only structural facts.
Run::

    uv run pytest -m perf tests/ui/widget/test_skin_render_profile.py -s

Fork to watch for in the output:
  * if OUR skin frames (``_render_pin``, ``add_pin_tooltip``, ``get_stored_type``)
    dominate cumulative time → micro-opt the skin (cache type/icon, lazy tooltips).
  * if ``Element.__init__`` / ``Slot`` / ``Props``/``Style``/``Classes`` dominate
    → it's NiceGUI element volume; the lever is fewer mounted cards (culling),
    same as the pan problem. Skin micro-opt won't move it.
"""

from __future__ import annotations

# editor import first to avoid circular import (see CLAUDE.md / test conventions)
import haywire.core.graph.editor  # noqa: F401

import cProfile
import io
import pstats
from collections import Counter
from pathlib import Path

import pytest
from nicegui import ui
from nicegui.element import Element

from haywire.core.graph.base import BaseGraph
from haywire.core.graph.scheduler import SyncScheduler
from haywire.ui.skin.factory import SkinFactory

# perf + integration: depends on the `library_system` fixture and a fully-loaded
# node registry (loads a real graph). Marked integration so it only runs where
# that registry state is reliable — outside it, shared-global registry pollution
# from earlier tests can leave PerformanceTester unregistered (0 nodes loaded).
pytestmark = [pytest.mark.perf, pytest.mark.integration]

_GRAPH = Path(__file__).resolve().parents[3] / "graphs" / "10x200nodes.haywire"

# Call-site frames we bucket Element constructions by. Each key is a substring
# matched against the constructing call stack; first match wins, else "other".
_BUCKETS = [
    ("_render_pin", "pin (icon + props)"),
    ("add_pin_tooltip", "tooltip (label x2)"),
    ("render_widget", "widget"),
    ("_render_left", "port row structure"),
    ("_render_right", "port row structure"),
    ("_render_config", "port row structure"),
    ("_render_root_ghost_pins", "ghost pins"),
    ("_render_diagnostics_button", "error/warning badge"),
    ("render", "card / header / columns"),
]


def _load_graph_and_factory(library_system):
    injector = library_system.injector
    skin_factory = injector.get(SkinFactory)
    graph = BaseGraph(graph_id="perf", name="perf", validation_scheduler=SyncScheduler())
    assert _GRAPH.exists(), f"graph fixture missing: {_GRAPH}"
    assert graph.load_from_file(str(_GRAPH)), "graph failed to load"
    wrappers = list(graph.node_wrappers.values())
    assert len(wrappers) == 200, f"expected 200 nodes, got {len(wrappers)}"
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()
    return skin_factory, skin_key, wrappers


def test_single_node_render_profile(library_system):
    """cProfile one node-card render and print the top cumulative frames."""
    skin_factory, skin_key, wrappers = _load_graph_and_factory(library_system)
    one = wrappers[0]

    # Warm the skin cache + any lazy imports so the profile reflects steady state.
    with ui.card():
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrappers[1])

    profiler = cProfile.Profile()
    with ui.card():
        profiler.enable()
        skin_factory.render(skin_registry_key=skin_key, wrapper=one)
        profiler.disable()

    s = io.StringIO()
    stats = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
    stats.print_stats(25)
    print("\n--- cProfile: single node-card render (top 25 cumulative) ---\n")
    print(s.getvalue())


def test_element_census_per_node(library_system):
    """Count Element constructions for one node, bucketed by skin call site."""
    skin_factory, skin_key, wrappers = _load_graph_and_factory(library_system)
    one = wrappers[0]

    with ui.card():
        skin_factory.render(skin_registry_key=skin_key, wrapper=wrappers[1])  # warm

    buckets: Counter[str] = Counter()
    orig_init = Element.__init__

    def counting_init(self, *a, **k):
        # Walk the stack once; attribute to the first matching skin call site.
        import traceback

        stack = "".join(traceback.format_stack(limit=25))
        label = "other"
        for needle, name in _BUCKETS:
            if f" {needle}(" in stack or f".{needle}(" in stack:
                label = name
                break
        buckets[label] += 1
        return orig_init(self, *a, **k)

    Element.__init__ = counting_init
    try:
        with ui.card():
            skin_factory.render(skin_registry_key=skin_key, wrapper=one)
    finally:
        Element.__init__ = orig_init

    total = sum(buckets.values())
    print("\n--- Element constructions for ONE node-card, by skin call site ---")
    print(f"  total elements / node : {total}  (x200 nodes = {total * 200} for the graph)\n")
    for name, n in buckets.most_common():
        print(f"    {n:5d}  {100 * n / total:5.1f}%  {name}")
    print()

    assert total > 0, "no elements constructed — census instrumentation missed the render"
