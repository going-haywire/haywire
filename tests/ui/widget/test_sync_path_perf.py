"""Microbenchmark of the unified BaseWidget model→view sync path.

Times the default bind() path vs an explicit-converter path. Informational
only — the base-class choice is performance-irrelevant, so this records the
numbers (the printed table is the deliverable) with no hard ratio gate.
Excluded from the default suite (``perf`` marker); run with::

    uv run pytest -m perf tests/ui/widget/test_sync_path_perf.py -s
"""

import statistics
import time

import pytest

from tests.ui.widget._sync_fixtures import build_base_converter, build_base_default

pytestmark = pytest.mark.perf

_N = 100_000
_WARMUP = 1_000
_REPEATS = 5


def _bench_once(builder) -> float:
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


def test_sync_to_view_cost():
    base_default = _median_seconds(build_base_default)
    base_converter = _median_seconds(build_base_converter)
    print(
        f"\n--- BaseWidget sync_to_view microbenchmark (N={_N}, median of {_REPEATS}) ---\n"
        f"  default bind    : {base_default:.4f}s\n"
        f"  explicit conv   : {base_converter:.4f}s  ({base_converter / base_default:.2f}x default)\n"
        f"  (informational — perf is not a gate)\n"
    )
    # No ratio assertion: the base-class choice is perf-irrelevant. This test
    # exists to surface the numbers, not to gate CI.
    assert base_default > 0
    assert base_converter > 0
