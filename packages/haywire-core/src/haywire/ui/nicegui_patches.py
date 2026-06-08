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
    on a tiny fixed set of handler functions whose signatures never change.

    On a 200-node graph this fires ~135,000 times (≈674 per node), recomputing
    the same booleans. Memoizing on the handler object turns all-but-the-first
    call per handler into a dict lookup.

    Measured: 200-node render 2.44s → 1.74s (≈1.41×, −0.7s). See
    ``tests/ui/widget/test_expects_arguments_cache.py`` for the benchmark and
    ``tests/ui/widget/test_skin_render_profile.py`` for the profile that found
    it. The function is pure (callable → bool) and handler identities are
    stable, so the cache is correctness-neutral.

    Upstream: not cached on NiceGUI ``main`` as of 2026-06; complements the
    ``.props/.classes/.style`` update-cost work in zauberzeug/nicegui#338.
    Candidate for an upstream ``functools.cache`` PR.
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

    cached = lru_cache(maxsize=None)(original)
    helpers.expects_arguments = cached  # type: ignore[attr-defined]

    logger.debug("Applied NiceGUI patch: cached helpers.expects_arguments")
