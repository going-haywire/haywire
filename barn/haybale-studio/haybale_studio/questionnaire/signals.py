"""Signals published by the Questionnaire store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from haywire.core.signals import Signal


@dataclass(frozen=True)
class QuestionnaireChanged(Signal):
    """The Questionnaire, an answer or its status changed. Cross-session, payload-free.

    Subscribers re-read ``QuestionnaireState.current``.
    """

    cross_session: ClassVar[bool] = True
