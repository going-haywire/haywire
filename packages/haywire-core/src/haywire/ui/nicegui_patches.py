"""Startup-time patches for NiceGUI internals.

These bridge known NiceGUI performance gaps until they are fixed upstream. Each
patch is guarded so a NiceGUI version bump that moves/renames the target fails
loudly at startup (raising) rather than silently reverting to the slow path.

Call :func:`apply_nicegui_patches` once, before any rendering.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_applied = False


def apply_nicegui_patches() -> None:
    """Apply all NiceGUI startup patches. Idempotent."""
    global _applied
    if _applied:
        return
    _cache_expects_arguments()
    _applied = True


def _cache_expects_arguments() -> None:
    """Memoize ``nicegui.helpers.expects_arguments``.

    Why
    ---
    Every ``.props()`` / ``.style()`` / ``.classes()`` mutation on an element
    fires that observable dict's change handler, which routes through
    ``nicegui.events.handle_event`` → ``helpers.expects_arguments(handler)`` to
    decide whether to call the handler with arguments. ``expects_arguments``
    runs ``inspect.signature(handler)`` — a heavy introspection — *every time*,
    on the same handler whose signature never changes.

    On a 200-node graph this fires ~135,000 times (≈674 per node), recomputing
    the same booleans. Memoizing turns the repeated calls into dict lookups.

    BOUNDED cache, on purpose. The cache key is the handler object, and the
    handler set is NOT small framework-wide: the observable ``_update`` handlers
    are bound methods (one per Props/Style/Classes instance → one key per element
    per collection), and ``handle_event`` is also the dispatch for every user
    ``on_click``/``on_change`` lambda. An unbounded ``lru_cache(maxsize=None)``
    would pin each handler — and through bound methods, their elements — for the
    whole process lifetime, leaking on a long-running server as clients connect/
    disconnect (this was the NiceGUI maintainer's review note on our upstream
    proposal). A WeakKeyDictionary does not help: bound methods are recreated on
    each access and collected immediately, so weak keys evict before they hit.

    A bounded cache is leak-free and loses nothing here: the per-element fires
    are CONSECUTIVE (``.classes().style().props()`` back-to-back hit the same
    handler), so a tiny cache captures them. Measured on the 200-node graph,
    every size from ``maxsize=4`` to ``None`` gives the identical 73% hit rate
    and ~1.4× speedup — confirming the consecutive-fire assumption. We keep a
    comfortable ``1024`` for headroom against interleaved handlers elsewhere.

    Measured: 200-node render ~2.4s → ~1.4–1.7s (~1.25–1.44× depending on path).
    See ``tests/ui/widget/test_expects_arguments_cache.py`` for the benchmark
    and ``tests/ui/widget/test_skin_render_profile.py`` for the profile that
    found it. The function is pure (callable → bool), so the cache is
    correctness-neutral.

    Upstream: not cached on NiceGUI ``main`` as of 2026-06. The maintainer's
    preferred fix is to resolve ``expects_arguments`` ONCE at handler-
    registration (mirroring ``Callback.expect_args`` in ``nicegui/event.py``)
    rather than cache per-fire — leak-free and the long-term home. This bounded
    cache is our local bridge until that lands; remove it then. See ADR-0006.
    """
    import nicegui.events as events
    import nicegui.helpers as helpers

    original = getattr(helpers, "expects_arguments", None)
    if original is None or not callable(original):
        raise RuntimeError(
            "NiceGUI patch target 'nicegui.helpers.expects_arguments' is missing or not "
            "callable — the NiceGUI internals changed. Review haywire.ui.nicegui_patches "
            "against the installed NiceGUI version before removing this guard."
        )

    # handle_event resolves the function as ``helpers.expects_arguments`` (an
    # attribute lookup on the helpers package each call), so patching the
    # package attribute is sufficient. We also patch the ``events.helpers``
    # binding defensively in case the resolution path changes.
    if getattr(events, "helpers", None) is not helpers:
        raise RuntimeError(
            "NiceGUI patch assumption broken: nicegui.events.helpers is not the "
            "nicegui.helpers package. Review haywire.ui.nicegui_patches."
        )

    # Bounded (not maxsize=None) — see docstring: keys are per-element bound
    # methods, so an unbounded cache leaks. Consecutive per-element fires mean a
    # small bound captures the full benefit.
    cached = lru_cache(maxsize=1024)(original)
    helpers.expects_arguments = cached  # type: ignore[attr-defined]

    logger.debug("Applied NiceGUI patch: cached helpers.expects_arguments")
