"""Measure the render speedup from caching NiceGUI's ``expects_arguments``.

The skin-render profile (``test_skin_render_profile.py``) showed the top
cumulative cost is ``nicegui.events.handle_event`` → ``helpers.expects_arguments``
→ ``inspect.signature``, called ~674x per node (134,800x for the 200-node graph),
recomputing the signature of the SAME handful of handler functions every time.

This test quantifies the *real* wall-time win from memoizing that introspection
on the 200-node perf-graph render (``conftest.build_perf_graph``) — before
deciding whether a startup-time monkeypatch of ``expects_arguments`` is worth
carrying.

It is a measurement, not a fix: it patches in-test, reports the delta, and
restores. If the delta is large, the follow-up is a permanent cache installed at
app startup (and ideally an upstream NiceGUI PR adding ``functools.cache`` to
``expects_arguments`` — the handler set is tiny and the function is pure).

Run::

    uv run pytest -m perf tests/ui/widget/test_expects_arguments_cache.py -s
"""

from __future__ import annotations


import time
from functools import lru_cache

import pytest
from nicegui import ui

from haywire.ui.skin.factory import SkinFactory

from .conftest import build_perf_graph

# perf + integration: depends on the `library_system` fixture and a fully-loaded
# node registry (builds a real graph). Marked integration so it only runs where
# that registry state is reliable — outside it, shared-global registry pollution
# from earlier tests can leave PerformanceTester unregistered (0 nodes built).
pytestmark = [pytest.mark.perf, pytest.mark.integration]

_REPEATS = 3


def _render_all(skin_factory, wrappers, skin_key) -> float:
    with ui.card():
        t0 = time.perf_counter()
        for w in wrappers:
            skin_factory.render(skin_registry_key=skin_key, wrapper=w)
        return time.perf_counter() - t0


def test_expects_arguments_cache_speedup(library_system, nicegui_slot_context):
    skin_factory = library_system.injector.get(SkinFactory)
    graph = build_perf_graph()
    wrappers = list(graph.node_wrappers.values())
    skin_key = skin_factory._skin_registry.get_default_skin_registry_key()

    _render_all(skin_factory, wrappers, skin_key)  # warm caches / lazy imports

    baseline = min(_render_all(skin_factory, wrappers, skin_key) for _ in range(_REPEATS))

    # Install the cache at the binding site handle_event actually resolves:
    # `helpers.expects_arguments` inside nicegui.events.
    import nicegui.events as ev
    import nicegui.helpers as helpers
    from nicegui.helpers.functions import expects_arguments as _orig

    # Bounded to match the shipped patch (haywire.ui.nicegui_patches): keys are
    # per-element bound methods, so maxsize=None would leak. Per-element fires
    # are consecutive, so a small bound keeps the full speedup — every size from
    # 4 to None measured the same 73% hit rate / ~1.4x on this graph.
    @lru_cache(maxsize=1024)
    def _cached(func):
        return _orig(func)

    helpers.expects_arguments = _cached  # type: ignore[attr-defined]
    ev.helpers.expects_arguments = _cached  # type: ignore[attr-defined]
    try:
        cached = min(_render_all(skin_factory, wrappers, skin_key) for _ in range(_REPEATS))
    finally:
        helpers.expects_arguments = _orig  # type: ignore[attr-defined]
        ev.helpers.expects_arguments = _orig  # type: ignore[attr-defined]

    print(
        "\n--- expects_arguments cache: 200-node render wall time ---\n"
        f"  baseline (uncached)   : {baseline:.3f}s  ({baseline / 200 * 1000:.2f} ms/node)\n"
        f"  cached expects_args   : {cached:.3f}s  ({cached / 200 * 1000:.2f} ms/node)\n"
        f"  speedup               : {baseline / cached:.2f}x   saved {baseline - cached:.3f}s\n"
        f"  verdict               : "
        f"{'worth a startup-time cache' if baseline / cached >= 1.3 else 'marginal — look elsewhere'}\n"
    )
