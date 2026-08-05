"""Validation and repair of a library's ``[tool.haywire].os`` declaration."""

from __future__ import annotations

import re
from pathlib import Path

from haywire.core.publishing.manifest.errors import InvalidOsDeclarationError

_DECLARABLE_OS_VALUES = frozenset({"macos", "windows", "linux"})


def _read_os_field(data: dict, lib_dir: Path) -> list[str]:
    """Read and validate [tool.haywire].os from a parsed pyproject.toml dict."""
    tool_haywire = data.get("tool", {}).get("haywire", {})
    os_decl = tool_haywire.get("os")
    if os_decl is None:
        return []
    if not isinstance(os_decl, list):
        raise InvalidOsDeclarationError(
            f"[tool.haywire].os in {lib_dir / 'pyproject.toml'} must be a list, "
            f"got {type(os_decl).__name__}."
        )
    validated: list[str] = []
    for value in os_decl:
        if not isinstance(value, str) or value not in _DECLARABLE_OS_VALUES:
            raise InvalidOsDeclarationError(
                f"Invalid os value {value!r} in {lib_dir / 'pyproject.toml'} [tool.haywire].os. "
                f"Declarable values: macos, windows, linux."
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


def invalid_os_values(lib_dir: Path) -> list[str]:
    """The invalid [tool.haywire].os values in lib_dir/pyproject.toml, read-only.

    Returns [] when the field is absent, not a list, or fully declarable.
    Used to compute a strip_os fix's label without mutating the file. Raises
    ManifestReadError if the file cannot be read or parsed.
    """
    from haywire.core.publishing.manifest.reader import _read_raw_toml

    _content, data = _read_raw_toml(lib_dir / "pyproject.toml")
    os_decl = data.get("tool", {}).get("haywire", {}).get("os")
    if not isinstance(os_decl, list):
        return []
    invalid, _corrected = _partition_os_values(os_decl)
    return invalid


def strip_undeclarable_os_values(lib_dir: Path) -> list[str]:
    """Rewrite [tool.haywire].os in lib_dir/pyproject.toml, keeping only
    declarable values (macos/windows/linux).

    Near-miss values (osx/darwin/mac -> macos, win/win32/nt -> windows) are
    corrected rather than dropped; anything else unmapped is removed outright
    — the vocabulary is closed and there is no honest way to guess intent for
    values like "other" or "freebsd".

    Rewrites the ``os = [...]`` line with a regex, following
    ``write_barn_versions``'s technique, so comments, key order, and
    formatting elsewhere in the file survive untouched.

    Returns the original non-declarable values found (i.e. the values that
    were not already declarable) — this is what a fix_label describes and
    what a caller reports as "removed", regardless of whether a value was
    corrected via near-miss mapping or dropped entirely.

    Raises ManifestReadError if the file cannot be read or parsed.
    """
    from haywire.core.publishing.manifest.reader import _read_raw_toml

    pyproject_path = lib_dir / "pyproject.toml"
    content, data = _read_raw_toml(pyproject_path)

    os_decl = data.get("tool", {}).get("haywire", {}).get("os")
    if not isinstance(os_decl, list):
        return []

    invalid, corrected = _partition_os_values(os_decl)
    if not invalid:
        return []

    new_list = ", ".join(f'"{v}"' for v in corrected)
    new_content, count = re.subn(
        r"^(os\s*=\s*)\[[^\]]*\]",
        rf"\g<1>[{new_list}]",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise InvalidOsDeclarationError(
            f"Could not locate an `os = [...]` line to rewrite in {pyproject_path}."
        )
    pyproject_path.write_text(new_content)
    return invalid
