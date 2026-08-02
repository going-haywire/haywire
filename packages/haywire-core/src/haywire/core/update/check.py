"""Is a newer Haywire released? A PyPI query, nothing more."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from packaging.version import InvalidVersion, Version


@dataclass(frozen=True)
class UpdateStatus:
    """The answer to "is there a newer Haywire?".

    ``reachable`` is False only when PyPI could not be queried. "Couldn't
    reach PyPI" and "you're up to date" are DIFFERENT answers — collapsing
    them would tell the user a comforting lie about an unanswered question.
    """

    installed: str
    latest: str | None
    reachable: bool

    @property
    def available(self) -> bool:
        if not self.reachable or not self.latest or not self.installed:
            return False
        try:
            return Version(self.latest) > Version(self.installed)
        except InvalidVersion:
            return False


def _installed_version(dist: str) -> str:
    import importlib.metadata as _meta

    try:
        return _meta.version(dist)
    except _meta.PackageNotFoundError:
        return ""


def _latest_on_pypi(dist: str, timeout: float) -> str:
    """The newest non-prerelease version PyPI lists for *dist*."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{dist}/json", timeout=timeout) as resp:
        data = json.loads(resp.read())
    candidates: list[Version] = []
    for raw in data.get("releases", {}):
        try:
            parsed = Version(raw)
        except InvalidVersion:
            continue
        if not parsed.is_prerelease:
            candidates.append(parsed)
    return str(max(candidates)) if candidates else ""


def check_for_update(dist: str = "haywire-studio", *, timeout: float = 10.0) -> UpdateStatus:
    """Compare the installed *dist* against the newest release on PyPI."""
    installed = _installed_version(dist)
    try:
        latest = _latest_on_pypi(dist, timeout)
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return UpdateStatus(installed=installed, latest=None, reachable=False)
    return UpdateStatus(installed=installed, latest=latest or None, reachable=True)
