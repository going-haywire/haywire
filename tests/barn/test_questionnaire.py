"""The Questionnaire: condition grammar, validator, store, Findings and Farmhand tools."""

from __future__ import annotations

import asyncio
import copy
from typing import Any

import pytest

from haywire.core.farmhand import FarmhandContext, FarmhandError

from haybale_studio.farmhands.questionnaire import StudioGetFindingsTool, StudioPostQuestionnaireTool
from haybale_studio.questionnaire.definition import (
    failed_checks,
    missing_required,
    unanswered,
    validate,
)
from haybale_studio.questionnaire.expressions import ExpressionError, parse_expression
from haybale_studio.states.questionnaire_state import (
    QuestionnaireClosed,
    QuestionnaireState,
    RequiredUnanswered,
)

pytestmark = pytest.mark.unit

# A live check of the ASIDE slot, shaped like the one a small model wrote, with Checks.
LIVE_CHECK: dict[str, Any] = {
    "title": "ASIDE slot live check",
    "showProgressBar": "top",
    "pages": [
        {
            "name": "toggle",
            "title": "The toggle",
            "elements": [
                {
                    "type": "check",
                    "name": "toggle_opens",
                    "title": "Toggle opens ASIDE",
                    "do": "Click the toggle at the right of the top bar.",
                    "expect": "A column opens between the canvas and CONTEXT.",
                    "isRequired": True,
                },
                {
                    "type": "comment",
                    "name": "toggle_detail",
                    "title": "What did you see instead?",
                    "visibleIf": "{toggle_opens} = 'fail'",
                },
            ],
        },
        {
            "name": "resize",
            "title": "Resize",
            "elements": [
                {
                    "type": "panel",
                    "name": "resize_panel",
                    "title": "Divider",
                    "elements": [
                        {"type": "html", "html": "<p>Drag the <b>left</b> divider.</p>"},
                        {
                            "type": "check",
                            "name": "resize_works",
                            "title": "Divider resizes",
                            "do": "Drag the divider to the left.",
                            "expect": "ASIDE grows.",
                        },
                    ],
                },
                {
                    "type": "rating",
                    "name": "feel",
                    "title": "How does it feel?",
                    "rateMin": 1,
                    "rateMax": 5,
                    "minRateDescription": "clumsy",
                    "maxRateDescription": "smooth",
                },
                {
                    "type": "radiogroup",
                    "name": "browser",
                    "title": "Browser",
                    "choices": ["Firefox", "Chrome", {"value": "safari", "text": "Safari"}],
                    "showOtherItem": True,
                    "requiredIf": "{feel} < 3",
                },
                {"type": "ranking", "name": "order", "title": "Rank", "choices": ["a", "b", "c"]},
                {"type": "boolean", "name": "again", "title": "Use it again?"},
                {"type": "text", "name": "when", "inputType": "date"},
            ],
        },
    ],
}


def _live_check() -> dict[str, Any]:
    return copy.deepcopy(LIVE_CHECK)


def _state(tmp_path) -> QuestionnaireState:
    state = QuestionnaireState()
    state._folder = tmp_path
    return state


# ---------------------------------------------------------------------------
# Condition grammar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("source", "values", "expected"),
    [
        ("{a} = 'yes'", {"a": "yes"}, True),
        ("{a} = 'YES'", {"a": "yes"}, True),
        ("{a} != 'yes'", {"a": "no"}, True),
        ("{a} <> 'yes'", {"a": "yes"}, False),
        ("{n} < 3", {"n": 2}, True),
        ("{n} >= 3", {"n": "3"}, True),
        ("{n} < 3", {}, False),
        ("{a} empty", {}, True),
        ("{a} notempty", {"a": ""}, False),
        ("{a} notempty and {n} > 1", {"a": "x", "n": 2}, True),
        ("{a} = 1 or not ({b} = 2)", {"a": 0, "b": 3}, True),
        ("!{flag}", {"flag": False}, True),
        ("{flag} = true", {"flag": True}, True),
        ("{tags} contains 'red'", {"tags": ["red", "blue"]}, True),
        ("{text} contains 'oo'", {"text": "Foo"}, True),
        ("{tags} notcontains 'red'", {"tags": ["blue"]}, True),
        ("{pick} anyof ['a', 'b']", {"pick": "b"}, True),
        ("{picks} anyof ['a', 'b']", {"picks": ["c", "a"]}, True),
        ("{my question} = 2", {"my question": 2}, True),
        ("{a} && {b} || {c}", {"c": 1}, True),
    ],
)
def test_conditions_evaluate(source: str, values: dict, expected: bool) -> None:
    assert parse_expression(source).evaluate(values) is expected


def test_a_condition_names_its_references() -> None:
    assert parse_expression("{a} = 1 and ({b} notempty or {c} anyof [1, 2])").references == {"a", "b", "c"}


@pytest.mark.parametrize(
    "source",
    ["iif({a}, 1, 2)", "{a} + 1 > 2", "{a} = ", "({a} = 1", "{a} = [{b}]", "age({birth}) > 18", "{a} ~ 1"],
)
def test_conditions_outside_the_grammar_are_refused(source: str) -> None:
    with pytest.raises(ExpressionError):
        parse_expression(source)


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def test_the_live_check_is_inside_the_subset() -> None:
    assert validate(_live_check()) == []


def test_top_level_elements_without_pages_are_accepted() -> None:
    assert validate({"elements": [{"type": "boolean", "name": "ok"}]}) == []


@pytest.mark.parametrize(
    ("mutate", "where", "prop"),
    [
        (lambda d: d.update(logoPosition="right"), "questionnaire", "logoPosition"),
        (lambda d: d["pages"][0]["elements"].append({"type": "matrix", "name": "m"}), "elements[2]", "type"),
        (
            lambda d: d["pages"][0]["elements"][1].update(rows=3, choicesByUrl={}),
            "'toggle_detail'",
            "choicesByUrl",
        ),
        (lambda d: d["pages"][0]["elements"][0].pop("do"), "'toggle_opens'", "do"),
        (lambda d: d["pages"][0]["elements"][1].pop("name"), "elements[1]", "name"),
        (lambda d: d["pages"][1]["elements"][1].update(name="toggle_opens"), "'toggle_opens'", "name"),
        (
            lambda d: d["pages"][0]["elements"][1].update(visibleIf="iif({a})"),
            "'toggle_detail'",
            "visibleIf",
        ),
        (
            lambda d: d["pages"][0]["elements"][1].update(visibleIf="{nobody} = 1"),
            "'toggle_detail'",
            "visibleIf",
        ),
        (lambda d: d["pages"][1]["elements"][2].update(choices=[]), "'browser'", "choices"),
        (lambda d: d["pages"][1]["elements"][5].update(inputType="file"), "'when'", "inputType"),
        (lambda d: d["pages"][1]["elements"][1].update(rateMax=1), "'feel'", "rateMin"),
        (lambda d: d.update(elements=[]), "questionnaire", "pages"),
    ],
)
def test_the_validator_names_element_and_property(mutate, where: str, prop: str) -> None:
    definition = _live_check()
    mutate(definition)
    issues = validate(definition)
    assert any(where in issue.where and issue.property == prop for issue in issues), issues


def test_a_nested_panel_element_is_validated() -> None:
    definition = _live_check()
    definition["pages"][1]["elements"][0]["elements"][1]["expect"] = ""
    (issue,) = validate(definition)
    assert issue.where == "pages[1].elements[0] 'resize_panel'.elements[1] 'resize_works'"
    assert issue.property == "expect"


# ---------------------------------------------------------------------------
# Walkers
# ---------------------------------------------------------------------------


def test_unanswered_skips_hidden_questions_and_counts_checks_by_verdict() -> None:
    definition = _live_check()
    names = unanswered(definition, {})
    assert "toggle_detail" not in names  # hidden until toggle_opens fails
    assert names[0] == "toggle_opens"

    after_fail = unanswered(definition, {"toggle_opens": {"verdict": "fail"}})
    assert "toggle_opens" not in after_fail
    assert "toggle_detail" in after_fail

    assert "toggle_opens" in unanswered(definition, {"toggle_opens": {"note": "no verdict"}})


def test_required_follows_is_required_and_required_if() -> None:
    definition = _live_check()
    assert missing_required(definition, {}) == ["toggle_opens"]
    assert missing_required(definition, {"toggle_opens": {"verdict": "pass"}, "feel": 2}) == ["browser"]
    page_two = definition["pages"][1]
    assert missing_required(definition, {"feel": 2}, page_two) == ["browser"]


def test_failed_checks_lists_fail_and_blocked() -> None:
    answers = {"toggle_opens": {"verdict": "blocked"}, "resize_works": {"verdict": "pass"}}
    assert failed_checks(_live_check(), answers) == ["toggle_opens"]


# ---------------------------------------------------------------------------
# Store and Findings
# ---------------------------------------------------------------------------


def test_post_answer_submit_and_findings(tmp_path) -> None:
    state = _state(tmp_path)
    q = state.post(_live_check(), principal="agent")
    assert q.status == "open"
    assert (tmp_path / f"{q.id}.json").exists()
    assert q.id.endswith("-aside-slot-live-check")

    state.set_answer("toggle_opens", {"verdict": "fail", "note": "nothing happened"})
    state.set_answer("browser", "other")
    state.set_answer("browser-Comment", "Arc")
    state.submit(principal="tester", user_agent="UA/1.0", anyway=True)

    findings = state.findings()
    assert findings is not None
    assert findings["status"] == "submitted"
    assert findings["incomplete"] is True
    assert findings["answers"]["toggle_opens"] == {"verdict": "fail", "note": "nothing happened"}
    assert findings["answers"]["browser-Comment"] == "Arc"
    assert findings["failed_checks"] == ["toggle_opens"]
    assert "toggle_detail" in findings["unanswered"]
    assert findings["posted_by"] == "agent"
    assert findings["submitted_by"] == "tester"
    assert findings["user_agent"] == "UA/1.0"
    assert set(findings["ledger_seq"]) == {"posted", "submitted", "now"}
    assert findings["ledger_seq"]["posted"] <= findings["ledger_seq"]["submitted"]


def test_an_answer_of_none_clears_it(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal=None)
    state.set_answer("feel", 4)
    state.set_answer("feel", None)
    assert state.current is not None
    assert "feel" not in state.current.answers


def test_an_unknown_question_is_refused(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal=None)
    with pytest.raises(KeyError):
        state.set_answer("nobody", 1)
    with pytest.raises(KeyError):
        state.set_answer("feel-Comment", "no Other item on a rating")


def test_submit_enforces_required_unless_anyway(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal=None)
    with pytest.raises(RequiredUnanswered) as raised:
        state.submit(principal=None, user_agent=None)
    assert raised.value.names == ["toggle_opens"]
    assert state.current is not None
    assert state.current.status == "open"

    state.set_answer("toggle_opens", {"verdict": "pass"})
    state.submit(principal=None, user_agent=None)
    assert state.current.status == "submitted"


def test_a_submitted_questionnaire_takes_no_more_answers(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal=None)
    state.submit(principal=None, user_agent=None, anyway=True)
    with pytest.raises(QuestionnaireClosed):
        state.set_answer("feel", 3)
    with pytest.raises(QuestionnaireClosed):
        state.submit(principal=None, user_agent=None, anyway=True)


def test_nothing_posted_is_closed(tmp_path) -> None:
    state = _state(tmp_path)
    assert state.findings() is None
    with pytest.raises(QuestionnaireClosed):
        state.set_answer("feel", 3)


def test_a_new_post_replaces_the_current_one_and_keeps_the_old_on_disk(tmp_path) -> None:
    state = _state(tmp_path)
    first = state.post(_live_check(), principal=None)
    state.set_answer("feel", 5)
    second_definition = {"title": "Second", "elements": [{"type": "boolean", "name": "ok"}]}
    second = state.post(second_definition, principal=None)

    assert state.current is second
    assert state.current.answers == {}
    assert second.id != first.id
    assert (tmp_path / f"{first.id}.json").exists()

    reloaded = _state(tmp_path)
    reloaded.on_enable()
    assert reloaded.current is not None
    assert reloaded.current.title == "Second"


def test_two_posts_in_one_second_keep_both_files(tmp_path) -> None:
    state = _state(tmp_path)
    first = state.post(_live_check(), principal=None)
    second = state.post(_live_check(), principal=None)
    assert second.id != first.id
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_answers_survive_a_restart(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal=None)
    state.set_answer("order", ["c", "a", "b"])

    reloaded = _state(tmp_path)
    reloaded.on_enable()
    assert reloaded.current is not None
    assert reloaded.current.answers == {"order": ["c", "a", "b"]}


FOLLOW_UP: dict[str, Any] = {
    "elements": [
        {"type": "radiogroup", "name": "pick", "choices": ["A", "B"], "showOtherItem": True},
        {"type": "comment", "name": "why", "visibleIf": "{pick} = 'B'"},
        {"type": "comment", "name": "deeper", "visibleIf": "{why} notempty"},
    ]
}


def test_submit_drops_the_answers_of_hidden_questions(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(copy.deepcopy(FOLLOW_UP), principal=None)
    state.set_answer("pick", "B")
    state.set_answer("why", "because")
    state.set_answer("deeper", "really")
    state.set_answer("pick", "A")
    assert state.current is not None
    assert set(state.current.answers) == {"pick", "why", "deeper"}

    state.submit(principal=None, user_agent=None)
    assert state.current.answers == {"pick": "A"}


def test_close_takes_it_out_of_the_studio_and_keeps_the_findings(tmp_path) -> None:
    state = _state(tmp_path)
    state.post(_live_check(), principal="agent")
    state.set_answer("toggle_opens", {"verdict": "pass"})
    state.close("discarded", principal="tester")
    assert state.current is not None
    assert state.current.on_show is False

    findings = state.findings()
    assert findings is not None
    assert findings["closed"] == "discarded"
    assert findings["closed_by"] == "tester"
    assert findings["answers"] == {"toggle_opens": {"verdict": "pass"}}
    with pytest.raises(QuestionnaireClosed):
        state.set_answer("toggle_opens", {"verdict": "fail"})

    state.close("read", principal="agent")
    assert state.current.closed == "discarded"

    reloaded = _state(tmp_path)
    reloaded.on_enable()
    assert reloaded.current is not None
    assert reloaded.current.closed == "discarded"


def test_close_before_a_post_does_nothing(tmp_path) -> None:
    state = _state(tmp_path)
    state.close("discarded", principal=None)
    assert state.current is None


# ---------------------------------------------------------------------------
# Farmhand tools
# ---------------------------------------------------------------------------


@pytest.fixture
def tool_state(tmp_path, monkeypatch) -> QuestionnaireState:
    state = _state(tmp_path)
    monkeypatch.setattr(FarmhandContext, "state", lambda self, cls: state)
    return state


def _run(tool_cls, **kwargs) -> dict:
    return asyncio.run(tool_cls().run(FarmhandContext(principal="agent"), **kwargs))


def test_post_questionnaire_posts_and_tells_the_protocol(tool_state) -> None:
    result = _run(StudioPostQuestionnaireTool, questionnaire=_live_check())
    assert tool_state.current is not None
    assert result["id"] == tool_state.current.id
    assert "haybale-studio_get_findings" in result["summary"]
    assert tool_state.current.posted_by == "agent"


def test_post_questionnaire_accepts_a_json_string(tool_state) -> None:
    import json

    _run(StudioPostQuestionnaireTool, questionnaire=json.dumps(_live_check()))
    assert tool_state.current is not None


def test_post_questionnaire_rejects_with_every_issue_and_the_format_page(tool_state) -> None:
    definition = _live_check()
    definition["logoPosition"] = "right"
    definition["pages"][0]["elements"][0].pop("do")
    with pytest.raises(FarmhandError) as raised:
        _run(StudioPostQuestionnaireTool, questionnaire=definition)
    error = raised.value
    assert error.code == "invalid_questionnaire"
    assert "logoPosition" in str(error)
    assert "'toggle_opens' do:" in str(error)
    assert "farmhand://docs/reference/questionnaire.md" in (error.help or "")
    assert tool_state.current is None


def test_get_findings_before_a_post_is_an_error(tool_state) -> None:
    with pytest.raises(FarmhandError) as raised:
        _run(StudioGetFindingsTool)
    assert raised.value.code == "no_questionnaire"


def test_get_findings_returns_the_answers_so_far(tool_state) -> None:
    _run(StudioPostQuestionnaireTool, questionnaire=_live_check())
    tool_state.set_answer("toggle_opens", {"verdict": "fail", "note": "x"})
    findings = _run(StudioGetFindingsTool)
    assert findings["status"] == "open"
    assert findings["failed_checks"] == ["toggle_opens"]
    assert "1 failed or blocked checks" in findings["summary"]


def test_get_findings_closes_a_submitted_questionnaire(tool_state) -> None:
    _run(StudioPostQuestionnaireTool, questionnaire=_live_check())
    tool_state.submit(principal="tester", user_agent=None, anyway=True)
    findings = _run(StudioGetFindingsTool)
    assert findings["closed"] == "read"
    assert findings["closed_by"] == "agent"
    assert "no longer shown" in findings["summary"]
    assert tool_state.current is not None
    assert tool_state.current.on_show is False

    again = _run(StudioGetFindingsTool)
    assert again["closed"] == "read"


def test_get_findings_leaves_an_open_questionnaire_on_show(tool_state) -> None:
    _run(StudioPostQuestionnaireTool, questionnaire=_live_check())
    findings = _run(StudioGetFindingsTool)
    assert findings["closed"] is None
    assert tool_state.current is not None
    assert tool_state.current.on_show is True
