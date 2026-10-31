"""Read the sample bit depth of an AVIF file from its ``av1C`` box."""

from __future__ import annotations

import struct

_FULL_BOXES = frozenset({b"meta"})


def _boxes(data: bytes, start: int, end: int):
    """Yield ``(type, payload_start, payload_end)`` for each ISOBMFF box in ``data[start:end]``."""
    pos = start
    while pos + 8 <= end:
        size, kind = struct.unpack_from(">I4s", data, pos)
        header = 8
        if size == 1:
            if pos + 16 > end:
                return
            (size,) = struct.unpack_from(">Q", data, pos + 8)
            header = 16
        elif size == 0:
            size = end - pos
        if size < header or pos + size > end:
            return
        yield kind, pos + header, pos + size
        pos += size


def _find_av1c(data: bytes, start: int, end: int, path: tuple[bytes, ...]) -> int | None:
    for kind, lo, hi in _boxes(data, start, end):
        if path and kind == path[0]:
            if kind in _FULL_BOXES:
                lo += 4
            found = _find_av1c(data, lo, hi, path[1:])
            if found is not None:
                return found
        elif not path and kind == b"av1C":
            return lo if hi - lo >= 3 else None
    return None


def avif_bit_depth(data: bytes) -> int | None:
    """Return 8, 10 or 12 from the first ``av1C`` box of an AVIF file; ``None`` if absent or unparseable."""
    pos = _find_av1c(data, 0, len(data), (b"meta", b"iprp", b"ipco"))
    if pos is None:
        return None
    flags = data[pos + 2]
    high, twelve = bool(flags & 0x40), bool(flags & 0x20)
    return 12 if high and twelve else 10 if high else 8
