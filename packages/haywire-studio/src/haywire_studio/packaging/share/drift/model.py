"""The `DepDrift` data model — no logic, just the shape of a drift result."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DepDrift:
    """What one library's declarations and its actual imports say about each other.

    All lists are sorted. Only the two ``missing`` lists are drift: something
    the source imports is undeclared, so the published library will fail to
    install. Everything else here is a *fact about the library*, reported so
    the author can act on it, and deliberately NOT a defect:

    * ``unused_declarations`` — declared but not imported. Inert for consumers;
      common for transitive deps and optional features. Removing is a decision,
      never automatic, because ``detect_deps`` cannot see dynamic imports.
    * ``pyproject_version_lag`` — ``(dist_name, declared_floor,
      installed_version)`` for declared floors below what is installed. NOT
      drift: the correct floor is the lowest version that still works, which
      requires resolving and testing candidates. Static scanning cannot reach
      it, so "installed is newer" is an observation that time passed, not
      evidence the declaration is wrong. Raising it on that basis would narrow
      consumer compatibility from the author's dev-machine state.
    * ``unresolved`` — imports that mapped to no distribution, usually dynamic.

    Consequently ``has_drift`` counts the missing lists only.
    """

    lib_dir: Path
    pyproject_missing: list[str] = field(default_factory=list)
    decorator_missing: list[str] = field(default_factory=list)
    unused_declarations: list[str] = field(default_factory=list)
    pyproject_version_lag: list[tuple[str, str, str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True iff something imported is undeclared — the only breaking state."""
        return bool(self.pyproject_missing or self.decorator_missing)

    @property
    def has_findings(self) -> bool:
        """True iff the detect report has anything at all to show for this library."""
        return bool(
            self.pyproject_missing
            or self.decorator_missing
            or self.unused_declarations
            or self.pyproject_version_lag
            or self.unresolved
        )
