"""Current-OS detection — spec §2.1 mapping table.

`platform.system()` returns OS-family strings; we map them to the four-value
runtime vocabulary (macos | windows | linux | other). `other` is a runtime-only
sentinel — never a declarable value (haywire share rejects it). The absent
default on Haybale.os is the "supports all platforms" case.
"""

from __future__ import annotations

import platform
from typing import Literal

from haywire.core.marketstall.types import Haybale

OsName = Literal["macos", "windows", "linux", "other"]


def current_os() -> OsName:
    """Map `platform.system()` to the four-value runtime OS vocabulary."""
    name = platform.system()
    if name == "Darwin":
        return "macos"
    if name == "Windows":
        return "windows"
    if name == "Linux":
        return "linux"
    return "other"


def haybale_supports_current_os(h: Haybale) -> bool:
    """True iff `h.os` is empty (= all platforms) or contains current_os()."""
    if not h.os:
        return True
    return current_os() in h.os
