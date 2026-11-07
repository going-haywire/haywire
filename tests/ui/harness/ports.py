"""Which port a harness server binds, so parallel runs never share one.

Two kinds of parallel run meet here. pytest-xdist starts one harness server per
worker, and two checkouts of the repository (git worktrees) may run the browser
tier at the same time. Each checkout gets its own block of ports, derived from
its path, and each worker takes the next port in its checkout's block.

The blocks lie in 10000-19999: clear of the studio (8124 and up) and of the
operating systems' ephemeral ranges (32768 and up). Two checkouts share a block
with a chance of 1 in 500.
"""

import zlib
from pathlib import Path

PORTS_PER_CHECKOUT = 20
_FIRST_PORT = 10000
_BLOCKS = 500


def base_port(checkout: Path) -> int:
    """The first port of this checkout's block."""
    block = zlib.crc32(str(checkout).encode()) % _BLOCKS
    return _FIRST_PORT + block * PORTS_PER_CHECKOUT


def harness_port(checkout: Path, worker: str) -> int:
    """The port for one xdist worker (``gw0``, ``gw1``, ...; empty without xdist)."""
    digits = "".join(ch for ch in worker if ch.isdigit())
    return base_port(checkout) + (int(digits) if digits else 0)
