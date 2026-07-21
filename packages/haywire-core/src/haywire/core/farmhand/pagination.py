"""Shared pagination helpers for Farmhand list-style tools.

Tools that return a slice of a larger collection (limit/offset) must tell the
caller when the payload is truncated — otherwise a client that only reads the
returned list silently misses the rest. `truncation_note` produces a suffix for
the tool's summary string; append it whenever a list is paginated.
"""

from __future__ import annotations


def truncation_note(shown: int, total: int, offset: int = 0) -> str:
    """A summary suffix describing a truncated page, or '' when nothing is hidden.

    `shown` is the number of items actually returned in this page, `total` the
    full collection size, `offset` the page's start index. Returns e.g.
    ' (showing 100 of 200 — pass limit/offset for more)' when items are hidden,
    and '' when the page already covers the whole collection.
    """
    end = offset + shown
    if offset == 0 and end >= total:
        return ""  # this page already covers the whole collection
    return f" (showing {offset + 1}-{end} of {total} — pass limit/offset for more)"
