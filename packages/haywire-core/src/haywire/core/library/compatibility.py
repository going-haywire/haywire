"""Compatibility Warnings — advisory, author-declared notices that a graph
saved by an older library version may not reflect a later behavioural change.

This module is pure logic: the dataclass an author writes, semver parsing,
and the CompatibilityChecker that decides which warnings fire for a saved
graph. It never mutates graph data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class SemverError(ValueError):
    """Raised when a version string is not strict MAJOR.MINOR.PATCH semver."""


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse a strict dotted ``MAJOR.MINOR.PATCH`` string into a comparable tuple.

    Raises:
        SemverError: if the string is not exactly three dot-separated integers.
    """
    match = _SEMVER_RE.match(version.strip()) if isinstance(version, str) else None
    if match is None:
        raise SemverError(f"version {version!r} is not valid semver; use 'MAJOR.MINOR.PATCH', e.g. '0.0.14'")
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


@dataclass
class CompatibilityWarning:
    """An author-declared advisory about a behavioural change in a library.

    Fields:
        version: The version in which the change landed (strict semver string).
            A graph whose saved node was stored with a library version *below*
            this value triggers the warning. This is a historical fact and is
            ALWAYS explicit — never derived from the library's current version.
        component: A node class exposing ``class_identity.registry_key`` (or a
            plain registry_key string), or ``None`` for a library-wide warning.
            A non-None component is matched against saved nodes by registry_key.
        message: Human-readable description of what changed and what to review.
    """

    version: str
    component: Optional[Any]
    message: str
    version_tuple: tuple[int, int, int] = field(init=False)

    def __post_init__(self) -> None:
        # Fail loud and early (at library load) on a malformed authored version.
        self.version_tuple = parse_semver(self.version)


@dataclass(frozen=True)
class SavedNode:
    """The minimal facts the checker needs about one node read from a file."""

    node_id: str
    registry_key: str
    library_id: str
    saved_version: Optional[str]  # None for files predating the library.version field


@dataclass(frozen=True)
class CompatibilityFinding:
    """A resolved warning to apply. node_id=None means a library-wide finding."""

    node_id: Optional[str]
    message: str
    source_version: Optional[str]


# Yields the append-only CompatibilityWarning history for a given library id.
HistoryLookup = Callable[[str], list[CompatibilityWarning]]


def _component_registry_key(component: Any) -> Optional[str]:
    """Resolve a warning's component to a registry_key, or None for library-wide.

    Accepts either a class exposing ``class_identity.registry_key`` or a plain
    registry_key string (used in unit tests and equally valid for authors).
    """
    if component is None:
        return None
    if isinstance(component, str):
        return component
    identity = getattr(component, "class_identity", None)
    return getattr(identity, "registry_key", None)


def _is_older(saved_version: Optional[str], warning: CompatibilityWarning) -> bool:
    """True if the saved version is strictly below the warning's version.

    A missing saved version is treated as infinitely old (every warning fires).
    """
    if saved_version is None:
        return True
    try:
        return parse_semver(saved_version) < warning.version_tuple
    except SemverError:
        # A saved file with a junk version is treated as old, not crashed on.
        return True


class CompatibilityChecker:
    """Decides which Compatibility Warnings fire for a set of saved nodes.

    Pure logic, no UI and no graph mutation. ``history_lookup`` supplies a
    library's append-only warning list by id (in production, from the live
    LibraryRegistry; in tests, from a dict).
    """

    def __init__(self, history_lookup: HistoryLookup):
        self._history = history_lookup

    def check(self, saved_nodes: Iterable[SavedNode]) -> list[CompatibilityFinding]:
        saved_list = list(saved_nodes)
        findings: list[CompatibilityFinding] = []

        # Collect library ids present in the graph (preserve first-seen order).
        lib_ids: list[str] = []
        for node in saved_list:
            if node.library_id not in lib_ids:
                lib_ids.append(node.library_id)

        for lib_id in lib_ids:
            warnings = self._history(lib_id)
            if not warnings:
                continue
            nodes_for_lib = [n for n in saved_list if n.library_id == lib_id]

            for warning in warnings:
                target_key = _component_registry_key(warning.component)

                if target_key is None:
                    # Library-wide: one finding if ANY node is below the version.
                    if any(_is_older(n.saved_version, warning) for n in nodes_for_lib):
                        findings.append(
                            CompatibilityFinding(
                                node_id=None,
                                message=warning.message,
                                source_version=None,
                            )
                        )
                    continue

                # Node-specific: one finding per matched node below the version.
                for node in nodes_for_lib:
                    if node.registry_key == target_key and _is_older(node.saved_version, warning):
                        findings.append(
                            CompatibilityFinding(
                                node_id=node.node_id,
                                message=warning.message,
                                source_version=node.saved_version,
                            )
                        )

        return findings
