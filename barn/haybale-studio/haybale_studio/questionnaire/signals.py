"""Signals published by the Questionnaire store and the post tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from haywire.api.workbench import RevealSignal, Signal


@dataclass(frozen=True)
class QuestionnaireChanged(Signal):
    """The Questionnaire, an answer or its status changed. Cross-session, payload-free.

    Subscribers re-read ``QuestionnaireState.current``.
    """

    cross_session: ClassVar[bool] = True


@dataclass(frozen=True, kw_only=True)
class RevealQuestionnaire(RevealSignal):
    """Bring the Questionnaire tab to the front in every session. Cross-session.

    Names no editor: ``QuestionnaireEditor`` answers it (see
    ``haywire.api.workbench.reveal_on``). A closed ASIDE opens. Send it with
    ``FarmhandContext.broadcast`` or ``SignalPeer.publish``.
    """

    cross_session: ClassVar[bool] = True
