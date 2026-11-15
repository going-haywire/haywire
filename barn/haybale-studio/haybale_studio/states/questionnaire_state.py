"""QuestionnaireState — the studio's one current Questionnaire, its answers and its status."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from haywire.core.errors.ledger import get_error_ledger
from haywire.core.state.base import AppState
from haywire.core.state.decorator import state
from haywire.core.storage import library_storage_dir

from haybale_studio.questionnaire.definition import (
    answer_keys,
    failed_checks,
    missing_required,
    unanswered,
)
from haybale_studio.questionnaire.signals import QuestionnaireChanged

logger = logging.getLogger(__name__)

OPEN = "open"
SUBMITTED = "submitted"


@dataclass
class Questionnaire:
    """A posted Questionnaire with its answers, as stored on disk."""

    id: str
    definition: dict
    answers: dict[str, Any] = field(default_factory=dict)
    """Question name → answer; a Check's answer is ``{"verdict": …, "note": …}``."""
    status: str = OPEN
    """``"open"`` while it takes answers, ``"submitted"`` after."""
    incomplete: bool = False
    """Whether it was submitted with visible questions unanswered."""
    posted_at: str = ""
    posted_by: Optional[str] = None
    submitted_at: Optional[str] = None
    submitted_by: Optional[str] = None
    user_agent: Optional[str] = None
    ledger_seq_posted: int = 0
    """The error ledger's cursor when it was posted."""
    ledger_seq_submitted: Optional[int] = None
    """The error ledger's cursor when it was submitted."""

    @property
    def title(self) -> str:
        """Return the definition's title, or its id."""
        return str(self.definition.get("title") or self.id)

    @property
    def submitted(self) -> bool:
        """Return whether it was submitted and takes no more answers."""
        return self.status == SUBMITTED


class QuestionnaireClosed(RuntimeError):
    """An answer or a submit reached a Questionnaire that is missing or already submitted."""


class RequiredUnanswered(ValueError):
    """A submit left required questions unanswered; ``names`` lists them."""

    def __init__(self, names: list[str]) -> None:
        super().__init__(f"Required questions unanswered: {', '.join(names)}")
        self.names = names


@state(
    label="Questionnaire",
    description="The Questionnaire an agent posted for a live check, its answers and its status",
)
class QuestionnaireState(AppState):
    """Holds the current Questionnaire and stores every change under the library's storage folder.

    One Questionnaire is current at a time; a new post replaces it, and earlier
    ones stay on disk under `questionnaires/`. Every change reaches every open
    studio session.

    ```python
    q = state.post(definition, principal="agent")
    state.set_answer("login", {"verdict": "fail", "note": "button greyed out"})
    state.submit(principal="tester", user_agent="Firefox", anyway=True)
    state.findings()  # {"id": ..., "status": "submitted", "answers": {...}, ...}
    ```
    """

    def __init__(self) -> None:
        super().__init__()
        self.current: Optional[Questionnaire] = None
        """The Questionnaire on show, or ``None`` before the first post."""
        self._folder: Optional[Path] = None

    @property
    def folder(self) -> Path:
        """Return (and create) the folder that holds every posted Questionnaire."""
        if self._folder is None:
            self._folder = library_storage_dir(__name__) / "questionnaires"
        self._folder.mkdir(parents=True, exist_ok=True)
        return self._folder

    def on_enable(self) -> None:
        """Load the Questionnaire that was current, if any."""
        # Only the current Questionnaire is ever written, so it is the newest file.
        files = sorted(self.folder.glob("*.json"), key=lambda path: path.stat().st_mtime_ns)
        if not files:
            return
        try:
            self.current = Questionnaire(**json.loads(files[-1].read_text(encoding="utf-8")))
        except Exception:
            logger.exception("could not load questionnaire %s", files[-1])

    # -- changes -------------------------------------------------------------

    def post(self, definition: dict, principal: Optional[str]) -> Questionnaire:
        """Make ``definition`` the current Questionnaire, replacing the one before.

        ``definition`` must already have passed
        :func:`haybale_studio.questionnaire.definition.validate`.
        """
        now = datetime.now(timezone.utc)
        slug = re.sub(r"[^a-z0-9]+", "-", str(definition.get("title", "")).lower()).strip("-")[:40]
        self.current = Questionnaire(
            id=self._free_id(f"{now:%Y%m%d-%H%M%S}-{slug or 'questionnaire'}"),
            definition=definition,
            posted_at=now.isoformat(timespec="seconds"),
            posted_by=principal,
            ledger_seq_posted=get_error_ledger().current_seq,
        )
        self._changed()
        return self.current

    def set_answer(self, name: str, value: Any) -> None:
        """Store the answer to question ``name``; ``None`` clears it.

        ``name`` is a question's name, or ``<name>-Comment`` for the text of a
        choice question's "Other" item.

        Raises:
            QuestionnaireClosed: If there is no current Questionnaire or it was submitted.
            KeyError: If no question has that name.
        """
        q = self._open()
        if name not in answer_keys(q.definition):
            raise KeyError(name)
        if value is None:
            q.answers.pop(name, None)
        else:
            q.answers[name] = value
        self._changed()

    def submit(self, *, principal: Optional[str], user_agent: Optional[str], anyway: bool = False) -> None:
        """Submit the current Questionnaire; it takes no more answers after.

        Args:
            principal: Who submits; ``None`` when authentication is off.
            user_agent: The submitting browser's user agent string.
            anyway: Submit even with required questions unanswered.

        Raises:
            QuestionnaireClosed: If there is no current Questionnaire or it was submitted.
            RequiredUnanswered: If ``anyway`` is false and required questions are unanswered.
        """
        q = self._open()
        missing = missing_required(q.definition, q.answers)
        if missing and not anyway:
            raise RequiredUnanswered(missing)
        q.status = SUBMITTED
        q.incomplete = bool(unanswered(q.definition, q.answers))
        q.submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        q.submitted_by = principal
        q.user_agent = user_agent
        q.ledger_seq_submitted = get_error_ledger().current_seq
        self._changed()

    # -- reading -------------------------------------------------------------

    def findings(self) -> Optional[dict[str, Any]]:
        """Return the Findings of the current Questionnaire, or ``None`` before the first post.

        Holds the answers, the status, what is still unanswered, the failed or
        blocked Checks, who posted and submitted it and when, and the error
        ledger's cursor range while it was open.
        """
        q = self.current
        if q is None:
            return None
        return {
            "id": q.id,
            "title": q.title,
            "status": q.status,
            "incomplete": q.incomplete,
            "answers": q.answers,
            "unanswered": unanswered(q.definition, q.answers),
            "failed_checks": failed_checks(q.definition, q.answers),
            "posted_at": q.posted_at,
            "posted_by": q.posted_by,
            "submitted_at": q.submitted_at,
            "submitted_by": q.submitted_by,
            "user_agent": q.user_agent,
            "ledger_seq": {
                "posted": q.ledger_seq_posted,
                "submitted": q.ledger_seq_submitted,
                "now": get_error_ledger().current_seq,
            },
        }

    # -- internals -----------------------------------------------------------

    def _free_id(self, base: str) -> str:
        """Return ``base``, or ``base-2``, ``base-3``… when a file of that name exists."""
        candidate, n = base, 1
        while (self.folder / f"{candidate}.json").exists():
            n += 1
            candidate = f"{base}-{n}"
        return candidate

    def _open(self) -> Questionnaire:
        q = self.current
        if q is None:
            raise QuestionnaireClosed("No questionnaire has been posted.")
        if q.submitted:
            raise QuestionnaireClosed(f"Questionnaire {q.id} was already submitted.")
        return q

    def _changed(self) -> None:
        q = self.current
        if q is not None:
            path = self.folder / f"{q.id}.json"
            path.write_text(json.dumps(asdict(q), indent=2, ensure_ascii=False), encoding="utf-8")
        # Only a container-built state has a dispatcher; a state built alone (tests) stays silent.
        if hasattr(self, "_dispatcher"):
            self._signal_emit(QuestionnaireChanged())
