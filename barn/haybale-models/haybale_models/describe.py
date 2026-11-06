"""What a catalog entry is, in words: a one-line summary, a plain-text description, and search text.

Used wherever a person chooses between models (the model picker, the Models editor),
so both describe an entry the same way.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.catalog import CatalogEntry

from haybale_models.filters import COMMERCIAL, NON_COMMERCIAL

_NOT_NON_COMMERCIAL = re.compile(r"(?<!non-)commercial")

__all__ = ["entry_description", "entry_search_text", "entry_summary", "search_matches"]

#: Tags shown in a summary line; the rest are counted (``+2``).
SUMMARY_TAGS = 4

#: Longest description shown in a tip, in characters; longer text ends in ``…``.
DESCRIPTION_LIMIT = 400

_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MARKUP = re.compile(r"[*_`#>]+")


def entry_summary(entry: CatalogEntry, *, scale: bool = True) -> str:
    """Return what tells *entry* apart at a glance, such as ``4x · ESRGAN · anime, photo +2``.

    Scale, architecture and the first tags, each left out when the entry has none.
    ``scale=False`` leaves the scale out, for a place that already shows it.
    """
    parts: list[str] = []
    if scale and entry.scale:
        parts.append(f"{entry.scale}x")
    if entry.architecture:
        parts.append(entry.architecture)
    if entry.tags:
        shown = ", ".join(entry.tags[:SUMMARY_TAGS])
        rest = len(entry.tags) - SUMMARY_TAGS
        parts.append(f"{shown} +{rest}" if rest > 0 else shown)
    return " · ".join(parts)


def entry_description(entry: CatalogEntry) -> str:
    """Return *entry*'s description as plain text for a tip, with purpose, author and licence below.

    Markdown links keep their text, other markup is dropped, and a description longer
    than ``DESCRIPTION_LIMIT`` characters is cut at a word and ends in ``…``.
    """
    text = _plain(entry.description)
    if len(text) > DESCRIPTION_LIMIT:
        text = text[:DESCRIPTION_LIMIT].rsplit(" ", 1)[0] + " …"
    facts = []
    if entry.purpose:
        facts.append("Purpose: " + ", ".join(entry.purpose))
    if entry.author:
        facts.append("By " + entry.author)
    if licence := entry_licence_text(entry):
        facts.append("Licence: " + licence)
    return "\n".join(part for part in (text, " · ".join(facts)) if part)


def entry_licence_text(entry: CatalogEntry) -> str:
    """Return *entry*'s licence, followed by ``non-commercial`` unless its author states otherwise.

    Empty for a commercial entry without a licence.
    """
    parts = [entry.license, "" if entry.commercial else NON_COMMERCIAL]
    return " · ".join(part for part in parts if part)


def entry_search_text(entry: CatalogEntry) -> str:
    """Return the lower-case text a search over *entry* matches; see :func:`search_matches`.

    Its name, scale (``4x``), architecture, purpose, tags, licence, commercial use and description.
    """
    words = [
        entry.name,
        f"{entry.scale}x" if entry.scale else "",
        entry.architecture,
        *entry.purpose,
        *entry.tags,
        entry.license,
        COMMERCIAL if entry.commercial else NON_COMMERCIAL,
        _plain(entry.description),
    ]
    return " ".join(w for w in words if w).lower()


def search_matches(query: str, text: str) -> bool:
    """Return whether every word of *query* appears somewhere in *text*, ignoring case.

    A word may be part of a longer one, in any order. An empty query matches everything. The word
    ``commercial`` does not match ``non-commercial``.
    """
    text = text.lower()
    return all(
        _NOT_NON_COMMERCIAL.search(text) if word == COMMERCIAL else word in text
        for word in query.lower().split()
    )


def _plain(markdown: str) -> str:
    text = _LINK.sub(r"\1", markdown or "")
    text = _MARKUP.sub("", text)
    return " ".join(text.split())
