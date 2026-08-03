"""Per-step body content for the Add Source flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.stepper import advance, busy_advance

from ._state import KEEP_EXISTING, USE_NEW, AddSourceFlow


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _panel_input(flow: AddSourceFlow, rerender: Callable[[], None]) -> None:
    """Paste a URL or a TOML block. Nothing is fetched yet."""
    ui.label("Add a marketplace source").classes("text-sm font-medium")
    ui.label(
        "Paste a marketstall URL, a marketplace URL, or a [[haybales]] TOML block. "
        "Nothing is subscribed until you have seen what it offers."
    ).classes("text-xs hw-text-dim")

    # ui.textarea (not hui.input_field) so a multi-line TOML paste preserves
    # newlines — a single-line input collapses them into spaces and produces
    # invalid TOML.
    field = (
        ui.textarea(placeholder="https://github.com/.../blob/main/marketstall.toml")
        .props("dense autogrow")
        .classes("w-full text-xs")
    )
    field.value = flow.user_input

    with ui.column().classes("gap-0 text-xs hw-text-dim"):
        ui.label("Accepted forms:")
        ui.label("• Blob URL (github.com/.../blob/{ref}/marketstall.toml)")
        ui.label("• Raw URL (raw.githubusercontent.com/...)")
        ui.label("• Any URL that serves a TOML file (GitHub Pages, GitLab Pages, etc.)")
        ui.label("• A [[haybales]] TOML block pasted directly")

    with ui.row().classes("w-full justify-end gap-2"):
        probe = ui.button("Probe").props("flat dense").style("color: var(--hw-positive);")
        probe.on_click(lambda: busy_advance(rerender, probe, lambda: flow.advance_from_input(field.value)))


def _panel_probed(flow: AddSourceFlow, rerender: Callable[[], None]) -> None:
    """What the source turned out to be. Still nothing written."""
    resolved = flow.resolved
    if resolved is None:  # pragma: no cover — unreachable via the flow
        return

    kind_label = "marketplace" if resolved.kind == "market" else "marketstall"
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label(f"A {kind_label} offering {_plural(len(flow.new_names), 'library')}.").classes(
            "text-sm"
        ).style("color: var(--hw-positive);")

    if resolved.is_paste:
        ui.label("Pasted block — it will be saved alongside your other sources when you subscribe.").classes(
            "text-xs hw-text-dim"
        )
    elif resolved.persist_url:
        ui.label(resolved.persist_url).classes("text-xs font-mono hw-text-dim")

    if flow.new_names:
        with ui.column().classes("gap-0.5 ml-1"):
            for name in flow.new_names[:12]:
                ui.label(name).classes("text-xs font-mono hw-text-dim")
            if len(flow.new_names) > 12:
                ui.label(f"…and {len(flow.new_names) - 12} more").classes("text-xs hw-text-muted")

    if resolved.kind == "market":
        ui.label(
            "Marketplaces are read one level deep, so this may pull in further "
            "marketstalls when you refresh."
        ).classes("text-xs hw-text-muted")

    if flow.conflicts:
        ui.label(
            f"{_plural(len(flow.conflicts), 'name')} already provided by another source — "
            "you will choose which to keep next."
        ).classes("text-xs").style("color: var(--hw-warning);")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Continue",
            on_click=lambda: advance(rerender, flow.advance_from_probed),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_resolved(flow: AddSourceFlow, rerender: Callable[[], None]) -> None:
    """One row per collision. Rendered even when clean, so the bar has no dead step."""
    if not flow.conflicts:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
            ui.label("No conflicts — nothing this source offers is already provided.").classes(
                "text-sm"
            ).style("color: var(--hw-positive);")
    else:
        ui.label("These names are offered by more than one source. Pick which to keep:").classes(
            "text-xs hw-text-dim"
        )
        for conflict in flow.conflicts:
            with ui.column().classes("border rounded p-2 gap-1 w-full"):
                ui.label(conflict.name).classes("text-xs font-medium")
                radio = ui.radio(
                    ["Keep existing", "Use new"],
                    value="Keep existing" if flow.choices.get(conflict.name) == KEEP_EXISTING else "Use new",
                ).props("inline dense")

                def _on_choice(_e, name=conflict.name, el=radio) -> None:
                    flow.choose(name, KEEP_EXISTING if "existing" in el.value.lower() else USE_NEW)

                radio.on("update:model-value", _on_choice)

                with ui.column().classes("gap-0 ml-2"):
                    ui.label(f"existing: {conflict.existing_source}").classes(
                        "text-xs hw-text-dim font-mono"
                    )
                    ui.label(f"new: {conflict.new_source}").classes("text-xs hw-text-dim font-mono")

        ui.label(
            "The source that loses a name is told to ignore it, so the choice survives future refreshes."
        ).classes("text-xs hw-text-muted")

    ui.label("Subscribing writes this source to your marketplace file.").classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        subscribe = ui.button("Subscribe").props("flat dense").style("color: var(--hw-positive);")
        subscribe.on_click(lambda: busy_advance(rerender, subscribe, flow.advance_from_resolved))


def _panel_added(flow: AddSourceFlow, rerender: Callable[[], None]) -> None:
    """Subscribed. Refreshing is the next step, but closing here is legitimate."""
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        ui.label("Subscribed.").classes("text-sm").style("color: var(--hw-positive);")

    if flow.persist_url:
        ui.label(flow.persist_url).classes("text-xs font-mono hw-text-dim")

    ui.label(
        "Its libraries reach the list on the next refresh. You can run that now, or later from the toolbar."
    ).classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=lambda: _close(flow)).props("flat dense")
        refresh = ui.button("Refresh now").props("flat dense").style("color: var(--hw-positive);")
        refresh.on_click(lambda: busy_advance(rerender, refresh, flow.advance_from_added))


def _panel_refreshed(flow: AddSourceFlow, on_done: Callable[[], None] | None) -> None:
    report = flow.report
    with ui.row().classes("w-full items-center gap-2"):
        ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
        if report is not None:
            ui.label(f"{_plural(report.haybales_resolved, 'library')} available.").classes("text-sm").style(
                "color: var(--hw-positive);"
            )
        else:  # pragma: no cover — refresh always sets a report on success
            ui.label("Refreshed.").classes("text-sm").style("color: var(--hw-positive);")

    if report is not None and report.unavailable_urls:
        ui.label(f"{_plural(len(report.unavailable_urls), 'source')} could not be reached.").classes(
            "text-xs hw-text-muted"
        )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=lambda: _close(flow)).props("flat dense").style(
            "color: var(--hw-positive);"
        )


def _close(flow: AddSourceFlow) -> None:
    if flow.popup is not None:
        flow.popup.close()


__all__ = [
    "_panel_added",
    "_panel_input",
    "_panel_probed",
    "_panel_refreshed",
    "_panel_resolved",
]
