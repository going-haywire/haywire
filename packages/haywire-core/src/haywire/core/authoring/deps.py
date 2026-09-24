"""What one module's source would add to its library's declarations."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from haywire.core.library.dep_detect import HaywireLibrarySource, detect_source_deps

if TYPE_CHECKING:
    from haywire.core.library.identity import LibraryIdentity


def linked_additions(source: str, identity: "LibraryIdentity", libraries: HaywireLibrarySource) -> list[str]:
    """The haywire libraries ``source`` imports that ``identity`` does not list in ``linked_libraries``.

    The same predicate ``detect_deps`` applies to a whole library: an import
    counts only when it resolves to an installed, registered haywire
    library. The library itself and ``haywire`` never count.
    """
    detected = detect_source_deps(source, self_module=_self_module(identity), libraries=libraries)
    declared = set(identity.linked_libraries or [])
    return [name for name in detected.library_linked if name not in declared and name != "haywire"]


def undeclared_imports(
    source: str, identity: "LibraryIdentity", libraries: HaywireLibrarySource
) -> list[str]:
    """The distributions ``source`` imports that the library's ``pyproject.toml`` does not declare.

    Returns distribution names, sorted. Empty when the library has no
    readable ``pyproject.toml``: there is nothing to compare against.
    """
    from haywire.core.library.dep_edit import norm_dep, read_dependencies
    from haywire.core.marketstall.requirement import dependency_name

    lib_dir = _distribution_dir(Path(identity.folder_path))
    if lib_dir is None:
        return []
    try:
        declared = {norm_dep(dependency_name(entry)) for entry in read_dependencies(lib_dir)}
    except Exception:
        return []

    detected = detect_source_deps(source, self_module=_self_module(identity), libraries=libraries)
    names = {dependency_name(entry) for entry in detected.pyproject}
    return sorted(name for name in names if norm_dep(name) not in declared)


def _self_module(identity: "LibraryIdentity") -> str:
    return identity.module_name.split(".")[0]


def _distribution_dir(package_dir: Path) -> Path | None:
    """The nearest directory at or above ``package_dir`` holding a ``pyproject.toml``."""
    for candidate in (package_dir, *package_dir.parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    return None
