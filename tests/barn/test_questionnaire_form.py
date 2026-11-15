"""QuestionnaireForm: answers in, answers out, in place; conditions, pages and read-only."""

from __future__ import annotations

import functools
from collections.abc import AsyncGenerator
from typing import Any

import pytest
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_simulation import user_simulation

from haybale_studio.questionnaire.form import QuestionnaireForm

DEFINITION: dict[str, Any] = {
    "title": "Form test",
    "pages": [
        {
            "elements": [
                {
                    "type": "check",
                    "name": "c1",
                    "title": "First check",
                    "do": "Click it.",
                    "expect": "It works.",
                    "isRequired": True,
                },
                {"type": "comment", "name": "why", "visibleIf": "{c1} = 'fail'"},
                {"type": "text", "name": "name"},
            ]
        },
        {"elements": [{"type": "boolean", "name": "again"}, {"type": "rating", "name": "feel"}]},
    ],
}


EVERY_TYPE: dict[str, Any] = {
    "elements": [
        {"type": "boolean", "name": "b"},
        {"type": "radiogroup", "name": "r", "choices": ["x", "y"], "showOtherItem": True},
        {"type": "checkbox", "name": "cb", "choices": ["x", "y"]},
        {"type": "dropdown", "name": "d", "choices": ["x", "y"]},
        {"type": "text", "name": "t"},
        {"type": "text", "name": "n", "inputType": "number"},
        {"type": "text", "name": "col", "inputType": "color"},
        {"type": "text", "name": "rng", "inputType": "range", "min": 0, "max": 10},
        {"type": "comment", "name": "co"},
        {"type": "rating", "name": "ra"},
        {"type": "rating", "name": "st", "rateType": "stars"},
        {"type": "ranking", "name": "rk", "choices": ["x", "y"], "enableIf": "{b} = true"},
        {"type": "check", "name": "ch", "do": "Do.", "expect": "Expect."},
        {"type": "html", "html": "<p>note</p>"},
    ]
}
"""One question of every type; the ranking is enabled only while ``b`` is yes."""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def user() -> AsyncGenerator[User, None]:
    async with user_simulation() as u:
        yield u


async def _forms(
    user: User,
    count: int,
    answers: dict | None = None,
    *,
    read_only: bool = False,
    definition: dict[str, Any] = DEFINITION,
):
    """Draw ``count`` forms over one shared answer dict, as sessions over one store do."""
    store: dict[str, Any] = dict(answers or {})
    reported: list[tuple[int, str, Any]] = []
    forms: list[QuestionnaireForm] = []

    def _on_answer(index: int, name: str, value: Any) -> None:
        reported.append((index, name, value))
        if value is None:
            store.pop(name, None)
        else:
            store[name] = value
        for other in forms:
            other.apply(store)

    @ui.page("/")
    def page() -> None:
        for index in range(count):
            form = QuestionnaireForm(
                definition,
                store,
                on_answer=functools.partial(_on_answer, index),
                read_only=read_only,
            )
            form.build()
            forms.append(form)

    await user.open("/")
    return forms, store, reported


def _field(form: QuestionnaireForm, name: str):
    return form._fields[name]


@pytest.mark.unit
@pytest.mark.anyio
async def test_an_answer_reaches_the_other_form_in_place(user: User) -> None:
    (a, b), store, reported = await _forms(user, 2)
    verdict_b = _field(b, "c1").inputs[0]

    _field(a, "c1").inputs[0].set_value("pass")

    assert store == {"c1": {"verdict": "pass"}}
    assert reported == [(0, "c1", {"verdict": "pass"})]  # b did not echo it back
    assert _field(b, "c1").inputs[0] is verdict_b  # updated in place, not redrawn
    assert verdict_b.value == "pass"


@pytest.mark.unit
@pytest.mark.anyio
async def test_text_commits_on_blur_not_per_keystroke(user: User) -> None:
    (form,), store, reported = await _forms(user, 1)
    name_input = _field(form, "name").inputs[0]
    name_input.mark("name-input")

    name_input.value = "Ad"
    assert reported == []
    user.find(marker="name-input").trigger("blur")
    assert store == {"name": "Ad"}


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_failed_check_opens_its_note_and_reveals_the_follow_up(user: User) -> None:
    (form,), store, _reported = await _forms(user, 1)
    verdict, note = _field(form, "c1").inputs
    why = _field(form, "why").wrapper
    assert note.visible is False
    assert why.visible is False

    verdict.set_value("fail")
    assert note.visible is True
    assert why.visible is True

    note.value = "nothing happened"
    note.mark("note")
    user.find(marker="note").trigger("blur")
    assert store["c1"] == {"verdict": "fail", "note": "nothing happened"}


@pytest.mark.unit
@pytest.mark.anyio
async def test_next_waits_for_required_questions(user: User) -> None:
    (form,), _store, _reported = await _forms(user, 1)
    first, second = form._page_boxes
    assert first.visible is True
    assert second.visible is False

    form._step(1)
    assert first.visible is True
    assert _field(form, "c1").error.visible is True

    _field(form, "c1").inputs[0].set_value("skip")
    assert _field(form, "c1").error.visible is False
    form._step(1)
    assert first.visible is False
    assert second.visible is True


@pytest.mark.unit
@pytest.mark.anyio
async def test_show_missing_goes_to_the_page_of_the_first(user: User) -> None:
    (form,), _store, _reported = await _forms(user, 1, {"c1": {"verdict": "pass"}})
    form._step(1)
    form.show_missing(["c1"])
    assert form._page_boxes[0].visible is True


@pytest.mark.unit
@pytest.mark.anyio
async def test_a_read_only_form_shows_answers_and_reports_nothing(user: User) -> None:
    (form,), _store, reported = await _forms(
        user, 1, {"c1": {"verdict": "fail", "note": "x"}}, read_only=True
    )
    verdict, note = _field(form, "c1").inputs
    assert verdict.value == "fail"
    assert note.value == "x"
    assert verdict.enabled is False

    verdict.set_value("pass")
    assert reported == []


@pytest.mark.unit
@pytest.mark.anyio
async def test_every_type_draws_read_only_with_its_inputs_disabled(user: User) -> None:
    (form,), _store, _reported = await _forms(
        user, 1, {"rk": ["y", "x"], "b": True}, read_only=True, definition=EVERY_TYPE
    )
    for name, field_ in form._fields.items():
        for item in field_.inputs:
            assert item.enabled is False, name


@pytest.mark.unit
@pytest.mark.anyio
async def test_enable_if_disables_a_ranking(user: User) -> None:
    (form,), _store, reported = await _forms(user, 1, definition=EVERY_TYPE)
    (ranking,) = _field(form, "rk").inputs
    assert ranking.enabled is False
    form.commit("b", True)
    assert ranking.enabled is True
    assert "disabled" not in ranking.box.classes
