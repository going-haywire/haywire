"""The `DepDrift` data model — no logic, just the shape of a drift result."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DepDrift:
    """What one library's declarations and its actual imports say about each other.

    All lists are sorted. Only ``pyproject_missing`` is drift: an import the
    published manifest does not declare, so a consumer installs the library and
    it fails on import. Everything else is a *fact about the library*, and each
    is handled differently:

    * ``linked_missing`` — registered haywire libraries the source imports
      that ``haybale.toml``'s ``linked_libraries`` does not list. Applied
      AUTOMATICALLY, never offered as a choice, because there is nothing to
      decide: ``detect_deps`` only emits a name here when the source imports it
      AND it resolves to an installed, registered library, so the entry is
      provably true. It carries no version specifier, narrows nothing for
      consumers, and its only effects are hot-reload scope tracking and the
      marketplace's enable/disable gating. Reported rather than silent, though
      — it edits ``haybale.toml``, which is hand-authored, not generated.
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

    Consequently ``has_drift`` counts ``pyproject_missing`` only: you cannot
    refuse to publish over something the tool fixes unconditionally.
    """

    lib_dir: Path
    pyproject_missing: list[str] = field(default_factory=list)
    linked_missing: list[str] = field(default_factory=list)
    unused_declarations: list[str] = field(default_factory=list)
    pyproject_version_lag: list[tuple[str, str, str]] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)

    @property
    def has_drift(self) -> bool:
        """True iff an imported distribution is undeclared — the breaking state.

        Excludes ``linked_missing``: that is repaired automatically, so it is
        never a state the author is asked to resolve or allowed to decline.
        """
        return bool(self.pyproject_missing)

    @property
    def has_findings(self) -> bool:
        """True iff the detect report has anything at all to show for this library."""
        return bool(
            self.pyproject_missing
            or self.linked_missing
            or self.unused_declarations
            or self.pyproject_version_lag
            or self.unresolved
        )
