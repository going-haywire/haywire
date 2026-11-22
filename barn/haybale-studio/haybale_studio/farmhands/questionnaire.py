"""post_questionnaire / get_findings — the live-check exchange between an agent and the user."""

from __future__ import annotations

import json
from typing import Any

from haybale_studio.questionnaire.definition import FORMAT_URI, validate
from haybale_studio.questionnaire.signals import RevealQuestionnaire
from haybale_studio.states.questionnaire_state import READ, SUBMITTED, QuestionnaireState
from haywire.api.workbench import (
    AccessTier,
    Farmhand,
    FarmhandContext,
    FarmhandError,
    ToolAnnotations,
    farmhand,
)

_MAX_ISSUES = 20


@farmhand(
    label="Post questionnaire",
    description="Post a Questionnaire for the user to answer; it opens in the studio's aside.",
    instructions="Post a Questionnaire (SurveyJS JSON, a subset) for the user to work through in the "
    "studio during a live check; it replaces the current one. Types: boolean, radiogroup, checkbox, "
    "dropdown, text (inputType text/number/date/color/range/email/url), comment, rating, ranking, html, "
    "panel, plus check {type:'check', name, title, do, expect}, answered with a verdict "
    "(pass/fail/blocked/skip) and a note: prefer check for each do/expect step. Use 'pages' or top-level "
    "'elements'. Conditions visibleIf/enableIf/requiredIf: {name}, = != < > <= >=, and/or/not, "
    "empty/notempty, contains/anyof; a check's value is its verdict. No functions, calculated values, "
    f"piping, triggers or matrices. Anything else is rejected. Full format: {FORMAT_URI}. After "
    "posting, it opens in every studio window's aside; tell the user it is there, then call "
    "haybale-studio_get_findings when they say they are done.",
    registry_id="post_questionnaire",
    annotations=ToolAnnotations(destructive_hint=False, idempotent_hint=False),
    requires=AccessTier.EDIT,
)
class StudioPostQuestionnaireTool(Farmhand):
    async def run(self, ctx: FarmhandContext, questionnaire: dict | str) -> dict:
        definition: Any = questionnaire
        if isinstance(questionnaire, str):
            try:
                definition = json.loads(questionnaire)
            except json.JSONDecodeError as exc:
                raise FarmhandError(
                    "invalid_questionnaire",
                    f"The questionnaire is not valid JSON: {exc}.",
                    help=f"Pass the questionnaire as a JSON object; the format is at {FORMAT_URI}.",
                ) from exc
        issues = validate(definition)
        if issues:
            shown = "\n".join(f"- {issue}" for issue in issues[:_MAX_ISSUES])
            more = f"\n… and {len(issues) - _MAX_ISSUES} more." if len(issues) > _MAX_ISSUES else ""
            raise FarmhandError(
                "invalid_questionnaire",
                f"The questionnaire leaves the supported subset in {len(issues)} places:\n{shown}{more}",
                help=f"Fix each place and post again; the supported format is at {FORMAT_URI}.",
            )
        q = ctx.state(QuestionnaireState).post(definition, ctx.principal)
        ctx.broadcast(RevealQuestionnaire())
        return {
            "summary": f"Posted questionnaire {q.id!r}; it is open in the studio's aside. Tell the user it "
            "is there, then call haybale-studio_get_findings when they say they are done; its status says "
            "whether they submitted.",
            "id": q.id,
            "ledger_seq": q.ledger_seq_posted,
        }


@farmhand(
    label="Get findings",
    description="Read the user's answers to the current Questionnaire.",
    instructions="Read the Findings of the current Questionnaire: status ('open' or 'submitted'), "
    "incomplete, answers by question name (a check's answer is {verdict, note}), the unanswered "
    "questions, the failed or blocked checks, who posted and submitted it and when, the browser user "
    "agent, and ledger_seq (posted / submitted / now): pass ledger_seq.posted as since_seq to "
    "haybale-studio_get_errors for the errors logged during the check. Answers are stored as they "
    "are given, so an open questionnaire returns the answers so far. Reading a submitted "
    "questionnaire takes it out of the studio (closed: 'read'); its Findings stay readable until the "
    "next post. closed: 'discarded' means the user discarded it.",
    registry_id="get_findings",
    annotations=ToolAnnotations(read_only_hint=False, idempotent_hint=True),
    requires=AccessTier.VIEW,
)
class StudioGetFindingsTool(Farmhand):
    async def run(self, ctx: FarmhandContext) -> dict:
        state = ctx.state(QuestionnaireState)
        findings = state.findings()
        if findings is None:
            raise FarmhandError(
                "no_questionnaire",
                "No questionnaire has been posted.",
                help="Post one with haybale-studio_post_questionnaire first.",
            )
        if findings["status"] == SUBMITTED and findings["closed"] is None:
            state.close(READ, principal=ctx.principal)
            findings = state.findings() or findings
        failed = findings["failed_checks"]
        findings["summary"] = (
            f"Questionnaire {findings['id']!r} is {findings['status']}"
            f"{' (incomplete)' if findings['incomplete'] else ''}: "
            f"{len(findings['answers'])} answers, {len(findings['unanswered'])} unanswered, "
            f"{len(failed)} failed or blocked checks."
        )
        if findings["closed"]:
            findings["summary"] += f" It is {findings['closed']} and no longer shown in the studio."
        return findings
