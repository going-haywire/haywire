#!/usr/bin/env python3
"""Haywire benchmark runner — invoked by the ``haywire-benchmark`` skill.

Runs every frozen benchmark case (or one filtered by name), records the
**min-of-N** per-operation time (plus median/p90 spread) as an absolute number,
stamps it with commit/dirty/host/python/timestamp, appends one JSONL row per case
to ``benchmarks/results/results.jsonl``, and prints a table comparing each case to
its last *comparable* prior run (same host, clean tree).

It only ever appends — it never commits. Fold the new rows into your own commit.
Methodology and the reasoning behind min-not-mean / absolute-not-delta /
frozen-inputs / host-and-dirty filtering lives in ``benchmarks/README.md``.

    uv run python benchmarks/run.py                # all cases
    uv run python benchmarks/run.py control_edge   # cases whose name contains "control_edge"
"""

from __future__ import annotations

import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cases as bench_cases  # noqa: E402  (after sys.path tweak)

_DEADBAND_PCT = 2.0  # |drift| below this reads as "~ flat" (noise floor)


def _project_root() -> Path:
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "pyproject.toml").exists():
            return p
        p = p.parent
    raise RuntimeError("project root (pyproject.toml) not found")


def _git(root: Path, *args: str) -> tuple[int, str]:
    """Run a git command; return (returncode, stripped stdout). Never raises."""
    out = subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(root), check=False)
    return out.returncode, out.stdout.strip()


def _bootstrap_library_system(root: Path):
    from haywire.core.di.config import set_global_injector, set_library_system
    from haywire.core.di.test_config import create_test_library_system

    service = create_test_library_system(
        workspace_root=str(root),
        library_paths=[str(root / "barn")],
        load_libraries=True,
        enable_file_watching=False,
    )
    set_library_system(service)
    set_global_injector(service.injector)
    return service


def _measure(prep: "bench_cases.Prepared") -> tuple[float, float, float, int]:
    """Warmup, then min-of-N per-operation timing with median/p90 spread."""
    for _ in range(prep.warmup):
        prep.run()
    per_op: list[float] = []
    for _ in range(prep.repeats):
        t0 = time.perf_counter_ns()
        prep.run()
        per_op.append((time.perf_counter_ns() - t0) / prep.ops)
    per_op.sort()
    p90 = per_op[min(len(per_op) - 1, int(0.9 * len(per_op)))]
    return per_op[0], statistics.median(per_op), p90, len(per_op)


def _load_prior(results_file: Path) -> list[dict]:
    if not results_file.exists():
        return []
    rows = []
    for line in results_file.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def _last_comparable(prior: list[dict], case: str, host: str) -> Optional[dict]:
    """Most recent prior row for this case on this host from a clean tree."""
    cands = [r for r in prior if r.get("case") == case and r.get("host") == host and not r.get("dirty")]
    return cands[-1] if cands else None


def _drift(new_min: float, prior: Optional[dict]) -> str:
    if prior is None:
        return "    (no prior)"
    base = prior.get("min")
    if not base:
        return "    (no prior)"
    pct = (new_min - base) / base * 100.0
    if pct > _DEADBAND_PCT:
        return f"  ↑ +{pct:.1f}%  (was {base:.1f})"
    if pct < -_DEADBAND_PCT:
        return f"  ↓ {pct:.1f}%  (was {base:.1f})"
    return f"  ~ {pct:+.1f}%  (was {base:.1f})"


def main(argv: list[str]) -> int:
    only = argv[1] if len(argv) > 1 else None
    root = _project_root()
    results_file = root / "benchmarks" / "results" / "results.jsonl"
    results_file.parent.mkdir(parents=True, exist_ok=True)

    rc_commit, commit_out = _git(root, "rev-parse", "HEAD")
    commit = commit_out[:12] if rc_commit == 0 and commit_out else "unknown"
    rc_branch, branch_out = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    branch = branch_out if rc_branch == 0 and branch_out else "unknown"
    # Fail-safe: a git-status failure (e.g. a transient index lock from a
    # concurrent git client) must read as DIRTY, never clean — a run we cannot
    # prove came from a clean tree must never be eligible as a baseline.
    rc_status, status_out = _git(root, "status", "--porcelain")
    dirty = rc_status != 0 or bool(status_out)
    host = platform.node() or "unknown"
    py = platform.python_version()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    selected = bench_cases.get_cases(only)
    if not selected:
        print(f"no cases match filter {only!r}; available: {[c.name for c in bench_cases.CASES]}")
        return 1

    _bootstrap_library_system(root)
    prior = _load_prior(results_file)

    print(f"\nhaywire-benchmark  commit {commit}  branch {branch}  host {host}  py {py}")
    if dirty:
        print("  ⚠ working tree is DIRTY — rows recorded as dirty=true and NOT usable as a baseline.")
    print(f"  comparing each case to its last clean run on {host} (deadband ±{_DEADBAND_PCT:.0f}%)\n")
    print(f"  {'case':22s} {'min':>10s} {'median':>10s} {'p90':>10s}  drift")
    print(f"  {'-' * 22} {'-' * 10} {'-' * 10} {'-' * 10}  {'-' * 22}")

    new_rows: list[dict] = []
    for case in selected:
        mn, med, p90, n = _measure(case.prepare())
        row = {
            "timestamp": timestamp,
            "commit": commit,
            "dirty": dirty,
            "branch": branch,
            "host": host,
            "python": py,
            "case": case.name,
            "category": case.category,
            "min": round(mn, 1),
            "median": round(med, 1),
            "p90": round(p90, 1),
            "n": n,
            "unit": case.unit,
        }
        new_rows.append(row)
        drift = _drift(mn, _last_comparable(prior, case.name, host))
        print(f"  {case.name:22s} {mn:10.1f} {med:10.1f} {p90:10.1f}{drift}   {case.unit}/op")

    with results_file.open("a") as f:
        for row in new_rows:
            f.write(json.dumps(row) + "\n")

    rel = results_file.relative_to(root)
    print(f"\n  appended {len(new_rows)} row(s) to {rel} (not committed — fold into your commit)\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
