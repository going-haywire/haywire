"""QuestionnaireForm — draws a Questionnaire's definition with NiceGUI and reports each answer.

One builder per element type (:data:`_BUILDERS`). The form keeps a field per
question name, so answers arriving from elsewhere update the fields in place
(:meth:`QuestionnaireForm.apply`) without redrawing, and conditions are
re-evaluated after every change. Text commits on blur or Enter, not per keystroke.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from nicegui import ui

# make_sortable imports Sortable lazily, after the page's importmap was written.
from nicegui.elements.sortable.sortable import Sortable as _Sortable  # noqa: F401

from haywire.ui import elements as hui

from haybale_studio.questionnaire.definition import (
    NOTE_VERDICTS,
    VERDICTS,
    choice_items,
    condition_holds,
    expression_values,
    is_required,
    missing_required,
    pages_of,
)

OTHER = "other"
"""The value of a choice question's "Other" item; its text goes under ``<name>-Comment``."""

_VERDICT_LABELS = {"pass": "Pass", "fail": "Fail", "blocked": "Blocked", "skip": "Skip"}

AnswerCallback = Callable[[str, Any], None]


@dataclass
class _Field:
    """A drawn question: its wrapper, how to show a value, and how to enable it."""

    element: dict
    wrapper: ui.element
    set_value: Callable[[Any], object]
    inputs: list[Any] = field(default_factory=list)
    required_mark: Optional[ui.label] = None
    error: Optional[ui.label] = None


class QuestionnaireForm:
    """Draws a validated Questionnaire definition page by page.

    Args:
        definition: A definition that passed
            :func:`haybale_studio.questionnaire.definition.validate`.
        answers: The answers so far, question name → value.
        on_answer: Called with ``(name, value)`` for each answer the user gives;
            ``value`` is ``None`` when the answer is cleared.
        read_only: Draw every field disabled.

    Example::

        form = QuestionnaireForm(definition, answers, on_answer=store.set_answer)
        form.build()                 # inside the container to draw into
        form.apply(new_answers)      # another session answered: update in place
        form.show_missing(["q3"])    # mark unanswered required questions, go to the first
    """

    def __init__(
        self,
        definition: Mapping[str, Any],
        answers: Mapping[str, Any],
        *,
        on_answer: AnswerCallback,
        read_only: bool = False,
    ) -> None:
        self._definition = definition
        self._answers: dict[str, Any] = dict(answers)
        self._on_answer = on_answer
        self._read_only = read_only
        self._pages = pages_of(definition)
        self._page_boxes: list[ui.element] = []
        self._page_index = 0
        self._fields: dict[str, _Field] = {}
        self._conditional: list[tuple[dict, ui.element]] = []
        self._applying = False
        self._number = 0
        self._nav: Optional[ui.row] = None
        self._progress: Optional[ui.linear_progress] = None

    # -- drawing -------------------------------------------------------------

    def build(self) -> None:
        """Draw the form into the current container."""
        definition = self._definition
        with ui.column().classes("w-full gap-3"):
            if definition.get("title"):
                hui.heading(str(definition["title"]))
            if definition.get("description"):
                hui.hint(str(definition["description"]))
            if len(self._pages) > 1 and definition.get("showProgressBar", "off") not in ("off", False):
                self._progress = ui.linear_progress(show_value=False, size="4px")
            for page in self._pages:
                with ui.column().classes("w-full gap-3") as box:
                    if page.get("title"):
                        hui.section_label(str(page["title"]))
                    if page.get("description"):
                        hui.hint(str(page["description"]))
                    self._build_elements(page.get("elements", []))
                self._page_boxes.append(box)
            if len(self._pages) > 1:
                self._nav = ui.row().classes("w-full items-center gap-2")
        self._refresh()

    def _build_elements(self, elements: list) -> None:
        for element in elements:
            with ui.column().classes("w-full gap-1") as wrapper:
                kind = element["type"]
                if kind == "panel":
                    self._build_panel(element)
                elif kind == "html":
                    ui.html(element["html"], sanitize=True).classes("w-full text-sm")
                else:
                    self._build_question(element, wrapper)
            if any(element.get(prop) for prop in ("visibleIf", "enableIf", "requiredIf")):
                self._conditional.append((element, wrapper))

    def _build_panel(self, element: dict) -> None:
        state = element.get("state", "default")
        if state in ("expanded", "collapsed"):
            with hui.expansion_section(str(element.get("title", "")), default_open=state == "expanded"):
                if element.get("description"):
                    hui.hint(str(element["description"]))
                self._build_elements(element.get("elements", []))
            return
        with hui.box():
            if element.get("title"):
                hui.section_label(str(element["title"]))
            if element.get("description"):
                hui.hint(str(element["description"]))
            self._build_elements(element.get("elements", []))

    def _build_question(self, element: dict, wrapper: ui.element) -> None:
        name = element["name"]
        numbered = self._definition.get("showQuestionNumbers", "on") not in ("off", False)
        self._number += 1
        title = str(element.get("title") or name)
        with ui.row().classes("items-baseline gap-1 no-wrap"):
            if numbered:
                hui.hint(f"{self._number}.")
            ui.label(title).classes("text-sm font-medium")
            required_mark = ui.label("*").classes("hw-text-danger text-sm")
        if element.get("description"):
            hui.hint(str(element["description"]))
        built = _BUILDERS[element["type"]](self, element)
        built.wrapper = wrapper
        built.required_mark = required_mark
        built.error = hui.error_label("Answer this question.").classes("p-0")
        built.error.set_visibility(False)
        self._fields[name] = built
        self._applying = True
        try:
            built.set_value(self._answers.get(name))
        finally:
            self._applying = False
        if self._read_only:
            for item in built.inputs:
                item.disable()

    # -- answers -------------------------------------------------------------

    def commit(self, name: str, value: Any) -> None:
        """Record the user's answer to ``name`` and report it, unless it echoes :meth:`apply`."""
        if self._applying or self._read_only:
            return
        if value is None or value == "" or value == []:
            if name not in self._answers:
                return
            self._answers.pop(name)
            value = None
        elif self._answers.get(name) == value:
            return
        else:
            self._answers[name] = value
        field_ = self._fields.get(name)
        if field_ is not None and field_.error is not None:
            field_.error.set_visibility(False)
        self._on_answer(name, value)
        self._refresh()

    def apply(self, answers: Mapping[str, Any]) -> None:
        """Show ``answers`` in the fields whose value differs, without reporting them back."""
        changed = [
            name
            for name in set(self._answers) | set(answers)
            if self._answers.get(name) != answers.get(name)
        ]
        if not changed:
            return
        self._answers = dict(answers)
        self._applying = True
        try:
            for name in changed:
                base = name.removesuffix("-Comment")
                if base in self._fields:
                    self._fields[base].set_value(self._answers.get(base))
        finally:
            self._applying = False
        self._refresh()

    def answer(self, name: str) -> Any:
        """Return the form's current answer to ``name``."""
        return self._answers.get(name)

    def show_missing(self, names: list[str]) -> None:
        """Mark the questions ``names`` as unanswered and go to the page of the first."""
        for name in names:
            field_ = self._fields.get(name)
            if field_ is not None and field_.error is not None:
                field_.error.set_visibility(True)
        for index, box in enumerate(self._page_boxes):
            if any(self._fields[n].wrapper in box.descendants() for n in names if n in self._fields):
                self._go(index)
                return

    # -- conditions and pages -------------------------------------------------

    def _values(self) -> dict[str, Any]:
        return expression_values(self._definition, self._answers)

    def _refresh(self) -> None:
        values = self._values()
        for element, wrapper in self._conditional:
            wrapper.set_visibility(condition_holds(element, "visibleIf", values, True))
            field_ = self._fields.get(element.get("name", ""))
            if field_ is not None and not self._read_only:
                enabled = condition_holds(element, "enableIf", values, True)
                for item in field_.inputs:
                    item.set_enabled(enabled)
        for field_ in self._fields.values():
            if field_.required_mark is not None:
                field_.required_mark.set_visibility(is_required(field_.element, values))
        self._go(
            self._page_index if self._page_visible(self._page_index, values) else self._first_visible(values)
        )

    def _page_visible(self, index: int, values: Mapping[str, Any]) -> bool:
        return 0 <= index < len(self._pages) and condition_holds(
            self._pages[index], "visibleIf", values, True
        )

    def _first_visible(self, values: Mapping[str, Any]) -> int:
        return next((i for i in range(len(self._pages)) if self._page_visible(i, values)), 0)

    def _step(self, direction: int) -> None:
        values = self._values()
        if direction > 0 and not self._read_only:
            missing = missing_required(self._definition, self._answers, self._pages[self._page_index])
            if missing:
                self.show_missing(missing)
                return
        index = self._page_index + direction
        while 0 <= index < len(self._pages) and not self._page_visible(index, values):
            index += direction
        if 0 <= index < len(self._pages):
            self._go(index)

    def _go(self, index: int) -> None:
        self._page_index = index
        for i, box in enumerate(self._page_boxes):
            box.set_visibility(i == index)
        if self._nav is None:
            return
        values = self._values()
        visible = [i for i in range(len(self._pages)) if self._page_visible(i, values)]
        position = visible.index(index) + 1 if index in visible else 1
        if self._progress is not None:
            self._progress.set_value(position / max(len(visible), 1))
        self._nav.clear()
        with self._nav:
            ui.button("Back", on_click=lambda: self._step(-1)).props("flat dense no-caps").set_enabled(
                position > 1
            )
            hui.hint(f"Page {position} of {len(visible)}")
            ui.space()
            ui.button("Next", on_click=lambda: self._step(1)).props("flat dense no-caps").set_enabled(
                position < len(visible)
            )


# ---------------------------------------------------------------------------
# Builders — one per element type; each returns the drawn _Field
# ---------------------------------------------------------------------------


def _text_commit(form: QuestionnaireForm, name: str, widget: Any, *, enter: bool = True) -> None:
    """Commit ``widget``'s value on blur (and on Enter for single-line fields)."""
    widget.on("blur", lambda: form.commit(name, widget.value))
    if enter:
        widget.on("keydown.enter", lambda: form.commit(name, widget.value))


def _build_boolean(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    options = {True: str(element.get("labelTrue", "Yes")), False: str(element.get("labelFalse", "No"))}
    toggle = ui.toggle(options, clearable=True, on_change=lambda e: form.commit(name, e.value)).props(
        "dense no-caps"
    )
    return _Field(element, toggle, lambda v: toggle.set_value(v if isinstance(v, bool) else None), [toggle])


def _other_input(form: QuestionnaireForm, element: dict) -> Optional[ui.input]:
    if not element.get("showOtherItem"):
        return None
    key = f"{element['name']}-Comment"
    other = hui.input_field(placeholder="Describe…")
    _text_commit(form, key, other)
    return other


def _choice_options(element: dict) -> dict[Any, str]:
    options = dict(choice_items(element["choices"]))
    if element.get("showOtherItem"):
        options[OTHER] = str(element.get("otherText", "Other"))
    return options


def _build_radiogroup(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    radio = ui.radio(_choice_options(element), on_change=lambda e: _on_choice(e.value)).props("dense")
    if element.get("colCount", 1) != 1:
        radio.props("inline")
    other = _other_input(form, element)

    def _on_choice(value: Any) -> None:
        if other is not None:
            other.set_visibility(value == OTHER)
        form.commit(name, value)

    def _set(value: Any) -> None:
        radio.set_value(value)
        if other is not None:
            other.set_visibility(value == OTHER)
            other.set_value(form.answer(f"{name}-Comment") or "")

    return _Field(element, radio, _set, [radio] + ([other] if other is not None else []))


def _build_checkbox(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    options = _choice_options(element)
    boxes: dict[Any, ui.checkbox] = {}
    row_classes = "gap-x-4 gap-y-0 flex-wrap" if element.get("colCount", 1) != 1 else "gap-0 flex-col"
    with ui.row().classes(row_classes):
        for value, label in options.items():
            boxes[value] = ui.checkbox(label, on_change=lambda _e: _on_tick()).props("dense")
    other = _other_input(form, element)

    def _selected() -> list:
        return [value for value, box in boxes.items() if box.value]

    def _on_tick() -> None:
        if other is not None:
            other.set_visibility(OTHER in _selected())
        form.commit(name, _selected())

    def _set(value: Any) -> None:
        chosen = value if isinstance(value, list) else []
        for option, box in boxes.items():
            box.set_value(option in chosen)
        if other is not None:
            other.set_visibility(OTHER in chosen)
            other.set_value(form.answer(f"{name}-Comment") or "")

    inputs: list[Any] = list(boxes.values()) + ([other] if other is not None else [])
    return _Field(element, inputs[0], _set, inputs)


def _build_dropdown(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    select = hui.select_field(
        options=dict(choice_items(element["choices"])),
        label=element.get("placeholder"),
        on_change=lambda e: form.commit(name, e.value),
        clearable=True,
    )
    return _Field(element, select, select.set_value, [select])


def _build_text(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    kind = element.get("inputType", "text")
    if kind == "range":
        slider = ui.slider(
            min=element.get("min", 0), max=element.get("max", 100), step=element.get("step", 1)
        ).props("label")
        slider.on("change", lambda: form.commit(name, slider.value))
        return _Field(
            element,
            slider,
            lambda v: slider.set_value(v if v is not None else slider.props["min"]),
            [slider],
        )
    if kind == "color":
        color = (
            ui.color_input(on_change=lambda e: form.commit(name, e.value)).classes("w-full").props("dense")
        )
        return _Field(element, color, lambda v: color.set_value(v or ""), [color])
    if kind == "number":
        number = hui.number_field(
            min=element.get("min"), max=element.get("max"), step=element.get("step", 1)
        )
        number.set_value(None)
        _text_commit(form, name, number)
        return _Field(element, number, number.set_value, [number])
    widget = hui.input_field(placeholder=element.get("placeholder"))
    if kind != "text":
        widget.props(f"type={kind}")
    _text_commit(form, name, widget)
    return _Field(element, widget, lambda v: widget.set_value(v or ""), [widget])


def _build_comment(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    area = (
        ui.textarea(placeholder=element.get("placeholder"))
        .classes("w-full")
        .props(f"dense autogrow rows={int(element.get('rows', 3))}")
    )
    _text_commit(form, name, area, enter=False)
    return _Field(element, area, lambda v: area.set_value(v or ""), [area])


def _build_rating(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    low, high = int(element.get("rateMin", 1)), int(element.get("rateMax", 5))
    widget: ui.element
    if element.get("rateType") == "stars":
        stars = ui.rating(max=high, on_change=lambda e: form.commit(name, int(e.value) if e.value else None))
        widget = stars
        setter: Callable[[Any], object] = lambda v: stars.set_value(v or 0)  # noqa: E731
    else:
        step = int(element.get("rateStep", 1))
        toggle = ui.toggle(
            list(range(low, high + 1, step)), clearable=True, on_change=lambda e: form.commit(name, e.value)
        ).props("dense")
        widget = toggle
        setter = toggle.set_value
    if element.get("minRateDescription") or element.get("maxRateDescription"):
        with ui.row().classes("w-full gap-2"):
            hui.hint(str(element.get("minRateDescription", "")))
            ui.space()
            hui.hint(str(element.get("maxRateDescription", "")))
    return _Field(element, widget, setter, [widget])


def _build_ranking(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    labels = dict(choice_items(element["choices"]))
    order: list[Any] = list(labels)
    box = ui.column().classes("w-full gap-1")
    box.make_sortable(group=f"hw-ranking:{box.id}", on_end=lambda e: _moved(e.old_index, e.new_index))

    def _draw() -> None:
        box.clear()
        with box:
            for position, value in enumerate(order, start=1):
                with ui.row().classes(
                    "w-full items-center gap-2 px-2 py-1 rounded cursor-grab hw-list-item-hover"
                ):
                    ui.icon(hui.icon.drag_handle, size="16px")
                    ui.label(f"{position}. {labels[value]}").classes("text-sm")

    def _moved(old: int, new: int) -> None:
        order.insert(new, order.pop(old))
        _draw()
        form.commit(name, list(order))

    def _set(value: Any) -> None:
        if isinstance(value, list) and sorted(map(str, value)) == sorted(map(str, labels)):
            order[:] = value
        else:
            order[:] = list(labels)
        _draw()

    return _Field(element, box, _set, [box])


def _build_check(form: QuestionnaireForm, element: dict) -> _Field:
    name = element["name"]
    ui.markdown(f"**Do:** {element['do']}").classes("text-sm w-full")
    ui.markdown(f"**Expect:** {element['expect']}").classes("text-sm w-full")
    verdict = ui.toggle(
        {v: _VERDICT_LABELS[v] for v in VERDICTS}, clearable=True, on_change=lambda e: _on_verdict(e.value)
    ).props("dense no-caps")
    note = ui.textarea(placeholder="What happened?").classes("w-full").props("dense autogrow rows=2")
    note.on("blur", lambda: _commit())

    def _commit() -> None:
        if verdict.value is None:
            form.commit(name, None)
            return
        answer: dict[str, Any] = {"verdict": verdict.value}
        if note.value and verdict.value in NOTE_VERDICTS:
            answer["note"] = note.value
        form.commit(name, answer)

    def _on_verdict(value: Any) -> None:
        note.set_visibility(value in NOTE_VERDICTS)
        _commit()

    def _set(value: Any) -> None:
        answer = value if isinstance(value, dict) else {}
        verdict.set_value(answer.get("verdict"))
        note.set_value(answer.get("note", ""))
        note.set_visibility(answer.get("verdict") in NOTE_VERDICTS)

    return _Field(element, verdict, _set, [verdict, note])


_BUILDERS: dict[str, Callable[[QuestionnaireForm, dict], _Field]] = {
    "boolean": _build_boolean,
    "radiogroup": _build_radiogroup,
    "checkbox": _build_checkbox,
    "dropdown": _build_dropdown,
    "text": _build_text,
    "comment": _build_comment,
    "rating": _build_rating,
    "ranking": _build_ranking,
    "check": _build_check,
}
