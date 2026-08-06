"""Pure string/tuple helpers for parsing and comparing PEP 440-ish version specs."""

import re

from packaging.version import InvalidVersion, Version


def _strip_specifier(spec: str) -> str:
    """Strip PEP 440 version operators and extras from a requirement string."""
    return re.split(r"[~>=<!;\s\[]", spec)[0]


def _parse_floor_spec(spec: str) -> tuple[str, str] | None:
    """Parse a requirement string into ``(operator, version)`` for lag-eligible
    floor operators. Returns None for operators we don't lag-check (==, <,
    !=, no operator, or anything we can't parse).

    Recognized lag-eligible operators: ``~=``, ``>=``, ``>``.
    """
    # Operators ordered longest-first so ``>=`` doesn't match as ``>``.
    for op in ("~=", ">=", ">"):
        idx = spec.find(op)
        if idx == -1:
            continue
        # Make sure the operator isn't a substring of a different operator —
        # find the FIRST run of operator chars in the spec and require it to
        # match exactly.
        m = re.search(r"([~>=<!]+)", spec)
        if m is None or m.group(1) != op:
            continue
        # Extract the version portion (everything after the operator, up to
        # any extras marker, semicolon, whitespace, or end-of-string).
        rest = spec[idx + len(op) :]
        version = re.split(r"[\s;,\[]", rest, maxsplit=1)[0].strip()
        if not version:
            return None
        return (op, version)
    return None


def version_lags(declared_floor: str, installed: str) -> bool:
    """Whether *installed* is strictly newer than *declared_floor*.

    Real PEP 440 comparison, not a numeric-tuple approximation. The former
    hand-rolled tuple sorted non-numeric segments as 0, so ``0.0.38rc1``
    compared *equal* to ``0.0.38`` and ``1.0`` sorted below ``1.0.0``. That was
    tolerable while lag was an internal gate; it is not tolerable now that the
    comparison's result is stated to the author as a fact about their project.

    Unparseable input returns False: an unreadable version is a gap in our
    metadata, and reporting lag we cannot substantiate is exactly the guessing
    this design removes.
    """
    try:
        return Version(installed) > Version(declared_floor)
    except InvalidVersion:
        return False
