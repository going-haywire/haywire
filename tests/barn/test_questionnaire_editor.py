"""QuestionnaireEditor: opening on a post, empty state, answering, submit, live sync and the badge."""

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
from haywire.core.session.handlers import discover_reveal_handlers
from haywire.core.signals import SignalDispatcher, SignalPeer
from haywire.ui.app.aside_slot import AsideSlot
from haywire.ui.app.shell import AppShell
from haywire.ui.editor.identity import OpenBehavior, SlotName

from haybale_studio.editors.questionnaire_editor import QuestionnaireEditor
from haybale_studio.questionnaire.signals import QuestionnaireChanged, RevealQuestionnaire
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


def test_identity_puts_it_in_aside_as_one_required_tab_a_post_reveals() -> None:
    identity = QuestionnaireEditor.class_identity
    assert identity.default_slot is SlotName.ASIDE
    assert identity.opens is OpenBehavior.REQUIRED
    assert identity.requires is AccessTier.VIEW
    assert discover_reveal_handlers(QuestionnaireEditor) == {RevealQuestionnaire: "_on_reveal_questionnaire"}


class _Registry:
    """The slice of EditorRegistry the shell's reveal and a slot's wrappers touch."""

    _KEY = QuestionnaireEditor.class_identity.registry_key

    def list_names(self) -> list[str]:
        return [self._KEY]

    def get(self, key: str) -> Any:
        return QuestionnaireEditor if key == self._KEY else None

    get_by_key = get

    def get_by_default_slot(self, slot) -> dict:
        return {self._KEY: QuestionnaireEditor} if slot is SlotName.ASIDE else {}

    def add_batch_event_subscriber(self, _cb) -> None:
        pass

    def remove_batch_event_subscriber(self, _cb) -> None:
        pass

    def add_event_subscriber(self, _key, _cb) -> None:
        pass

    def remove_event_subscriber(self, _key, _cb) -> None:
        pass


def _window(dispatcher: SignalDispatcher, state: QuestionnaireState) -> tuple[AsideSlot, ui.row]:
    """Build one studio window (peer, shell, closed ASIDE); return the slot and its toggle box."""
    peer = SignalPeer(dispatcher)
    context = _context(state)
    context.can_access.return_value = True
    session: Any = MagicMock()
    session.context = context
    session.subscribe = peer.subscribe
    registry: Any = _Registry()
    slot = AsideSlot(session=session, name=SlotName.ASIDE, registry=registry, bar_place="top", visible=False)
    slot.populate_from_snapshot({})
    with ui.row() as row:
        slot.render(row)
    with ui.row() as toggle_box:
        slot.render_toggle(toggle_box)
    shell = AppShell(session=session, editor_registry=registry)
    shell._managed_slots = {SlotName.ASIDE: slot}
    shell._subscribe_reveal_on_editors()
    return slot, toggle_box


def _buttons(box: ui.element) -> list[ui.button]:
    return [e for e in box.descendants() if isinstance(e, ui.button)]


@pytest.mark.anyio
async def test_a_post_opens_the_aside_on_the_tab_in_every_window(
    user: User, state: QuestionnaireState
) -> None:
    dispatcher = SignalDispatcher()
    windows: list[tuple[AsideSlot, ui.row]] = []

    @ui.page("/")
    def page() -> None:
        windows.append(_window(dispatcher, state))
        windows.append(_window(dispatcher, state))

    await user.open("/")
    key = QuestionnaireEditor.class_identity.registry_key
    for slot, box in windows:
        assert [w.editor_key for w in slot.bindings] == [key]
        assert slot.bindings[0].can_close is False
        assert slot.visible is False
        assert len(_buttons(box)) == 2  # the tab's button next to the toggle

    state.post(copy.deepcopy(DEFINITION), principal="agent")
    dispatcher.broadcast(RevealQuestionnaire())

    for slot, _box in windows:
        assert slot.visible is True
        assert slot.active_binding_id == key
        assert len(slot.bindings) == 1

    first, _first_box = windows[0]
    first.set_visible(False)
    dispatcher.broadcast(RevealQuestionnaire())
    assert first.visible is True
    assert len(first.bindings) == 1


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
    wrapper: Any = editor.wrapper
    context = _context(state)
    assert editor._form is not None
    verdict = editor._form._fields["c1"].inputs[0]

    state.set_answer("c1", {"verdict": "blocked", "note": "no server"})
    editor._on_changed(context, QuestionnaireChanged())
    assert verdict.value == "blocked"
    wrapper.redraw.assert_not_called()
    wrapper.refresh_tab_bar.assert_called()

    state.post({"title": "Next", "elements": [{"type": "boolean", "name": "ok"}]}, principal="agent")
    editor._on_changed(context, QuestionnaireChanged())
    wrapper.redraw.assert_called_once()


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


@pytest.mark.anyio
async def test_discard_takes_it_out_of_the_studio(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    await _open(user, state)
    user.find(marker="questionnaire-discard").click()
    assert state.current is not None
    assert state.current.closed == "discarded"
    assert state.current.closed_by == "tester"


@pytest.mark.anyio
async def test_a_submitted_questionnaire_offers_discard_only(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    state.submit(principal="tester", user_agent=None, anyway=True)
    await _open(user, state)
    await user.should_see(marker="questionnaire-discard")
    await user.should_not_see(marker="questionnaire-submit")


@pytest.mark.anyio
async def test_a_closed_questionnaire_shows_the_empty_state(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    state.close("read", principal="agent")
    editor = await _open(user, state)
    assert editor._unanswered_count(_context(state)) == 0


@pytest.mark.anyio
async def test_a_viewer_cannot_discard(user: User, state: QuestionnaireState) -> None:
    state.post(copy.deepcopy(DEFINITION), principal="agent")
    await _open(user, state, can_edit=False)
    await user.should_not_see(marker="questionnaire-discard")
