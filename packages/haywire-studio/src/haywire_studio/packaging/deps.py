"""``haywire deps check`` — CI-shaped dependency-manifest drift detector.

Deliberately independent of SharePipeline: no git, no preconditions, no
versioning, no marketstall. Loops every barn/* library, runs the same
detect_share_drift() the interactive wizard and --yes both gate on, and
reports. Never writes — fixing drift stays on the wizard's drift step or
the Library Overview Editor's Detect Dependencies button.
"""

from __future__ import annotations

from pathlib import Path

from haywire.core.publishing.barn import barn_library_dirs
from haywire.core.publishing.drift.detect import detect_share_drift

EXIT_OK = 0
EXIT_DRIFT = 1


def run_deps_check_cli(repo_root: Path) -> int:
    """Report dependency-manifest drift for every barn/* library.

    Never writes. Exit code gates only on actionable drift (missing pyproject
    or decorator declarations, or a version-lag floor) — unresolved imports
    are printed for information but never fail the run, matching the
    interactive wizard's own treatment of them.
    """
    barn = repo_root / "barn"
    libraries = barn_library_dirs(repo_root)

    if not libraries:
        print(f"No library with a pyproject.toml under {barn}. Nothing to check.")
        return EXIT_OK

    any_drift = False
    for lib_dir in libraries:
        drift = detect_share_drift(lib_dir)
        if drift.has_drift:
            any_drift = True
            print(f"{lib_dir.name}:")
            for dep in drift.pyproject_missing:
                print(f"  + pyproject.toml: {dep}")
            for dep in drift.decorator_missing:
                print(f"  + haybale.toml linked_libraries: {dep}")
            for dist, declared, installed in drift.pyproject_version_lag:
                print(f"  ~ {dist}: declared {declared}, installed {installed}")
        if drift.unresolved:
            # Informational only — matches the interactive wizard's own
            # treatment of unresolved imports. Never gates the exit code.
            print(f"{lib_dir.name}: unresolved imports (declare manually): {', '.join(drift.unresolved)}")

    if any_drift:
        print(
            "\n✗ Dependency drift found. Resolve it with `haywire share` "
            "(interactive) or the Library Overview Editor's Detect Dependencies button."
        )
        return EXIT_DRIFT

    print("✓ No dependency drift.")
    return EXIT_OK
