"""Reading and parsing a library's pyproject.toml manifest."""

from __future__ import annotations

from pathlib import Path

import toml

from haywire_studio.packaging.share.manifest.errors import ManifestReadError
from haywire_studio.packaging.share.manifest.os_field import _read_os_field


def _read_raw_toml(pyproject_path: Path) -> tuple[str, dict]:
    """Read and parse a pyproject.toml with NO [tool.haywire].os validation.

    Returns (raw_text, parsed_dict). Raises ManifestReadError on I/O or parse
    failure. Deliberately bypasses :func:`read_manifest`, which raises
    InvalidOsDeclarationError on the exact invalid value the strip_os
    functions below exist to repair or describe.
    """
    try:
        content = pyproject_path.read_text()
    except OSError as exc:
        raise ManifestReadError(f"Could not read {pyproject_path}: {exc}") from exc
    try:
        data = toml.loads(content)
    except toml.TomlDecodeError as exc:
        raise ManifestReadError(f"Malformed TOML in {pyproject_path}: {exc}") from exc
    return content, data


def read_manifest(lib_dir: Path) -> dict:
    """Parse and validate a library pyproject. Raises ManifestReadError.

    For read-to-rewrite callers: refusing is the point, because the
    alternative is overwriting a file we could not understand. Also validates
    [tool.haywire].os, whose vocabulary is closed.
    """
    pyproject_path = lib_dir / "pyproject.toml"
    try:
        text = pyproject_path.read_text()
    except OSError as exc:
        raise ManifestReadError(f"Could not read {pyproject_path}: {exc}") from exc
    try:
        data = toml.loads(text)
    except toml.TomlDecodeError as exc:
        raise ManifestReadError(f"Malformed TOML in {pyproject_path}: {exc}") from exc
    _read_os_field(data, lib_dir)
    return data


def read_manifest_lenient(lib_dir: Path) -> dict:
    """Parse a library pyproject, returning {} on any failure.

    For read-to-report callers, where a corrupt manifest should still let the
    report name what is missing. Pinned by tests/test_share_drift.py:176.
    """
    try:
        return read_manifest(lib_dir)
    except ManifestReadError:
        return {}
