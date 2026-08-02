"""Rewriting the root project's framework pins.

Only the ROOT pyproject.toml is touched — every lockstep dist is declared
there. A scaffolded barn library's own ``haywire-core`` floor is left alone:
``~=0.0.31`` already admits ``0.0.34`` (``~=X.Y.Z`` ≡ ``>=X.Y.Z, ==X.Y.*``),
so it is not a hazard for patch moves. It only bites at ``0.1.0``.
"""

from __future__ import annotations

import re
from pathlib import Path

import toml
from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

# Dists released in lockstep with the framework. A pin bump moves all of them.
LOCKSTEP_DISTS: tuple[str, ...] = ("haywire-studio", "haywire-core", "haybale-marketplace")


def _installed_version(dist: str) -> str:
    import importlib.metadata as _meta

    try:
        return _meta.version(dist)
    except _meta.PackageNotFoundError:
        return ""


def _dep_name(entry: str) -> str:
    head = entry.split(";", 1)[0].split(" @ ", 1)[0]
    return re.split(r"[\[<>=!~ ]", head, maxsplit=1)[0].strip()


def _operator(entry: str, name: str) -> str:
    """The operator the author already chose (``~=`` / ``>=`` / ``==``).

    Preserved rather than normalized: an update moves the version, never the
    author's declared compatibility policy.
    """
    tail = entry[len(name) :].strip()
    for op in ("~=", ">=", "==", ">"):
        if tail.startswith(op):
            return op
    return ">="


def rewrite_pins(pyproject_path: Path, version: str) -> str:
    """The new file TEXT with every lockstep pin moved to *version*.

    Returns text rather than writing, because the conflict check needs
    write-resolve-restore: it holds the original in memory, writes this,
    resolves, and restores in a ``finally``.
    """
    data = toml.loads(pyproject_path.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", []) or []
    lockstep = {d.lower() for d in LOCKSTEP_DISTS}

    new_deps: list[str] = []
    for entry in deps:
        name = _dep_name(entry)
        if name.lower() in lockstep:
            new_deps.append(f"{name}{_operator(entry, name)}{version}")
        else:
            new_deps.append(entry)
    data.setdefault("project", {})["dependencies"] = new_deps
    return toml.dumps(data)


def declared_floor(pyproject_path: Path, dist: str = "haywire-studio") -> str:
    """The version *dist* is pinned to in the root pyproject, or "".

    Parsed with ``Requirement`` so the specifier's structure — not its raw
    text — decides what the floor is.
    """
    if not pyproject_path.is_file():
        return ""
    data = toml.loads(pyproject_path.read_text(encoding="utf-8"))
    for entry in data.get("project", {}).get("dependencies", []) or []:
        if _dep_name(entry).lower() != dist.lower():
            continue
        try:
            requirement = Requirement(entry)
        except InvalidRequirement:
            return ""
        floors = [s.version for s in requirement.specifier if s.operator in (">=", "~=", "==")]
        return max(floors, key=Version) if floors else ""
    return ""


def startup_mismatch(pyproject_path: Path, dist: str = "haywire-studio") -> str | None:
    """The "environment wasn't synced" notice, or None when there is nothing to say.

    Derived, never stored: a stored marker goes stale (hand-edited pin, upgrade
    by other means), whereas pin-vs-installed IS the condition and is always
    current. Success needs no acknowledgement — the notice simply stops
    appearing.

    What this really catches is a BYPASSED sync (``--no-sync``/``UV_FROZEN``, a
    bare ``.venv/bin/haywire``, an IDE run config), not a failed one: if the
    resolve fails at launch, studio never starts and there is no UI to report
    it. That population — developer machines — is exactly where the original
    version skew arose.
    """
    floor = declared_floor(pyproject_path, dist)
    installed = _installed_version(dist)
    if not floor or not installed:
        return None
    try:
        if Version(floor) <= Version(installed):
            return None
    except InvalidVersion:
        return None
    return (
        f"pyproject.toml requests {floor} but {installed} is running — this "
        f"environment wasn't synced. Launch with `uv run haywire`."
    )
