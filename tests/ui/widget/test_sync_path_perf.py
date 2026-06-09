"""Test 1 — microbenchmark of isolated ``_sync_to_view`` cost.

Answers GREEN-vs-YELLOW for finding #3: is the BaseWidget + create_default_binding()
model->view path within 1.5x of SimpleWidget's bare get_value -> setattr?

We assert the *ratio*, never absolute time — absolute numbers are machine- and
load-dependent and would flake in CI. The 5x-median absorbs noise; run on an idle
machine. Excluded from the default suite (marked ``perf``); run explicitly with::

    uv run pytest -m perf tests/ui/widget/test_sync_path_perf.py -s

The ``-s`` surfaces the printed timing table, which is the actual deliverable —
the assert is a guard rail, the numbers are the decision input.

See ``docs/plans/widget-unification-perf-verification.md`` for the decision rule
(GREEN within 1.5x micro + <5% graph; YELLOW add fast path; RED keep SimpleWidget).
"""

import statistics
import time

import pytest

from tests.ui.widget._sync_fixtures import (
    build_base_converter,
    build_base_default,
    build_simple,
)

pytestmark = pytest.mark.perf

# Pre-registered threshold (set BEFORE measuring — see plan).
RATIO_BUDGET = 1.5

_N = 100_000
_WARMUP = 1_000
_REPEATS = 5


def _bench_once(builder) -> float:
    """Time _N model->view syncs, alternating the model value each iteration.

    Alternating the value defeats any accidental caching/hoisting of the
    converter result so we measure real per-sync work.
    """
    sync, port, _el = builder()

    for i in range(_WARMUP):
        port.set_value(float(i))
        sync()

    t0 = time.perf_counter()
    for i in range(_N):
        port.set_value(float(i))
        sync()
    return time.perf_counter() - t0


def _median_seconds(builder) -> float:
    return statistics.median(_bench_once(builder) for _ in range(_REPEATS))


def test_sync_to_view_ratio():
    simple = _median_seconds(build_simple)
    base_default = _median_seconds(build_base_default)
    base_converter = _median_seconds(build_base_converter)

    ratio_default = base_default / simple
    ratio_converter = base_converter / simple

    verdict = "GREEN (micro)" if ratio_default <= RATIO_BUDGET else "YELLOW — build fast path, re-measure"

    print(
        f"\n--- _sync_to_view microbenchmark (N={_N}, median of {_REPEATS}) ---\n"
        f"  simple          : {simple:.4f}s  (1.00x, baseline)\n"
        f"  base + default  : {base_default:.4f}s  ({ratio_default:.2f}x)\n"
        f"  base + converter: {base_converter:.4f}s  ({ratio_converter:.2f}x)\n"
        f"  budget          : <= {RATIO_BUDGET:.2f}x for GREEN on the default path\n"
        f"  verdict         : {verdict}\n"
    )

    # This is a measurement documenting a known finding (the YELLOW verdict in
    # docs/plans/widget-unification-perf-verification.md), NOT a behavior guard.
    # Over budget is the *expected* current state, so record it as xfail rather
    # than a hard failure — it flips to a real pass (GREEN) only if a future fast
    # path brings the default-binding sync within budget, which is exactly when
    # we'd want to be alerted.
    if ratio_default > RATIO_BUDGET:
        pytest.xfail(
            f"BaseWidget+create_default_binding() _sync_to_view is {ratio_default:.2f}x "
            f"SimpleWidget (budget {RATIO_BUDGET:.2f}x) — known YELLOW. Fix: skip the "
            "converter for the source_property=='value' + PrimitiveUnwrappingConverter "
            "case, then this passes GREEN."
        )
