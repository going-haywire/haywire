"""Volume keys: ``<library-id>:volume:<name>``, the identity a graph stores for a volume."""

from __future__ import annotations

import re

__all__ = ["PROJECT_KEY", "VOLUME_KEY_RE", "user_volume_key", "volume_name"]

VOLUME_KEY_RE = re.compile(r"^[a-z][a-z0-9-]*:volume:[a-z][a-z0-9_-]*$")
_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

PROJECT_KEY = "haywire-core:volume:project"
"""The built-in volume at the open project's folder."""


def user_volume_key(name: str) -> str:
    """Return the key of a volume a user adds, ``user:volume:<name>``.

    Raises:
        ValueError: If *name* is not lowercase letters, digits, ``-`` or ``_``,
            starting with a letter.
    """
    if not _NAME_RE.match(name):
        raise ValueError(
            f"Invalid volume name {name!r}: use lowercase letters, digits, '-' or '_',"
            " starting with a letter"
        )
    return f"user:volume:{name}"


def volume_name(key: str) -> str:
    """Return the name part of *key* (``models`` for ``haybale-models:volume:models``)."""
    return key.rsplit(":", 1)[-1]
