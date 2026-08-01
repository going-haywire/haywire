"""Pure string/tuple helpers for parsing and comparing PEP 440-ish version specs."""

import re


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


def _version_tuple(version: str) -> tuple[int, ...]:
    """Best-effort numeric tuple for version comparison. Non-numeric segments
    sort as 0 so pre-release tails don't crash the comparison; this gate's
    job is to surface obvious lag, not to enforce strict PEP 440."""
    parts = re.split(r"[.\-+]", version)
    out: list[int] = []
    for p in parts:
        m = re.match(r"(\d+)", p)
        out.append(int(m.group(1)) if m else 0)
    return tuple(out)
