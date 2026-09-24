"""Per-step body content for the New Node flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.core.node.info import NodeInfo
from haywire.ui import elements as hui
from haywire.ui.components.stepper import advance, busy_advance

from ._state import NewNodeFlow

_NO_TARGET_HELP = (
    "A new node needs a library installed with 'pip install -e' that registers a nodes/ folder and "
    "watches its files. 'haywire init' creates a project with one."
)


#: Wide enough for the longest plan-row label.
_INFO_WIDTH = "w-40"


def _refusal_row(text: str) -> None:
    with ui.row().classes("w-full items-center gap-2 mt-1"):
        ui.icon("error", size="16px").classes("hw-text-danger")
        ui.label(text).classes("text-sm hw-text-danger")


def _close(flow: NewNodeFlow) -> None:
    if flow.popup is not None:
        flow.popup.close()


def _then_close(flow: NewNodeFlow, action: Callable[[], None]) -> Callable[[], None]:
    """``action``, then close the wizard."""

    def _run() -> None:
        action()
        _close(flow)

    return _run


# ── source ───────────────────────────────────────────────────────────────────


def _panel_source(flow: NewNodeFlow, rerender: Callable[[], None]) -> None:
    """Pick a Node template or a node class to clone. Picking a row advances."""
    ui.label("Start a new node from a template or from an existing node.").classes("text-xs hw-text-dim")

    ui.toggle(
        {"template": "Template", "clone": "Clone a node"},
        value=flow.mode,
        on_change=lambda e: _on_mode(flow, e.value, rerender),
    ).props("dense no-caps")

    search = ui.input(placeholder="Search…", value=flow.query).classes("w-full")
    search.props("dense outlined clearable autofocus")
    results = ui.column().classes("w-full gap-0").style("max-height: 50vh; overflow-y: auto;")

    def _fill() -> None:
        results.clear()
        with results:
            _source_list(flow, rerender)

    def _on_query(value: str | None) -> None:
        flow.query = value or ""
        _fill()

    # ui.input emits `update:value`; on_value_change binds it.
    search.on_value_change(lambda e: _on_query(e.value))
    _fill()


def _on_mode(flow: NewNodeFlow, mode: str, rerender: Callable[[], None]) -> None:
    flow.mode = "clone" if mode == "clone" else "template"
    rerender()


def _source_list(flow: NewNodeFlow, rerender: Callable[[], None]) -> None:
    rows = flow.source_rows()
    if not rows:
        empty = "No templates match." if flow.mode == "template" else "No nodes match."
        ui.label(empty).classes("text-sm hw-text-muted p-2")
        return

    group: str | None = None
    for row_group, info in rows:
        if row_group != group:
            group = row_group
            ui.label(group).classes("text-xs font-semibold hw-text-dim mt-2")
        _source_row(flow, info, rerender)


def _source_row(flow: NewNodeFlow, info: NodeInfo, rerender: Callable[[], None]) -> None:
    async def _go() -> None:
        if flow.pick(info):
            await flow.advance_from_source()

    library = info.library.label if info.library is not None else ""
    with hui.menu_row(info.identity.label, on_click=lambda: advance(rerender, _go)):
        if library:
            ui.badge(library).classes("shrink-0 ml-2 text-xs hw-text-dim")
    if info.identity.description:
        ui.label(info.identity.description).classes("text-xs hw-text-muted pl-2 truncate")


# ── details ──────────────────────────────────────────────────────────────────


def _panel_details(flow: NewNodeFlow, rerender: Callable[[], None]) -> None:
    """The new node's identity and the library it goes into. Nothing written yet."""
    if not flow.targets:
        _refusal_row("No library in this project can receive a node.")
        ui.label(_NO_TARGET_HELP).classes("text-xs hw-text-muted")
        return

    if flow.source_cls is not None:
        source_label = flow.source_cls.class_identity.label
        ui.label(f"Starting from {source_label}").classes("text-xs hw-text-dim")

    label_input = ui.input(label="Label", value=flow.fields.label).classes("w-full")
    label_input.props("dense outlined autofocus")
    class_input = ui.input(label="Class name", value=flow.fields.class_name).classes("w-full")
    class_input.props("dense outlined")
    file_label = ui.label(flow.file_name).classes("text-xs font-mono hw-text-dim")

    ui.select(
        options=sorted({*flow.menu_paths, flow.fields.menu}),
        value=flow.fields.menu,
        label="Menu",
        with_input=True,
        new_value_mode="add-unique",
        on_change=lambda e: setattr(flow.fields, "menu", e.value or ""),
    ).classes("w-full").props("dense outlined")

    ui.select(
        options=list(flow.fields.search_tags),
        value=list(flow.fields.search_tags),
        label="Tags",
        multiple=True,
        with_input=True,
        new_value_mode="add-unique",
        on_change=lambda e: setattr(flow.fields, "search_tags", list(e.value or [])),
    ).classes("w-full").props("dense outlined use-chips")

    ui.textarea(
        label="Description",
        value=flow.fields.description,
        on_change=lambda e: setattr(flow.fields, "description", e.value or ""),
    ).classes("w-full").props("dense outlined autogrow")

    if len(flow.targets) > 1:
        ui.select(
            {t.library_id: t.label for t in flow.targets},
            label="Library",
            value=flow.target.library_id if flow.target else None,
            on_change=lambda e: _on_target(e.value),
        ).classes("w-full").props("dense outlined")
    elif flow.target is not None:
        ui.label(f"Into {flow.target.label}").classes("text-xs hw-text-dim")

    refusal_label = ui.label("").classes("text-xs hw-text-danger")

    with ui.row().classes("w-full justify-end gap-2"):
        if flow.templates or flow.clone_sources:
            ui.button("Back", on_click=lambda: _back(flow, rerender, "source")).props("flat dense")
        plan_button = ui.button("Continue").props("flat dense").style("color: var(--hw-positive);")
        plan_button.on_click(lambda: busy_advance(rerender, plan_button, flow.advance_from_details))

    def _on_target(library_id: str) -> None:
        flow.set_target(library_id)
        _refresh()

    def _refresh() -> None:
        file_label.set_text(flow.file_name)
        refusal = flow.details_refusal
        refusal_label.set_text(refusal or "")
        plan_button.set_enabled(refusal is None)

    def _on_label(value: str) -> None:
        flow.set_label(value or "")
        if not flow.class_name_edited:
            class_input.set_value(flow.fields.class_name)
        _refresh()

    def _on_class_name(value: str) -> None:
        # set_value from _on_label echoes back here; only a real edit detaches the name.
        if (value or "").strip() != flow.fields.class_name:
            flow.set_class_name(value or "")
        _refresh()

    # Wired after every element exists, since the handlers write to them.
    label_input.on_value_change(lambda e: _on_label(e.value))
    class_input.on_value_change(lambda e: _on_class_name(e.value))
    _refresh()


def _back(flow: NewNodeFlow, rerender: Callable[[], None], step: str):
    """Return to an earlier step. Nothing was written, so there is nothing to undo."""

    async def _go() -> None:
        flow.retry()
        flow.step = step

    return advance(rerender, _go)


# ── planned ──────────────────────────────────────────────────────────────────


def _panel_planned(flow: NewNodeFlow, rerender: Callable[[], None]) -> None:
    """The file that would be written. The next click is the one that writes."""
    plan = flow.plan
    if plan is None:  # pragma: no cover — unreachable via the flow
        return

    ui.label("This will be written:").classes("text-sm font-medium")
    ui.label(str(plan.path)).classes("text-xs font-mono hw-text-dim")

    if plan.refusal is not None:
        _refusal_row(plan.refusal)
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Back", on_click=lambda: _back(flow, rerender, "details")).props("flat dense")
        return

    hui.info_row("Registry key", plan.registry_key, label_width=_INFO_WIDTH)
    mode = "the whole module" if plan.mode == "whole" else "the class and the module's imports"
    hui.info_row("Copies", mode, label_width=_INFO_WIDTH)
    if plan.rewritten_imports:
        hui.info_row("Imports made absolute", str(len(plan.rewritten_imports)), label_width=_INFO_WIDTH)
        for before, after in plan.rewritten_imports:
            ui.label(f"{before}  →  {after}").classes("text-xs font-mono hw-text-muted")
    if plan.free_names:
        hui.info_row("Imported from the source", ", ".join(plan.free_names), label_width=_INFO_WIDTH)
    if plan.linked_additions:
        target = flow.target.label if flow.target is not None else "the library"
        hui.info_row(
            f"New dependency of {target}", ", ".join(plan.linked_additions), label_width=_INFO_WIDTH
        )

    ui.code(plan.source, language="python").classes("w-full text-xs").style(
        "max-height: 40vh; overflow: auto;"
    )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Back", on_click=lambda: _back(flow, rerender, "details")).props("flat dense")
        create = ui.button("Create").props("flat dense").style("color: var(--hw-positive);")
        create.on_click(lambda: busy_advance(rerender, create, flow.advance_from_planned))


# ── result ───────────────────────────────────────────────────────────────────


def _panel_result(flow: NewNodeFlow, _rerender: Callable[[], None]) -> None:
    outcome = flow.outcome
    if outcome is None:  # pragma: no cover — unreachable via the flow
        return

    if flow.succeeded:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
            ui.label(f"{flow.fields.label} is registered.").classes("text-sm").style(
                "color: var(--hw-positive);"
            )
        ui.label(outcome.registry_key or "").classes("text-xs font-mono hw-text-dim")
        with ui.row().classes("w-full justify-end gap-2"):
            ui.button("Close", on_click=lambda: _close(flow)).props("flat dense")
            ui.button("Edit", on_click=_then_close(flow, flow.edit)).props("flat dense")
            ui.button("Place", on_click=_then_close(flow, flow.place)).props("flat dense").style(
                "color: var(--hw-positive);"
            )
        return

    if outcome.status == "timeout":
        _refusal_row("The file was written, but the node did not register in time.")
    else:
        _refusal_row("The file was written, but it failed to import.")
    for error in outcome.errors:
        ui.label(error.message).classes("text-xs hw-text-danger whitespace-pre-line")
    if flow.plan is not None:
        ui.label(str(flow.plan.path)).classes("text-xs font-mono hw-text-dim")
    ui.label("The file stays on disk; fix it and save, and the library registers it.").classes(
        "text-xs hw-text-muted"
    )
    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Close", on_click=lambda: _close(flow)).props("flat dense")
        ui.button("Open file", on_click=_then_close(flow, flow.open_file)).props("flat dense")
