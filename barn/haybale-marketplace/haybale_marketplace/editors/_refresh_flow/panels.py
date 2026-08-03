"""Per-step body content for the Refresh Libraries flow."""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.core.marketstall import RefreshOutcome
from haywire.ui import elements as hui
from haywire.ui.components.stepper import advance, busy_advance

from ._state import RefreshFlow


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _panel_sources(flow: RefreshFlow, rerender: Callable[[], None]) -> None:
    """What will be contacted. Read-only: nothing has been fetched yet."""
    global_file = flow.state.get_global()

    if global_file is None:
        ui.label(
            "The global marketplace file could not be read. Repair it with Edit File, "
            "then start the refresh again."
        ).classes("text-xs hw-text-danger")
        return

    markets = len(global_file.markets)
    stalls = len(global_file.stalls)
    inline = len(global_file.haybales)

    if not (markets or stalls or inline):
        ui.label(
            "No sources subscribed. Add a marketplace or marketstall URL first — "
            "a refresh would have nothing to contact."
        ).classes("text-xs hw-text-dim")
        return

    ui.label("These sources will be contacted:").classes("text-xs hw-text-dim")
    with ui.column().classes("gap-0.5 ml-1"):
        for sub in global_file.markets:
            ui.label(f"market · {sub.url}").classes("text-xs font-mono hw-text-dim")
        for sub in global_file.stalls:
            ui.label(f"stall · {sub.url}").classes("text-xs font-mono hw-text-dim")
        if inline:
            ui.label(f"{_plural(inline, 'library')} listed directly in the global file").classes(
                "text-xs hw-text-dim"
            )

    ui.label(
        "Markets are read one level deep, so they may add stalls beyond the ones listed here. "
        "Fetching only reads — nothing is written until you apply."
    ).classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        fetch = ui.button("Fetch").props("flat dense").style("color: var(--hw-positive);")
        fetch.on_click(lambda: busy_advance(rerender, fetch, flow.advance_from_sources))


def _panel_fetched(flow: RefreshFlow, rerender: Callable[[], None]) -> None:
    """Per-source outcome. Still nothing written."""
    fetched = flow.fetched
    if fetched is None:  # pragma: no cover — unreachable via the flow
        return

    cached = fetched.sources_from_cache
    unavailable = fetched.unavailable_urls

    with ui.row().classes("w-full items-center gap-2"):
        icon = "check_circle" if not unavailable else "warning"
        colour = "var(--hw-positive)" if not unavailable else "var(--hw-warning)"
        ui.icon(icon, size="16px").style(f"color: {colour};")
        ui.label(f"{_plural(len(fetched.outcomes), 'source')} contacted.").classes("text-sm").style(
            f"color: {colour};"
        )

    with ui.column().classes("gap-0.5 ml-1"):
        for outcome in fetched.outcomes:
            if outcome.outcome is RefreshOutcome.FRESH:
                mark, tone = "✓", "hw-text-dim"
            elif outcome.outcome is RefreshOutcome.CACHE_FALLBACK:
                mark, tone = "~", "hw-text-muted"
            else:
                mark, tone = "✕", "hw-text-danger"
            suffix = " (discovered)" if outcome.discovered else ""
            ui.label(f"{mark} {outcome.url}{suffix}").classes(f"text-xs font-mono {tone}")

    if cached:
        ui.label(
            f"{_plural(cached, 'source')} could not be reached and was served from the local cache, "
            "so their entries may be out of date."
        ).classes("text-xs hw-text-muted")
    if unavailable:
        ui.label(
            f"{_plural(len(unavailable), 'source')} unreachable with no cached copy — "
            "libraries offered only by those will be marked stale."
        ).classes("text-xs hw-text-muted")

    ui.label("Next: work out what this would change in the library list. Still no writes.").classes(
        "text-xs hw-text-dim"
    )

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button(
            "Resolve",
            on_click=lambda: advance(rerender, flow.advance_from_fetched),
        ).props("flat dense").style("color: var(--hw-positive);")


def _panel_resolved(flow: RefreshFlow, rerender: Callable[[], None]) -> None:
    """The deltas a write would produce — the informed-decision point."""
    resolved = flow.resolved
    if resolved is None:  # pragma: no cover — unreachable via the flow
        return

    unchanged = not (resolved.newly_added or resolved.newly_stale)
    if unchanged:
        ui.label(
            f"Nothing changes — {_plural(resolved.resolved_count, 'library')} available, same as now."
        ).classes("text-xs hw-text-dim")
    else:
        ui.label("Applying this refresh will:").classes("text-xs hw-text-dim")

    with ui.column().classes("gap-0.5 ml-1"):
        for name in resolved.newly_added:
            ui.label(f"+ {name}").classes("text-xs font-mono").style("color: var(--hw-positive);")
        for name in resolved.newly_stale:
            ui.label(f"~ {name} — no longer offered, kept as stale").classes("text-xs font-mono").style(
                "color: var(--hw-warning);"
            )

    if resolved.updates_available:
        hui.section_label("Updates")
        ui.label(
            f"{_plural(resolved.updates_available, 'installed library')} "
            f"{'has' if resolved.updates_available == 1 else 'have'} a newer version available."
        ).classes("text-xs hw-text-dim")

    ui.label(
        "Applying overwrites the project's cached library list. Nothing is installed or removed."
    ).classes("text-xs hw-text-dim")

    with ui.row().classes("w-full justify-end gap-2"):
        apply_button = ui.button("Apply").props("flat dense").style("color: var(--hw-positive);")
        apply_button.on_click(lambda: busy_advance(rerender, apply_button, flow.advance_from_resolved))


def _panel_applied(flow: RefreshFlow, on_done: Callable[[], None] | None) -> None:
    report = flow.report
    if report is not None:
        with ui.row().classes("w-full items-center gap-2"):
            ui.icon("check_circle", size="16px").style("color: var(--hw-positive);")
            ui.label(f"{_plural(report.haybales_resolved, 'library')} available.").classes("text-sm").style(
                "color: var(--hw-positive);"
            )

        if report.updates_available:
            ui.label(f"{_plural(report.updates_available, 'update')} available.").classes(
                "text-xs hw-text-dim"
            )

    def _close() -> None:
        if flow.popup is not None:
            flow.popup.close()

    with ui.row().classes("w-full justify-end gap-2"):
        ui.button("Done", on_click=_close).props("flat dense").style("color: var(--hw-positive);")
