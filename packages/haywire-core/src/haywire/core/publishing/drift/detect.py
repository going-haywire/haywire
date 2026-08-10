"""Dependency-drift detection (Plan E follow-up, piece 3).

`haywire share` is the publish boundary: whatever the user emits here is what
downstream consumers will install. If the library's pyproject.toml or its
``haybale.toml`` ``linked_libraries`` are out of sync with the actual source
imports, the published library will fail to install or to enable for
consumers. The gate below detects that drift at share time so the user can fix
it before emitting.
"""

from pathlib import Path

from haywire.core.library.dep_edit import norm_dep
from haywire.core.library.dep_detect import (
    DetectedDeps,
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
)
from haywire.core.publishing.drift.model import DepDrift
from haywire.core.publishing.drift.versionspec import (
    _parse_floor_spec,
    _strip_specifier,
    version_lags,
)
from haywire.core.publishing.manifest.deps import _read_library_dependencies
from haywire.core.publishing.manifest.reader import read_manifest_lenient

_norm_dep = norm_dep


def detect_share_drift(lib_dir: Path) -> DepDrift:
    """Compute the drift between detected and declared dependencies for one library.

    Drift surfaces only ``missing`` entries — items that detect_deps found in
    the source but are NOT declared in the library's pyproject.toml or
    ``haybale.toml``'s ``linked_libraries``. Extra declarations (declared but
    unused) are not flagged: they are common (transitive deps, optional
    features) and false positives would block users unfairly. `share` is about
    correctness for consumers, which means "everything imported must be
    declared," not "everything declared must be imported."

    Uses :class:`EntryPointLibrarySource` so the gate works without a live
    haywire registry — any installed dist with a ``haywire.libraries`` entry
    point counts as a haywire library.

    Returns an empty :class:`DepDrift` when no module dir is found (the
    library has no inspectable source). Callers should still treat that as
    "nothing to gate" rather than an error.

    Degrades to treating declarations as empty (surfacing everything as
    missing) not just on unparsable TOML but also on an invalid ``os``
    declaration in ``haybale.toml``, since both go through
    :func:`read_manifest_lenient`.
    """
    libraries = EntryPointLibrarySource()
    detected: DetectedDeps = detect_deps(lib_dir, libraries=libraries)

    # Read current declarations. Lenient: a malformed or unreadable manifest
    # treats declarations as empty so the drift report still surfaces what's
    # missing, rather than crashing a read-only report.
    pyproject_data = read_manifest_lenient(lib_dir)
    declared_pyproject: list[str] = list(pyproject_data.get("project", {}).get("dependencies", []))

    module_dir = find_module_dir(lib_dir)
    declared_decorator: list[str] = []
    if module_dir:
        declared_decorator = _read_library_dependencies(module_dir)

    # Convert declared_pyproject specs ("haywire-core~=0.0.1") to bare dist names
    # so we can compare against detected entries by name.
    decl_py_names = {_strip_specifier(s) for s in declared_pyproject}
    detected_py_names = {_strip_specifier(s) for s in detected.pyproject}
    pyproject_missing = sorted(detected_py_names - decl_py_names)

    # Declared but never imported. Reported, never removed automatically: a
    # dynamic import detect_deps cannot see looks exactly like an unused
    # declaration, so acting on this without asking would break the library.
    unused_declarations = sorted(decl_py_names - detected_py_names)

    # Decorator deps round-trip as bare module names in detect_deps output;
    # _read_library_dependencies already converts to pip-package form. Re-
    # normalize both sides so "haybale_core" and "haybale-core" compare equal.
    decl_dec_norm = {_norm_dep(d) for d in declared_decorator}
    detected_dec_norm = {_norm_dep(d) for d in detected.library_decorator}
    decorator_missing = sorted(detected_dec_norm - decl_dec_norm)

    pyproject_version_lag = _detect_pyproject_version_lag(declared_pyproject, libraries=libraries)

    return DepDrift(
        lib_dir=lib_dir,
        pyproject_missing=pyproject_missing,
        decorator_missing=decorator_missing,
        unused_declarations=unused_declarations,
        pyproject_version_lag=pyproject_version_lag,
        unresolved=list(detected.unresolved),
    )


def _detect_pyproject_version_lag(
    declared: list[str],
    *,
    libraries: EntryPointLibrarySource,
) -> list[tuple[str, str, str]]:
    """Report declared haybale-* deps whose floor sits below the installed version.

    A fact, not a finding: see :class:`DepDrift`. Nothing here is ever raised
    automatically, and this does not count toward ``has_drift``.

    Scoped to registered haywire libraries and to the ``~=``/``>=``/``>``
    operators. ``==`` and ``<`` express deliberate intent that "lag" does not
    describe.
    """
    import importlib.metadata as _meta

    haybale_dists: set[str] = set()
    for lib_id in libraries.list_names():
        dist = libraries.get_library_distribution_name(lib_id)
        if dist:
            haybale_dists.add(dist)

    out: list[tuple[str, str, str]] = []
    for spec in declared:
        dist_name = _strip_specifier(spec)
        if dist_name not in haybale_dists:
            continue
        parsed = _parse_floor_spec(spec)
        if parsed is None:
            continue
        _op, declared_floor = parsed
        try:
            installed = _meta.version(dist_name)
        except _meta.PackageNotFoundError:
            continue
        if version_lags(declared_floor, installed):
            out.append((dist_name, declared_floor, installed))
    return sorted(out)
