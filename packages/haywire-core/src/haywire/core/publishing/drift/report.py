"""Human-readable formatting of a `DepDrift`."""

from haywire.core.publishing.drift.model import DepDrift


def _format_drift_report(drift: DepDrift) -> str:
    """Format a :class:`DepDrift` as a multi-line human-readable string."""
    lines: list[str] = [f"Dependency drift in {drift.lib_dir.name}:"]
    if drift.pyproject_missing:
        lines.append("  pyproject.toml [project] dependencies missing:")
        for s in drift.pyproject_missing:
            lines.append(f"    + {s}")
    if drift.decorator_missing:
        lines.append("  @library(dependencies=[...]) missing:")
        for s in drift.decorator_missing:
            lines.append(f"    + {s}")
    if drift.pyproject_version_lag:
        lines.append("  pyproject.toml haybale floors lagging installed:")
        for dist, declared_floor, installed in drift.pyproject_version_lag:
            lines.append(f"    ~ {dist}: declared {declared_floor}, installed {installed}")
    if drift.unresolved:
        lines.append("  Unresolved imports (not mapped to any distribution — likely dynamic):")
        for s in drift.unresolved:
            lines.append(f"    ? {s}")
    return "\n".join(lines)
