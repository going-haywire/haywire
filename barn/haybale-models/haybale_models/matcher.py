"""Variant matching: which resources fit a preference, which entries fit a filter."""

from collections.abc import Sequence
from typing import Any

from haywire.core.models import CatalogEntry, Resource

#: Ordered tag sets, best first. A tag a resource lacks is a wildcard.
Preference = list[dict[str, str]]


def matches(resource: Resource, tagset: dict[str, str]) -> bool:
    """Whether every tag in ``tagset`` is absent from the resource (wildcard) or equal."""
    tags = resource.tags()
    return all(tags.get(key, value) == value for key, value in tagset.items())


def candidates(resources: Sequence[Resource], preference: Preference) -> list[tuple[int, Resource]]:
    """Rank resources by the first tag set each matches; an empty preference is ``[{}]``.

    The result is ordered by rank; each resource appears once, at its best rank.
    """
    tagsets = preference or [{}]
    ranked: list[tuple[int, Resource]] = []
    taken: set[int] = set()
    for rank, tagset in enumerate(tagsets):
        for index, resource in enumerate(resources):
            if index not in taken and matches(resource, tagset):
                taken.add(index)
                ranked.append((rank, resource))
    return ranked


def entry_matches(entry: CatalogEntry, filter: dict[str, list[Any]]) -> bool:  # noqa: A002
    """Whether the entry satisfies a port ``filter`` (entry field -> allowed values).

    List-valued fields (``purpose``, ``tags``) match on any overlap; scalars on
    membership. A field the entry does not have never matches.
    """
    fields = entry.fields()
    for name, allowed in filter.items():
        if name not in fields:
            return False
        value = fields[name]
        if isinstance(value, list):
            if not any(item in allowed for item in value):
                return False
        elif value not in allowed:
            return False
    return True
