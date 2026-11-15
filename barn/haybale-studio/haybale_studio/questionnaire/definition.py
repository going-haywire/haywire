"""A Questionnaire's definition: the supported SurveyJS subset, its validator and its walkers.

The definition is SurveyJS JSON restricted to the types and properties in
:data:`TYPE_PROPERTIES`, plus the ``check`` element (``do`` / ``expect``,
answered with a verdict and a note). :func:`validate` rejects anything else;
the walkers below answer what the editor and the Findings need: which
questions there are, which are visible, answered or required. See ADR 0083.

Example::

    issues = validate(definition)          # [] when it is inside the subset
    pages = pages_of(definition)           # top-level elements become one page
    names = unanswered(definition, answers)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Mapping

from haybale_studio.questionnaire.expressions import Expression, ExpressionError, parse_expression

FORMAT_URI = "farmhand://docs/reference/questionnaire.md"
"""The canon page that teaches the format; validator errors point to it."""

VERDICTS = ("pass", "fail", "blocked", "skip")
"""The verdicts a Check is answered with."""

NOTE_VERDICTS = ("fail", "blocked")
"""The verdicts that open a Check's note field."""

CONDITIONS = ("visibleIf", "enableIf", "requiredIf")

_QUESTION_COMMON = {"type", "name", "title", "description", "isRequired", *CONDITIONS}
_CHOICE_PROPS = {"choices", "colCount", "showOtherItem", "otherText"}

TYPE_PROPERTIES: dict[str, set[str]] = {
    "boolean": _QUESTION_COMMON | {"labelTrue", "labelFalse"},
    "radiogroup": _QUESTION_COMMON | _CHOICE_PROPS,
    "checkbox": _QUESTION_COMMON | _CHOICE_PROPS,
    "dropdown": _QUESTION_COMMON | {"choices", "placeholder"},
    "text": _QUESTION_COMMON | {"inputType", "placeholder", "min", "max", "step"},
    "comment": _QUESTION_COMMON | {"placeholder", "rows"},
    "rating": _QUESTION_COMMON
    | {"rateMin", "rateMax", "rateStep", "rateType", "minRateDescription", "maxRateDescription"},
    "ranking": _QUESTION_COMMON | {"choices"},
    "check": _QUESTION_COMMON | {"do", "expect"},
    "html": {"type", "name", "html", "visibleIf"},
    "panel": {"type", "name", "title", "description", "elements", "state", "visibleIf", "enableIf"},
}
"""Every supported element type and the properties it accepts."""

QUESTIONNAIRE_PROPERTIES = {
    "title",
    "description",
    "pages",
    "elements",
    "showProgressBar",
    "showQuestionNumbers",
    "completedHtml",
}
PAGE_PROPERTIES = {"name", "title", "description", "elements", "visibleIf"}

INPUT_TYPES = ("text", "number", "date", "color", "range", "email", "url")
RATE_TYPES = ("labels", "stars")
PANEL_STATES = ("default", "expanded", "collapsed")

_UNANSWERED_TYPES = {"html", "panel"}


@dataclass(frozen=True)
class Issue:
    """One thing outside the subset: where it is, which property, and what is wrong."""

    where: str
    """The element's path, such as ``pages[1].elements[0] 'login'``."""
    property: str
    message: str

    def __str__(self) -> str:
        prop = f" {self.property}:" if self.property else ""
        return f"{self.where}{prop} {self.message}"


def validate(definition: Any) -> list[Issue]:
    """Return every place ``definition`` leaves the supported subset; empty when it is valid."""
    issues: list[Issue] = []
    if not isinstance(definition, dict):
        return [Issue("questionnaire", "", "must be a JSON object.")]
    _unknown(definition, QUESTIONNAIRE_PROPERTIES, "questionnaire", issues)
    has_pages, has_elements = "pages" in definition, "elements" in definition
    if has_pages == has_elements:
        issues.append(
            Issue("questionnaire", "pages", "give either 'pages' or 'elements', not both or neither.")
        )
        return issues

    names: dict[str, str] = {}
    conditions: list[tuple[str, str, Expression]] = []
    if has_pages:
        pages = definition["pages"]
        if not isinstance(pages, list) or not pages:
            issues.append(Issue("questionnaire", "pages", "must be a non-empty list of pages."))
            return issues
        for i, page in enumerate(pages):
            where = f"pages[{i}]"
            if not isinstance(page, dict):
                issues.append(Issue(where, "", "must be an object."))
                continue
            _unknown(page, PAGE_PROPERTIES, where, issues)
            _condition(page, "visibleIf", where, issues, conditions)
            _elements(page.get("elements"), where, issues, names, conditions)
    else:
        _elements(definition["elements"], "questionnaire", issues, names, conditions)

    for where, prop, expr in conditions:
        for ref in sorted(expr.references - names.keys()):
            issues.append(Issue(where, prop, f"refers to {{{ref}}}, which is no question's name."))
    return issues


def _unknown(obj: dict, allowed: set[str], where: str, issues: list[Issue]) -> None:
    for key in obj:
        if key not in allowed:
            issues.append(
                Issue(where, key, f"is not supported here; allowed: {', '.join(sorted(allowed))}.")
            )


def _condition(
    obj: dict, prop: str, where: str, issues: list[Issue], conditions: list[tuple[str, str, Expression]]
) -> None:
    if prop not in obj:
        return
    source = obj[prop]
    if not isinstance(source, str):
        issues.append(Issue(where, prop, "must be an expression string."))
        return
    try:
        conditions.append((where, prop, parse_expression(source)))
    except ExpressionError as exc:
        issues.append(Issue(where, prop, str(exc)))


def _elements(
    elements: Any,
    where: str,
    issues: list[Issue],
    names: dict[str, str],
    conditions: list[tuple[str, str, Expression]],
) -> None:
    if not isinstance(elements, list) or not elements:
        issues.append(Issue(where, "elements", "must be a non-empty list of elements."))
        return
    for i, element in enumerate(elements):
        here = f"{where}.elements[{i}]"
        if not isinstance(element, dict):
            issues.append(Issue(here, "", "must be an object."))
            continue
        name = element.get("name")
        if isinstance(name, str):
            here = f"{here} '{name}'"
        kind = element.get("type")
        if kind not in TYPE_PROPERTIES:
            issues.append(
                Issue(
                    here,
                    "type",
                    f"{kind!r} is not supported; use one of {', '.join(sorted(TYPE_PROPERTIES))}.",
                )
            )
            continue
        _unknown(element, TYPE_PROPERTIES[kind], here, issues)
        for prop in CONDITIONS:
            _condition(element, prop, here, issues, conditions)
        if kind not in _UNANSWERED_TYPES:
            if not isinstance(name, str) or not name:
                issues.append(Issue(here, "name", "is required: answers are keyed by it."))
            elif name in names:
                issues.append(Issue(here, "name", f"repeats the name of {names[name]}."))
            else:
                names[name] = here
        _type_rules(kind, element, here, issues)
        if kind == "panel":
            _elements(element.get("elements"), here, issues, names, conditions)


def _type_rules(kind: str, element: dict, where: str, issues: list[Issue]) -> None:
    if kind in ("radiogroup", "checkbox", "dropdown", "ranking"):
        choices = element.get("choices")
        if not isinstance(choices, list) or not choices:
            issues.append(Issue(where, "choices", "must be a non-empty list."))
        else:
            for choice in choices:
                if isinstance(choice, dict):
                    if "value" not in choice or set(choice) - {"value", "text"}:
                        issues.append(
                            Issue(where, "choices", "an object choice has 'value' and optional 'text'.")
                        )
                elif not isinstance(choice, (str, int, float)):
                    issues.append(
                        Issue(where, "choices", "each choice is a string, a number or {value, text}.")
                    )
    if kind == "check":
        for prop in ("do", "expect"):
            if not isinstance(element.get(prop), str) or not element[prop].strip():
                issues.append(Issue(where, prop, "is required: say what to do and what should happen."))
    if kind == "html" and not isinstance(element.get("html"), str):
        issues.append(Issue(where, "html", "is required and must be a string."))
    if kind == "text" and element.get("inputType", "text") not in INPUT_TYPES:
        issues.append(Issue(where, "inputType", f"use one of {', '.join(INPUT_TYPES)}."))
    if kind == "rating":
        if element.get("rateType", "labels") not in RATE_TYPES:
            issues.append(Issue(where, "rateType", f"use one of {', '.join(RATE_TYPES)}."))
        low, high = element.get("rateMin", 1), element.get("rateMax", 5)
        if not isinstance(low, int) or not isinstance(high, int) or low >= high or high - low > 20:
            issues.append(
                Issue(
                    where,
                    "rateMin",
                    "rateMin and rateMax are integers, rateMin < rateMax, at most 20 apart.",
                )
            )
    if kind == "panel" and element.get("state", "default") not in PANEL_STATES:
        issues.append(Issue(where, "state", f"use one of {', '.join(PANEL_STATES)}."))


# ---------------------------------------------------------------------------
# Walkers — on a definition that passed validate()
# ---------------------------------------------------------------------------


def pages_of(definition: Mapping[str, Any]) -> list[dict]:
    """Return the pages; a definition with top-level ``elements`` is one page."""
    if "pages" in definition:
        return list(definition["pages"])
    return [{"elements": definition.get("elements", [])}]


def choice_items(choices: list) -> list[tuple[Any, str]]:
    """Return ``(value, label)`` for each choice, a plain value being its own label."""
    items: list[tuple[Any, str]] = []
    for choice in choices:
        if isinstance(choice, dict):
            items.append((choice["value"], str(choice.get("text", choice["value"]))))
        else:
            items.append((choice, str(choice)))
    return items


def walk(definition: Mapping[str, Any]) -> Iterator[tuple[dict, tuple[dict, ...]]]:
    """Yield every element with its containers (page first, then panels), in order."""

    def _walk(elements: list, parents: tuple[dict, ...]) -> Iterator[tuple[dict, tuple[dict, ...]]]:
        for element in elements:
            yield element, parents
            if element.get("type") == "panel":
                yield from _walk(element.get("elements", []), (*parents, element))

    for page in pages_of(definition):
        yield from _walk(page.get("elements", []), (page,))


def questions(definition: Mapping[str, Any]) -> Iterator[tuple[dict, tuple[dict, ...]]]:
    """Yield every element that takes an answer, with its containers."""
    for element, parents in walk(definition):
        if element.get("type") not in _UNANSWERED_TYPES:
            yield element, parents


def answer_keys(definition: Mapping[str, Any]) -> set[str]:
    """Return every key an answer may be stored under.

    That is each question's name, and ``<name>-Comment`` for a question with an "Other" item.
    """
    keys: set[str] = set()
    for element, _parents in questions(definition):
        keys.add(element["name"])
        if element.get("showOtherItem"):
            keys.add(f"{element['name']}-Comment")
    return keys


def expression_values(definition: Mapping[str, Any], answers: Mapping[str, Any]) -> dict[str, Any]:
    """Return the values conditions see: the answers, with each Check reduced to its verdict."""
    values = dict(answers)
    for element, _parents in questions(definition):
        if element.get("type") == "check":
            answer = answers.get(element["name"])
            values[element["name"]] = answer.get("verdict") if isinstance(answer, dict) else None
    return values


def condition_holds(obj: Mapping[str, Any], prop: str, values: Mapping[str, Any], default: bool) -> bool:
    """Return the truth of ``obj[prop]``, or ``default`` when it has none."""
    source = obj.get(prop)
    if not source:
        return default
    return parse_expression(source).evaluate(values)


def is_visible(element: Mapping[str, Any], parents: tuple[dict, ...], values: Mapping[str, Any]) -> bool:
    """Return whether the element and every container around it are visible."""
    return all(condition_holds(obj, "visibleIf", values, True) for obj in (*parents, element))


def is_required(element: Mapping[str, Any], values: Mapping[str, Any]) -> bool:
    """Return whether the element must be answered: ``isRequired`` or a true ``requiredIf``."""
    return bool(element.get("isRequired")) or condition_holds(element, "requiredIf", values, False)


def is_answered(element: Mapping[str, Any], answer: Any) -> bool:
    """Return whether ``answer`` answers the element; a Check needs a verdict."""
    if element.get("type") == "check":
        return isinstance(answer, dict) and answer.get("verdict") in VERDICTS
    if element.get("type") == "boolean":
        return isinstance(answer, bool)
    return answer is not None and answer != "" and answer != []


def unanswered(definition: Mapping[str, Any], answers: Mapping[str, Any]) -> list[str]:
    """Return the names of the visible questions not yet answered."""
    values = expression_values(definition, answers)
    return [
        element["name"]
        for element, parents in questions(definition)
        if is_visible(element, parents, values) and not is_answered(element, answers.get(element["name"]))
    ]


def visible_answers(definition: Mapping[str, Any], answers: Mapping[str, Any]) -> dict[str, Any]:
    """Return ``answers`` without those of hidden questions, as SurveyJS keeps them on completion.

    Dropping an answer can hide further questions, so it repeats until nothing changes.
    """
    kept = dict(answers)
    while True:
        values = expression_values(definition, kept)
        hidden: set[str] = set()
        for element, parents in questions(definition):
            if not is_visible(element, parents, values):
                hidden |= {element["name"], f"{element['name']}-Comment"}
        dropped = {key: value for key, value in kept.items() if key not in hidden}
        if dropped == kept:
            return kept
        kept = dropped


def missing_required(
    definition: Mapping[str, Any], answers: Mapping[str, Any], page: Mapping[str, Any] | None = None
) -> list[str]:
    """Return the names of the visible required questions not yet answered, on ``page`` or everywhere."""
    values = expression_values(definition, answers)
    return [
        element["name"]
        for element, parents in questions(definition)
        if (page is None or parents[0] is page)
        and is_visible(element, parents, values)
        and is_required(element, values)
        and not is_answered(element, answers.get(element["name"]))
    ]


def failed_checks(definition: Mapping[str, Any], answers: Mapping[str, Any]) -> list[str]:
    """Return the names of the Checks answered ``fail`` or ``blocked``."""
    return [
        element["name"]
        for element, _parents in questions(definition)
        if element.get("type") == "check"
        and isinstance(answers.get(element["name"]), dict)
        and answers[element["name"]].get("verdict") in NOTE_VERDICTS
    ]
