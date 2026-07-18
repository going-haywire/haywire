"""Smoke test for the benchmark suite — keeps the cases from rotting.

Imports the benchmark case registry from ``benchmarks/cases.py`` and runs each
case once, asserting it produces a positive per-op timing. This is NOT a
performance gate (timings are not asserted against thresholds) — it only proves
each frozen case still builds and runs after framework changes.

``perf``-marked, so it's excluded from the default suite::

    uv run pytest -m perf tests/core/test_execution/test_benchmarks_smoke.py
"""

import sys
import time
from pathlib import Path

import pytest


def _bench_dir() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p / "benchmarks"
        p = p.parent
    raise RuntimeError("repo root (pyproject.toml) not found")


sys.path.insert(0, str(_bench_dir()))
import cases as bench_cases  # noqa: E402  (after sys.path tweak)

pytestmark = [pytest.mark.perf, pytest.mark.integration]


@pytest.mark.parametrize("case", bench_cases.get_cases(), ids=lambda c: c.name)
def test_case_runs_and_times(case, library_system):
    """Each frozen case builds, runs, and yields a positive per-op timing."""
    prepared = case.prepare()
    assert prepared.ops > 0

    prepared.run()  # warm (build executors/pipes)
    t0 = time.perf_counter_ns()
    prepared.run()
    elapsed = time.perf_counter_ns() - t0
    assert elapsed > 0, f"case {case.name!r} produced a non-positive timing"
