"""Validation and repair of a library's ``os`` declaration in ``haybale.toml``.

``os`` gates installation, so a typo is expensive: "osx" declares a platform
nobody runs on, and the library silently offers itself to nobody. The vocabulary
is closed (macos/windows/linux) precisely so a wrong value can be *detected*
rather than passed through.

The declaration used to live in ``[tool.haywire]`` in pyproject, because a
decorator kwarg could not reach a consumer — but neither could that table, since
``pyproject.toml`` is not installed. It was therefore readable only at publish
time. ``haybale.toml`` ships inside the package, so the field is now readable
wherever the library is.
"""

from __future__ import annotations

from pathlib import Path

from haywire.core.publishing.manifest.errors import InvalidOsDeclarationError

_DECLARABLE_OS_VALUES = frozenset({"macos", "windows", "linux"})


def read_os_field(lib_dir: Path) -> list[str]:
    """Read and validate ``os`` from the library's haybale.toml.

    Raises :class:`InvalidOsDeclarationError` on anything outside the closed
    vocabulary, so a typo surfaces at preflight — where ``strip_os`` can repair
    it — rather than at install time on a consumer's machine, where it silently
    hides the library from everyone.
    """
    from haywire.core.library.haybale_toml import HAYBALE_TOML, read_raw

    module_dir = _module_dir_of(lib_dir)
    if module_dir is None:
        return []
    source = module_dir / HAYBALE_TOML
    os_decl = read_raw(module_dir).get("os")
    if os_decl is None:
        return []
    if not isinstance(os_decl, list):
        raise InvalidOsDeclarationError(f"`os` in {source} must be a list, got {type(os_decl).__name__}.")
    validated: list[str] = []
    for value in os_decl:
        if not isinstance(value, str) or value not in _DECLARABLE_OS_VALUES:
            raise InvalidOsDeclarationError(
                f"Invalid os value {value!r} in {source}. Declarable values: macos, windows, linux."
            )
        validated.append(value)
    return validated


_OS_NEAR_MISSES: dict[str, str] = {
    "osx": "macos",
    "darwin": "macos",
    "mac": "macos",
    "win": "windows",
    "win32": "windows",
    "nt": "windows",
}


def describe_os_fix(invalid_values: list[str]) -> str:
    """The fix_label for a strip_os repair, given the invalid values found.

    "Correct to <target>" when every value has a near-miss mapping (see
    :data:`_OS_NEAR_MISSES`) AND all of them map to the SAME declarable
    target; "Remove invalid values" otherwise (mixed targets, or any value
    with no near-miss mapping at all — e.g. "other", "freebsd").
    """
    if not invalid_values:
        return "Remove invalid values"
    targets = {_OS_NEAR_MISSES[v] for v in invalid_values if v in _OS_NEAR_MISSES}
    all_mapped = all(v in _OS_NEAR_MISSES for v in invalid_values)
    if all_mapped and len(targets) == 1:
        return f"Correct to {next(iter(targets))}"
    return "Remove invalid values"


def _partition_os_values(os_decl: list) -> tuple[list[str], list[str]]:
    """Split a raw [tool.haywire].os list into (invalid, corrected).

    ``invalid`` holds the original values that are not declarable (in
    document order, duplicates included). ``corrected`` is the list this
    field should become: already-declarable values kept as-is, near-miss
    values mapped to their target, and unmapped-invalid values dropped.
    """
    invalid: list[str] = []
    corrected: list[str] = []
    for value in os_decl:
        if isinstance(value, str) and value in _DECLARABLE_OS_VALUES:
            corrected.append(value)
        else:
            invalid.append(value)
            mapped = _OS_NEAR_MISSES.get(value) if isinstance(value, str) else None
            if mapped is not None:
                corrected.append(mapped)
    # dict.fromkeys dedups against the FINAL result while preserving first-seen
    # order — a running-prefix check here would miss a near-miss that appears
    # BEFORE the already-declarable value it maps to (e.g. ["osx", "macos"]).
    return invalid, list(dict.fromkeys(corrected))


def _module_dir_of(lib_dir: Path) -> Path | None:
    from haywire.core.library.dep_detect import find_module_dir

    return find_module_dir(lib_dir)


def invalid_os_values(lib_dir: Path) -> list[str]:
    """The invalid ``os`` values in the library's haybale.toml, read-only.

    Returns [] when the field is absent, not a list, or fully declarable.
    Used to compute a strip_os fix's label without mutating the file.
    """
    from haywire.core.library.haybale_toml import read_raw

    module_dir = _module_dir_of(lib_dir)
    if module_dir is None:
        return []
    os_decl = read_raw(module_dir).get("os")
    if not isinstance(os_decl, list):
        return []
    invalid, _corrected = _partition_os_values(os_decl)
    return invalid


def strip_undeclarable_os_values(lib_dir: Path) -> list[str]:
    """Rewrite ``os`` in the library's haybale.toml, keeping only declarable
    values (macos/windows/linux).

    Near-miss values (osx/darwin/mac -> macos, win/win32/nt -> windows) are
    corrected rather than dropped; anything else unmapped is removed outright —
    the vocabulary is closed and there is no honest way to guess intent for
    values like "other" or "freebsd".

    Returns the original non-declarable values found — what a fix_label
    describes and what a caller reports as "removed", whether a value was
    corrected via near-miss mapping or dropped entirely.

    Edits through ``edit_toml`` rather than a regex: the file is hand-editable
    and carries the author's comments, and unlike the pyproject rewrite this
    replaced, there is no risk of matching an ``os = [...]`` line belonging to
    some other table.
    """
    from haywire.core.library.haybale_toml import HAYBALE_TOML
    from haywire.core.publishing.manifest.errors import ManifestReadError
    from haywire.core.tomlio import edit_toml, read_toml

    module_dir = _module_dir_of(lib_dir)
    if module_dir is None:
        return []

    source = module_dir / HAYBALE_TOML
    # Parsed strictly, unlike the read-only probe above: a file this cannot
    # read is the condition the caller most needs reported. Skipping it
    # silently would report "repaired" on a file still holding a bad value.
    try:
        data = read_toml(source)
    except OSError as exc:
        raise ManifestReadError(f"Could not read {source}: {exc}") from exc
    except Exception as exc:
        raise ManifestReadError(f"Malformed TOML in {source}: {exc}") from exc

    os_decl = data.get("os")
    if not isinstance(os_decl, list):
        return []

    invalid, corrected = _partition_os_values(os_decl)
    if not invalid:
        return []

    with edit_toml(module_dir / HAYBALE_TOML) as doc:
        if corrected:
            doc["os"] = corrected
        else:
            # Every value was junk. An empty list means "all platforms", which
            # is what an absent key already means — so remove it rather than
            # leaving a declaration that says nothing.
            doc.pop("os", None)
    return invalid
