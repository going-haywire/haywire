"""Generating ``[project]`` metadata from a library's ``haybale.toml``.

``haybale.toml`` is canon for everything descriptive, including ``name`` and
``version``. The PEP 621 fields exist so the wheel is a well-formed package —
PyPI, ``uv`` and ``pip`` read them, and Haywire does not — so they are
*projected* out of it rather than authored twice.

``pyproject.toml`` keeps one canonical field of its own — ``[project]
dependencies`` — plus the packaging machinery no other file can own
(``build-system``, ``entry-points``, ``[tool.hatch]``). None of that is
touched here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from haywire.core.library.dep_detect import find_module_dir
from haywire.core.library.haybale_toml import HAYBALE_TOML, read_raw
from haywire.core.publishing.manifest.errors import ManifestReadError
from haywire.core.tomlio import edit_toml, read_toml

__all__ = ["PROJECT_FIELDS", "pyproject_drift", "sync_pyproject_from_haybale"]

#: ``[project]`` keys generated from haybale.toml, and where each comes from.
#: ``haybale.toml`` is canon for all of these; ``pyproject.toml`` carries the
#: generated copy because pip, uv and PyPI read that file and cannot read this
#: one. Drift is therefore reported against pyproject, never the other way.
PROJECT_FIELDS = {
    "name": "name",
    "version": "version",
    "description": "description",
    "keywords": "tags",
}

#: ``[project.urls]`` labels, and the haybale.toml key each is generated from.
#: ``Source`` comes from ``origin``, which the share wizard writes from the git
#: remote rather than from anything an author types.
URL_FIELDS = {
    "Homepage": "homepage_url",
    "Documentation": "documentation_url",
    "Issues": "issues_url",
    "Source": "origin",
}

#: Emitted only when a ``[deprecated]`` block is present. PEP 621 has no
#: deprecation field and one cannot be invented — unknown ``[project]`` keys are
#: a spec violation — so this classifier is the ecosystem's only signal.
_DEPRECATED_CLASSIFIER = "Development Status :: 7 - Inactive"


def _declared(lib_dir: Path) -> dict[str, Any]:
    module_dir = find_module_dir(lib_dir)
    if module_dir is None:
        raise ManifestReadError(f"No Python package found in {lib_dir}; cannot read {HAYBALE_TOML}.")
    source = module_dir / HAYBALE_TOML
    if not source.is_file():
        raise ManifestReadError(f"{source} not found.")
    return read_raw(module_dir)


def _projected(declared: dict[str, Any]) -> dict[str, Any]:
    """What ``[project]`` should hold, given a parsed haybale.toml.

    Absent and empty are the same thing: a key with no value is omitted rather
    than written as ``""``, so a generated file is indistinguishable from one an
    author wrote by hand.
    """
    out: dict[str, Any] = {}
    for project_key, haybale_key in PROJECT_FIELDS.items():
        value = declared.get(haybale_key)
        if value:
            out[project_key] = list(value) if isinstance(value, list) else value

    # PEP 621 authors carry {name, email} and have no URL slot, so an author's
    # url survives in haybale.toml and reaches the marketstall row, but has
    # nowhere to go here. Dropping it is the honest projection.
    authors = declared.get("authors")
    if isinstance(authors, list):
        names = [
            {"name": entry["name"]} for entry in authors if isinstance(entry, dict) and entry.get("name")
        ]
        if names:
            out["authors"] = names

    if isinstance(declared.get("deprecated"), dict):
        out["classifiers"] = [_DEPRECATED_CLASSIFIER]

    urls = {
        label: declared[key]
        for label, key in URL_FIELDS.items()
        if isinstance(declared.get(key), str) and declared[key]
    }
    if urls:
        out["urls"] = urls
    return out


def pyproject_drift(lib_dir: Path) -> dict[str, tuple[Any, Any]]:
    """``{field: (current, generated)}`` for every generated field that differs.

    Read-only. Lets a caller render *what* a sync would change before doing it —
    the write is unconditional, but it should never be a surprise.
    """
    declared = _declared(lib_dir)
    want = _projected(declared)

    pyproject = lib_dir / "pyproject.toml"
    try:
        data = read_toml(pyproject)
    except OSError as exc:
        raise ManifestReadError(f"Could not read {pyproject}: {exc}") from exc
    except Exception as exc:
        raise ManifestReadError(f"Malformed TOML in {pyproject}: {exc}") from exc

    project = data.get("project", {})
    current_urls = dict(project.get("urls", {}) or {})

    drift: dict[str, tuple[Any, Any]] = {}
    for key in (*PROJECT_FIELDS, "authors", "classifiers"):
        have = project.get(key)
        want_value = want.get(key)
        # tomlkit containers compare unequal to plain lists/dicts of the same
        # content, so normalise both sides before comparing.
        if _plain(have) != _plain(want_value):
            drift[key] = (_plain(have), _plain(want_value))

    if _plain(current_urls) != _plain(want.get("urls", {})):
        drift["urls"] = (_plain(current_urls), _plain(want.get("urls", {})))
    return drift


def _plain(value: Any) -> Any:
    """Strip tomlkit's container types so equality compares content."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if value is None:
        return None
    return str(value) if not isinstance(value, (bool, int, float)) else value


def sync_pyproject_from_haybale(lib_dir: Path) -> list[str]:
    """Write the generated ``[project]`` fields. Returns the field names changed.

    Comment-preserving: ``pyproject.toml`` is hand-authored for the fields this
    does *not* own, so it is edited in place rather than rebuilt.
    """
    changed = list(pyproject_drift(lib_dir))
    if not changed:
        return []

    declared = _declared(lib_dir)
    want = _projected(declared)
    pyproject = lib_dir / "pyproject.toml"

    with edit_toml(pyproject) as doc:
        project = doc.setdefault("project", {})
        for key in (*PROJECT_FIELDS, "authors", "classifiers"):
            value = want.get(key)
            if value:
                project[key] = value
            else:
                project.pop(key, None)

        urls = want.get("urls") or {}
        if urls:
            project["urls"] = urls
        else:
            project.pop("urls", None)

    return changed
