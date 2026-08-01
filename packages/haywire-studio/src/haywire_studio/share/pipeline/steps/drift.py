"""Step 2 — dependency drift detection and the Union/Replace decision."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.decorator_io import merge_decorator_list_field
from haywire.core.library.dep_detect import (
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)
from haywire_studio.share.drift.apply import apply_drift_fix
from haywire_studio.share.drift.detect import detect_share_drift
from haywire_studio.share.pipeline.errors import ManifestError
from haywire_studio.share.pipeline.fixes import _MANIFEST_FAILURE_TYPES
from haywire_studio.share.pipeline.results import DriftReport

if TYPE_CHECKING:
    from haywire_studio.share.pipeline.pipeline import SharePipeline


def check(pipeline: "SharePipeline") -> DriftReport:
    """Run the drift gate against every barn library.

    Splits findings into actionable drift (a decision) and unresolved-only
    (informational). Uses ``detect_share_drift``, which is also called by
    ``haywire deps check`` CLI, so both commands report the same drift.
    """
    drifted: list[object] = []
    unresolved_only: list[object] = []
    for lib_dir in pipeline._barn_library_dirs():
        drift = detect_share_drift(lib_dir)
        if drift.has_drift:
            drifted.append(drift)
        elif drift.unresolved:
            unresolved_only.append(drift)
    return DriftReport(drifted=drifted, unresolved_only=unresolved_only)


def apply_union(pipeline: "SharePipeline", report: DriftReport) -> list[Path]:
    """Merge detected deps into what's declared. Additive — removes nothing."""
    written: list[Path] = []
    for drift in report.drifted:
        try:
            apply_drift_fix(drift)
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
        written.extend(_written_paths(pipeline, drift.lib_dir))
    return pipeline.record(written)


def apply_replace(pipeline: "SharePipeline", report: DriftReport) -> list[Path]:
    """Overwrite declared deps with exactly what was detected.

    Destructive by design: a declaration the source no longer imports is
    removed. That is why step 2 is a decision and not an auto-fix.
    """
    written: list[Path] = []
    libraries = EntryPointLibrarySource()
    for drift in report.drifted:
        lib_dir = drift.lib_dir
        detected = detect_deps(lib_dir, libraries=libraries)

        try:
            set_pyproject_dependencies(lib_dir, sorted(detected.pyproject))
            written.append(lib_dir / "pyproject.toml")

            module_dir = find_module_dir(lib_dir)
            if module_dir is not None:
                init_file = module_dir / "__init__.py"
                if init_file.is_file():
                    merge_decorator_list_field(
                        init_file,
                        "dependencies",
                        detected.library_decorator,
                        mode="replace",
                    )
                    written.append(init_file)
        except _MANIFEST_FAILURE_TYPES as exc:
            raise ManifestError(str(exc)) from exc
    return pipeline.record(written)


def _written_paths(pipeline: "SharePipeline", lib_dir: Path) -> list[Path]:
    """The files ``apply_drift_fix`` may have touched for one library.

    ``apply_drift_fix`` returns nothing, so the paths are reconstructed
    here. Both are included unconditionally: a path already identical on
    disk is a no-op for ``git add``, whereas a missed path would silently
    leave a fix out of the commit.
    """
    paths = [lib_dir / "pyproject.toml"]
    module_dir = find_module_dir(lib_dir)
    if module_dir is not None and (module_dir / "__init__.py").is_file():
        paths.append(module_dir / "__init__.py")
    return paths
