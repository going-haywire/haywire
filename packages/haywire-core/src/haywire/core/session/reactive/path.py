"""ReactivePath: a typed reference to a reactive field on a class.

Phase 1: data class only. Class-level attribute access on a SessionContext
that uses `reactive_field()` returns one of these. Phase 2's `@reads`
decorator records these as method metadata for drift verification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReactivePath:
    """Identifies a single reactive field on a class.

    `owner` is the class that defines the field. `attr` is the attribute
    name. Two ReactivePaths with the same (owner, attr) compare equal and
    hash equal, so they can be used as dict keys.
    """

    owner: type
    attr: str

    def __repr__(self) -> str:
        return f"{self.owner.__name__}.{self.attr}"
