"""Filters over catalog rows: what a row is, what to offer, and which rows a selection keeps."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from haywire.core.catalog import CatalogEntry

FILTER_FIELDS: tuple[tuple[str, str], ...] = (
    ("library", "Library"),
    ("purpose", "Purpose"),
    ("tags", "Tags"),
    ("architecture", "Architecture"),
    ("scale", "Scale"),
    ("commercial", "Commercial use"),
    ("status", "Status"),
)
"""The filter fields, as ``(key, label)``, in the order they are shown."""

COMMERCIAL = "commercial"
NON_COMMERCIAL = "non-commercial"
ON_THIS_MACHINE = "on this machine"
NEEDED = "needed"
AVAILABLE = "available"


def entry_facts(entry: CatalogEntry, *, on_machine: bool, needed: bool) -> dict[str, set[str]]:
    """Return the values one catalog row has in each filter field.

    A field the entry has no value for holds an empty set. Status belongs to the row: the variants
    of one entry can differ.

    Args:
        entry: The row's entry.
        on_machine: Whether the variant's files are found on this machine.
        needed: Whether an open graph misses this variant.
    """
    status = {ON_THIS_MACHINE if on_machine else AVAILABLE}
    if needed:
        status.add(NEEDED)
    library = entry.library.label or entry.library.name
    return {
        "library": {library} if library else set(),
        "purpose": set(entry.purpose),
        "tags": set(entry.tags),
        "architecture": {entry.architecture} if entry.architecture else set(),
        "scale": {f"{entry.scale}x"} if entry.scale else set(),
        "commercial": {COMMERCIAL if entry.commercial else NON_COMMERCIAL},
        "status": status,
    }


def values_on_offer(rows: Iterable[Mapping[str, set[str]]]) -> dict[str, list[str]]:
    """Return the sorted values of every filter field, by field key; a field without values holds ``[]``.

    Scale sorts by number.
    """
    seen: dict[str, set[str]] = {}
    for facts in rows:
        for key, values in facts.items():
            seen.setdefault(key, set()).update(values)
    offered: dict[str, list[str]] = {}
    for key, _label in FILTER_FIELDS:
        values = seen.get(key, set())
        offered[key] = sorted(values, key=_scale_order if key == "scale" else str.lower)
    return offered


def row_matches(facts: Mapping[str, set[str]], selected: Mapping[str, set[str]]) -> bool:
    """Return whether a row holds a selected value in every field that has a selection.

    A field with nothing selected keeps every row.
    """
    return all(not chosen or facts.get(key, set()) & chosen for key, chosen in selected.items())


def _scale_order(value: str) -> int:
    return int(value.rstrip("x"))
