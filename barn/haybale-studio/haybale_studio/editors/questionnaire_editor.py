"""QuestionnaireEditor — the Questionnaire an agent posted, answered in the ASIDE slot.

One tab, always present; ``RevealQuestionnaire`` brings it to the front in every
session when an agent posts. It shows the current Questionnaire of
``QuestionnaireState`` until it is closed; a new post replaces it. Answers are
stored as they are given and reach every session in place, without a redraw;
only a new post, a submit or a close redraws. The tab's badge counts the unanswered questions, and stays
in view next to the top-bar toggle while ASIDE is closed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nicegui import ui

from haybale_studio.questionnaire.definition import unanswered
from haybale_studio.questionnaire.form import QuestionnaireForm
from haybale_studio.questionnaire.signals import QuestionnaireChanged, RevealQuestionnaire
from haybale_studio.states.questionnaire_state import (
    DISCARDED,
    Questionnaire,
    QuestionnaireClosed,
    QuestionnaireState,
    RequiredUnanswered,
)
from haywire.api.workbench import (
    AccessTier,
    BaseEditor,
    OpenBehavior,
    SlotName,
    editor,
    hui,
    react_on,
    reveal_on,
)

if TYPE_CHECKING:
    from nicegui.element import Element

    from haywire.api.workbench import EditorWrapper, SessionContext


@editor(
    label="Questionnaire",
    icon=hui.icon.questionnaire,
    default_slot=SlotName.ASIDE,
    opens=OpenBehavior.REQUIRED,
    description="The Questionnaire an agent posted for a live check. Answer it, then submit.",
    requires=AccessTier.VIEW,
)
class QuestionnaireEditor(BaseEditor):
    """Shows the Questionnaire an agent posted, so the user can work through it and submit.

    An agent posts it with the `post_questionnaire` tool and reads the answers
    back with `get_findings`. Answering needs the edit tier; a viewer sees the
    form read-only. After *Submit* the form is read-only for everyone.

    When an agent posts, the aside opens on this tab in every studio window.
    The questionnaire leaves the studio once the agent has read the submitted
    answers, or when you press *Discard*.
    """

    def __init__(self, wrapper: EditorWrapper) -> None:
        super().__init__(wrapper)
        self._context: SessionContext | None = None
        self._form: QuestionnaireForm | None = None
        self._shown: tuple[str, str, str | None] | None = None
        self._status: ui.label | None = None

    @reveal_on(RevealQuestionnaire)
    @classmethod
    def _on_reveal_questionnaire(cls, context: SessionContext, event: RevealQuestionnaire) -> bool:
        """Answer a post: always reveal the tab."""
        return True

    def _state(self, context: SessionContext) -> QuestionnaireState:
        return context.app_data[QuestionnaireState]

    def _on_show(self, context: SessionContext) -> Questionnaire | None:
        q = self._state(context).current
        return q if q is not None and q.on_show else None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def draw(self, context: SessionContext, container: Element) -> None:
        self._context = context
        q = self._on_show(context)
        self._form = None
        self._shown = (q.id, q.status, q.closed) if q is not None else None
        with container:
            if q is None:
                hui.empty_state(
                    "No questionnaire",
                    icon=hui.icon.questionnaire,
                    hint="An agent posts one here when a change needs a live check.",
                )
                return
            with ui.column().classes("w-full h-full gap-0"):
                with hui.panel_header("Questionnaire", icon=hui.icon.questionnaire):
                    self._status = hui.hint("").classes("ml-auto")
                with ui.scroll_area().classes("flex-1 w-full"):
                    with ui.column().classes("w-full gap-3 p-3"):
                        if q.submitted:
                            hui.hint(self._submitted_text(q.submitted_at, q.submitted_by, q.incomplete))
                            if completed := q.definition.get("completedHtml"):
                                ui.html(str(completed), sanitize=True).classes("w-full text-sm")
                        self._form = QuestionnaireForm(
                            q.definition,
                            q.answers,
                            on_answer=self._on_answer,
                            read_only=q.submitted or not context.can_edit(),
                        )
                        self._form.build()
                if context.can_edit():
                    with (
                        ui.row()
                        .classes("w-full justify-end gap-2 p-2")
                        .style("border-top: 1px solid var(--hw-border);")
                    ):
                        ui.button("Discard", on_click=self._discard).props("flat dense no-caps").classes(
                            "mr-auto"
                        ).mark("questionnaire-discard").tooltip("Remove it from the studio")
                        if not q.submitted:
                            ui.button("Submit anyway", on_click=lambda: self._submit(anyway=True)).props(
                                "flat dense no-caps"
                            ).mark("questionnaire-submit-anyway").tooltip("Submit with questions unanswered")
                            ui.button("Submit", on_click=lambda: self._submit(anyway=False)).props(
                                "dense no-caps"
                            ).mark("questionnaire-submit")
        self._update_status()

    def draw_tab(self, context, *, orientation) -> None:
        """Tab interior: label and the count of unanswered questions while one is open."""
        label = self.wrapper.label or self.class_identity.label
        count = self._unanswered_count(context)
        with ui.row().classes("items-center gap-1 no-wrap"):
            if orientation == "vertical":
                ui.icon(self.class_identity.icon).tooltip(self.class_identity.label)
            else:
                ui.icon(self.class_identity.icon, size="14px")
                ui.label(label)
            if count:
                hui.count_badge(count, tone="info")

    def _unanswered_count(self, context: SessionContext) -> int:
        q = self._on_show(context)
        if q is None or q.submitted:
            return 0
        return len(unanswered(q.definition, q.answers))

    @staticmethod
    def _submitted_text(when: str | None, who: str | None, incomplete: bool) -> str:
        by = f" by {who}" if who else ""
        rest = ", with questions unanswered" if incomplete else ""
        return f"Submitted {when or ''}{by}{rest}. The agent can read the findings now."

    def _update_status(self) -> None:
        if self._status is None or self._context is None:
            return
        q = self._on_show(self._context)
        if q is None:
            return
        count = self._unanswered_count(self._context)
        self._status.set_text(
            "Submitted" if q.submitted else f"{count} unanswered" if count else "All answered"
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_answer(self, name: str, value: Any) -> None:
        if self._context is None or not self._context.can_edit():
            return
        try:
            self._state(self._context).set_answer(name, value)
        except (QuestionnaireClosed, KeyError):
            ui.notify("This questionnaire takes no more answers.", type="warning")
            self.wrapper.redraw()

    def _submit(self, *, anyway: bool) -> None:
        if self._context is None or not self._context.can_edit():
            return
        try:
            self._state(self._context).submit(
                principal=self._context.principal, user_agent=self._user_agent(), anyway=anyway
            )
        except RequiredUnanswered as exc:
            if self._form is not None:
                self._form.show_missing(exc.names)
            ui.notify(f"{len(exc.names)} required questions are unanswered.", type="warning")
        except QuestionnaireClosed:
            self.wrapper.redraw()

    def _discard(self) -> None:
        if self._context is None or not self._context.can_edit():
            return
        self._state(self._context).close(DISCARDED, principal=self._context.principal)

    @staticmethod
    def _user_agent() -> str | None:
        """Return the submitting browser's user agent, or ``None`` outside a page request."""
        try:
            return ui.context.client.request.headers.get("user-agent")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Live sync
    # ------------------------------------------------------------------

    @react_on(QuestionnaireChanged)
    def _on_changed(self, context: SessionContext, signal: QuestionnaireChanged) -> None:
        """Redraw on a new post, a submit or a close; otherwise show the new answers in place."""
        q = self._on_show(context)
        shown = (q.id, q.status, q.closed) if q is not None else None
        if shown != self._shown or self._form is None or q is None:
            self.wrapper.redraw()
        else:
            self._form.apply(q.answers)
            self._update_status()
        self.wrapper.refresh_tab_bar()

    def cleanup(self) -> None:
        self._context = None
        self._form = None
        self._status = None
