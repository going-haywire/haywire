"""QuestionnaireEditor: empty state, answering through the store, submit, live sync and the badge."""

from __future__ import annotations

import copy
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import MagicMock

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haywire.core.access import AccessTier
from haywire.ui.editor.identity import OpenBehavior, SlotName

from haybale_studio.editors.questionnaire_editor import QuestionnaireEditor
from haybale_studio.questionnaire.signals import QuestionnaireChanged
from haybale_studio.states.questionnaire_state import QuestionnaireState

pytestmark = pytest.mark.unit

DEFINITION: dict[str, Any] = {
    "title": "Editor test",
    "elements": [
        {"type": "check", "name": "c1", "do": "Do it.", "expect": "It works.", "isRequired": True},
        {"type": "boolean", "name": "again"},
    ],
}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


@pytest.fixture
def state(tmp_path) -> QuestionnaireState:
    s = QuestionnaireState()
    s._folder = tmp_path
    return s


def _context(state: QuestionnaireState, *, can_edit: bool = True) -> MagicMock:
    context = MagicMock()
    context.app_data = {QuestionnaireState: state}
    context.can_edit.return_value = can_edit
    context.principal = "tester"
    return context


async def _open(user: User, state: QuestionnaireState, *, can_edit: bool = True) -> QuestionnaireEditor:
    holder: dict[str, QuestionnaireEditor] = {}

    @ui.page("/")
    def page() -> None:
        editor = QuestionnaireEditor(MagicMock())
        editor.draw(_context(state, can_edit=can_edit), ui.column())
        holder["editor"] = editor

    await user.open("/")
    return holder["editor"]


def test_identity_puts_it_in_aside_as_one_required_tab() -> None:
    identity = QuestionnaireEditor.class_identity
    assert identity.default_slot is SlotName.ASIDE
    assert identity.opens is OpenBehavior.REQUIRED
    assert identity.requires is AccessTier.VIEW


@pytest.mark.anyio
async def test_nothing_posted_shows_the_empty_state(user: User, state: QuestionnaireState) -> None:
    await _open(user, state)
    await user.should_see("No questionnaire")


@pytest.mark.anyio
async def test_an_answer_goes_to_the_store(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    editor = await _open(user, state)
    await user.should_see("Editor test")
    assert editor._form is not None

    editor._form._fields["c1"].inputs[0].set_value("pass")

    assert state.current is not None
    assert state.current.answers == {"c1": {"verdict": "pass"}}


@pytest.mark.anyio
async def test_submit_enforces_required_and_submit_anyway_does_not(
    user: User, state: QuestionnaireState
) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    await _open(user, state)

    user.find(marker="questionnaire-submit").click()
    assert state.current is not None
    assert state.current.status == "open"
    await user.should_see("Answer this question.")

    user.find(marker="questionnaire-submit-anyway").click()
    assert state.current.status == "submitted"
    assert state.current.submitted_by == "tester"
    assert state.current.incomplete is True


@pytest.mark.anyio
async def test_a_viewer_sees_no_submit_and_cannot_answer(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    editor = await _open(user, state, can_edit=False)
    await user.should_not_see("Submit anyway")
    assert editor._form is not None
    editor._form._fields["c1"].inputs[0].set_value("pass")
    assert state.current is not None
    assert state.current.answers == {}


@pytest.mark.anyio
async def test_another_sessions_answer_lands_in_place_and_a_new_post_redraws(
    user: User, state: QuestionnaireState
) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    editor = await _open(user, state)
    context = _context(state)
    assert editor._form is not None
    verdict = editor._form._fields["c1"].inputs[0]

    state.set_answer("c1", {"verdict": "blocked", "note": "no server"})
    editor._on_changed(context, QuestionnaireChanged())
    assert verdict.value == "blocked"
    editor.wrapper.redraw.assert_not_called()
    editor.wrapper.refresh_tab_bar.assert_called()

    state.post({"title": "Next", "elements": [{"type": "boolean", "name": "ok"}]}, principal="agent")
    editor._on_changed(context, QuestionnaireChanged())
    editor.wrapper.redraw.assert_called_once()


@pytest.mark.anyio
async def test_the_tab_counts_unanswered_questions(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    editor = await _open(user, state)
    context = _context(state)
    assert editor._unanswered_count(context) == 2
    state.set_answer("again", False)
    assert editor._unanswered_count(context) == 1
    state.submit(principal=None, user_agent=None, anyway=True)
    assert editor._unanswered_count(context) == 0
