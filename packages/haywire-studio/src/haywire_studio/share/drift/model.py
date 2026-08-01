"""The `DepDrift` data model — no logic, just the shape of a drift result."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DepDrift:
    """Drift between a library's declared deps and what its imports require.

    All lists are sorted. ``has_drift`` is True iff any actionable list
    (missing or version-lag) is non-empty; ``unresolved`` is informational
    only and does not count as drift.

    ``pyproject_version_lag`` entries are ``(dist_name, declared_floor,
    installed_version)`` tuples. Scoped to haybale-* deps only.
    """

    lib_dir: Path
    pyproject_missing: list[str] = field(default_factory=list)
    decorator_missing: list[str] = field(default_factory=list)
    pyproject_version_lag: list[tuple[str, str, str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        return bool(self.pyproject_missing or self.decorator_missing or self.pyproject_version_lag)
