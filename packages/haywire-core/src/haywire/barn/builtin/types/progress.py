"""The ``PROGRESS`` type: a node's progress, as shown by ``ProgressSettings``."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from haywire.barn.builtin import widget_keys
from haywire.core.types import type as type_decorator
from haywire.core.types.base import BaseType

from ..wires import DataWire


@type_decorator(
    wire_type=DataWire,
    label="Progress",
    description="Whether a node is busy, how far it is, and what it is doing",
    color="#80cbc4",
    default={"active": False, "fraction": None, "label": ""},
    widget_key=widget_keys.PROGRESS_WIDGET,
)
@dataclass
class PROGRESS(BaseType):
    """A node's progress: idle, busy without a known end, or busy at a known fraction.

    - Idle: `active` is `False`; the bar is empty.
    - Busy, no known end: `active` is `True` and `fraction` is `None`; the bar sweeps.
    - Busy at a fraction: `active` is `True` and `fraction` runs from 0 to 1; the bar fills.

    `label` names what the node is doing, such as "inferring".

    Nodes don't write this value directly: they declare a `progress_field()` on
    a `ProgressSettings` subclass and report through its `track()` and `busy()`.
    """

    active: bool = False
    fraction: float | None = None
    label: str = ""

    def __init__(self, **kwargs: Any) -> None:
        """Build a progress value from its parts; unknown keys are ignored, a fraction is clamped to 0..1."""
        # Settings seed a cell with ``value=``; tolerating unknown keys keeps that path working.
        self.active = bool(kwargs.get("active", False))
        fraction = kwargs.get("fraction")
        self.fraction = None if fraction is None else min(max(float(fraction), 0.0), 1.0)
        self.label = str(kwargs.get("label", "") or "")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "PROGRESS":
        """Rebuild from stored JSON; anything malformed becomes idle."""
        if not isinstance(data, dict):
            return cls()
        try:
            return cls(**data)
        except (TypeError, ValueError):
            return cls()
