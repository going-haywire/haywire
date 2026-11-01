"""Signals published by haybale-models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from haywire.core.signals import Signal


@dataclass(frozen=True)
class ModelsChanged(Signal):
    """The model index or the download queue changed. Cross-session, payload-free.

    Subscribers re-read ``ModelsState.index`` and ``ModelsState.queue``.
    """

    cross_session: ClassVar[bool] = True
