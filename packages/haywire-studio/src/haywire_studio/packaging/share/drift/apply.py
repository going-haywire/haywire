"""Applying a computed `DepDrift` by writing missing deps to disk."""

from haywire.core.library.decorator_io import merge_decorator_list_field
from haywire.core.library.dep_detect import (
    EntryPointLibrarySource,
    detect_deps,
    find_module_dir,
    set_pyproject_dependencies,
)
from haywire_studio.packaging.share.drift.model import DepDrift
from haywire_studio.packaging.share.drift.versionspec import _parse_floor_spec, _strip_specifier
from haywire_studio.packaging.share.manifest.reader import read_manifest


def union_pyproject_deps(
    *,
    current: list[str],
    detected: list[str],
    libraries: object,
) -> list[str]:
    """Merge declared and detected pyproject deps by distribution
    NAME (not by full specifier string).

    For each distribution:
      - If both sides have a spec and the dist is a registered haybale, prefer
        the detected spec (so a lagging floor bumps to the installed version).
      - If both sides have a spec and the dist is third-party, keep the
        user's existing spec (we never narrow third-party compatibility).
      - If only one side has a spec, keep it.

    ``libraries`` must implement ``HaywireLibrarySource`` (only ``list_names``
    and ``get_library_distribution_name`` are used).
    """
    haybale_dists: set[str] = set()
    if hasattr(libraries, "list_names") and hasattr(libraries, "get_library_distribution_name"):
        # libraries: object is duck-typed (HaywireLibrarySource) and guarded by
        # the hasattr() check above; both checkers need the methods waved through.
        for lib_id in libraries.list_names():  # type: ignore[attr-defined]  # ty: ignore[call-non-callable]
            dist = libraries.get_library_distribution_name(lib_id)  # type: ignore[attr-defined]  # ty: ignore[call-non-callable]
            if dist:
                haybale_dists.add(dist)

    current_by_name: dict[str, str] = {_strip_specifier(s): s for s in current}
    detected_by_name: dict[str, str] = {_strip_specifier(s): s for s in detected}

    result: dict[str, str] = {}
    for name in current_by_name.keys() | detected_by_name.keys():
        cur_spec = current_by_name.get(name)
        det_spec = detected_by_name.get(name)
        if cur_spec is not None and det_spec is not None:
            result[name] = det_spec if name in haybale_dists else cur_spec
        else:
            result[name] = cur_spec or det_spec or name
    return sorted(result.values())


def apply_drift_fix(drift: DepDrift) -> None:
    """Apply a :class:`DepDrift` by writing missing deps to disk.

    Updates the library's pyproject.toml with the union of currently declared
    and detected dependencies, and rewrites the @library decorator to include
    any missing names. Existing declarations are preserved — the gate's
    "missing-only" definition makes this an additive operation.
    """
    if not drift.has_drift:
        return

    lib_dir = drift.lib_dir

    # 1. pyproject.toml: re-run detect_deps to get the proper specifiers, then
    #    union with what's already declared. Also rewrite lagging haybale-* floors.
    if drift.pyproject_missing or drift.pyproject_version_lag:
        libraries = EntryPointLibrarySource()
        detected = detect_deps(lib_dir, libraries=libraries)
        pyproject_path = lib_dir / "pyproject.toml"
        declared: list[str] = []
        if pyproject_path.is_file():
            # Strict: reading to rewrite. Must fail here, before
            # set_pyproject_dependencies below, or a corrupt file gets
            # silently overwritten (it deliberately re-raises on bad TOML).
            data = read_manifest(lib_dir)
            declared = list(data.get("project", {}).get("dependencies", []))
        # Bump any lagging haybale floors to the installed version, preserving
        # the declared operator (~=, >=, or >).
        lag_by_dist = {dist: installed for dist, _floor, installed in drift.pyproject_version_lag}
        rewritten: list[str] = []
        for spec in declared:
            dist_name = _strip_specifier(spec)
            if dist_name in lag_by_dist:
                parsed = _parse_floor_spec(spec)
                if parsed is not None:
                    op, _old_floor = parsed
                    rewritten.append(f"{dist_name}{op}{lag_by_dist[dist_name]}")
                    continue
            rewritten.append(spec)
        # Union with newly detected pyproject specs (the missing-deps branch).
        declared_names = {_strip_specifier(s) for s in rewritten}
        unioned = list(rewritten)
        for spec in detected.pyproject:
            if _strip_specifier(spec) not in declared_names:
                unioned.append(spec)
        set_pyproject_dependencies(lib_dir, sorted(unioned))

    # 2. @library decorator: delegate to the shared rewriter also used by
    #    apply_drift_replace and the marketplace Edit dialog.
    if drift.decorator_missing:
        module_dir = find_module_dir(lib_dir)
        if module_dir is None:
            return
        init_file = module_dir / "__init__.py"
        if not init_file.is_file():
            return
        merge_decorator_list_field(init_file, "dependencies", drift.decorator_missing, mode="union")
