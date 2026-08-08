"""Read a library's PEP 621 metadata back out of its installed distribution.

``pyproject.toml`` is the single source for version, description, authors,
keywords and URLs. The build backend copies them into the wheel's ``METADATA``,
so at decoration time the values come from here rather than from
``@library(...)`` kwargs — which is what stops the two from drifting.

The header shapes are not obvious and were verified against a real wheel:

* ``{name = "X"}`` renders as ``Author: X``, but ``{name = "X", email = "…"}``
  renders as ``Author-email: X <…>``. A list mixing both **splits across the two
  headers**, so reading only one silently loses authors.
* ``Keywords`` is a single comma-joined string, alphabetized by the backend —
  not repeated headers, and not in the order the author wrote them.
* ``Project-URL`` is one header per entry, ``"Label, URL"``, labels verbatim.
"""

from __future__ import annotations

import importlib.metadata
from email.utils import getaddresses
from typing import Protocol


class _Headers(Protocol):
    """The read surface both ``email.message.Message`` and ``PackageMetadata`` share.

    ``importlib.metadata`` declares ``.metadata`` as ``PackageMetadata``, not as
    ``Message``, so typing the parsers against the concrete class would make the
    real caller a type error. They only ever read headers.
    """

    def get(self, name: str, failobj: None = None) -> str | None: ...

    def get_all(self, name: str, failobj: None = None) -> list[str] | None: ...


#: Placeholder some backends write for an absent field.
_PLACEHOLDERS = {"", "UNKNOWN"}


def _clean(value: str | None) -> str:
    """Normalise a header value, treating backend placeholders as absent."""
    text = (value or "").strip()
    return "" if text in _PLACEHOLDERS else text


def _parse_authors(md: _Headers) -> list[str]:
    """Every declared author's display name, across both header spellings."""
    names = [n for n in (_clean(str(v)) for v in md.get_all("Author") or []) if n]
    for raw in md.get_all("Author-email") or []:
        for name, address in getaddresses([str(raw)]):
            display = name.strip() or address.strip()
            if display:
                names.append(display)
    return names


def _parse_urls(md: _Headers) -> dict[str, str]:
    """``{label: url}`` from ``Project-URL`` headers. Malformed entries skipped."""
    urls: dict[str, str] = {}
    for entry in md.get_all("Project-URL") or []:
        label, sep, target = str(entry).partition(", ")
        if sep and label.strip() and target.strip():
            urls[label.strip()] = target.strip()
    return urls


def _parse_keywords(md: _Headers) -> list[str]:
    """``Keywords`` is comma-joined; order is the backend's, not the author's."""
    raw = _clean(md.get("Keywords"))
    return [k.strip() for k in raw.split(",") if k.strip()]


def distribution_fields(dist_name: str) -> dict[str, object]:
    """The ``LibraryMetadata`` fields carried by *dist_name*'s metadata.

    Returns ``{}`` when the distribution is not installed — the caller decides
    whether that is fatal. Keys are omitted rather than set empty when a field
    is absent, so a caller can splat this over defaults without clobbering them.
    """
    try:
        md = importlib.metadata.distribution(dist_name).metadata
    except importlib.metadata.PackageNotFoundError:
        return {}

    urls = _parse_urls(md)
    fields: dict[str, object] = {}

    for key, value in (
        ("version", _clean(md.get("Version"))),
        ("description", _clean(md.get("Summary"))),
        ("homepage_url", urls.get("Homepage", "")),
        ("documentation_url", urls.get("Documentation", "")),
        ("author_url", urls.get("Author", "")),
        ("issues_url", urls.get("Issues", "")),
    ):
        if value:
            fields[key] = value

    authors = _parse_authors(md)
    if authors:
        fields["authors"] = authors
    keywords = _parse_keywords(md)
    if keywords:
        fields["tags"] = keywords

    return fields
