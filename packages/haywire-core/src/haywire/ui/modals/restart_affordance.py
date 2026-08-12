"""The shared "your registry is stale, restart Studio" affordance.

Several library operations leave the in-memory registry disagreeing with what
is on disk. Evicting a library from the registry does not evict the module
objects that mounted nodes, registered types, and DI singletons still hold, so
the pre-operation classes and the post-operation classes coexist (the
``assert Foo is Foo`` failure documented in
``.insights/project_slow_test_outliers.md``). Rescanning refreshes the
metadata, not the live objects.

Restarting is the only reliable remedy, so every such path ends by *offering*
one — never forcing it. The button is graceful ``app.shutdown()``, matching
:mod:`haywire.ui.modals.update_dialog`: under ``reload=False`` that takes the
``should_exit`` branch so lifespan handlers run and the Farmhand MCP host stops
cleanly. Nothing relaunches the app, hence the manual command alongside it.

The unsaved-work line is a static warning, deliberately matching the update
dialog rather than querying project state — see the same warning at
``update_dialog._run_conflict_check``.
"""

from __future__ import annotations

from nicegui import app, ui

RESTART_COMMAND = "uv run haywire"
"""The command the user runs to bring Studio back up after the quit."""

_DEFAULT_REASON = "The library registry is now out of sync with what's on disk."

_EXPLAINER = (
    "Studio keeps running, but components loaded before this change may be stale. "
    "Restarting reloads everything cleanly."
)


def restart_affordance(
    *,
    reason: str | None = None,
    compact: bool = False,
) -> ui.button:
    """Render the stale-registry notice and a "Restart Studio" button.

    Renders into the current NiceGUI slot, so call it inside the container that
    should hold it — this is a renderer, not a popup of its own. Callers keep
    their own dismiss/close button; this only adds the restart path.

    Args:
        reason: Overrides the leading sentence explaining what went stale.
            Defaults to a generic registry-staleness message.
        compact: When True, drops the explainer paragraph and renders the
            notice on a single line. For panels that are already text-heavy.

    Returns:
        The "Restart Studio" button, so callers can restyle or further wire it.
    """
    with (
        ui.row()
        .classes("w-full items-start gap-2 p-2 rounded")
        .style("border-left: 3px solid var(--hw-warning); background: var(--hw-bg-surface);")
    ):
        ui.icon("restart_alt", size="16px").classes("flex-shrink-0 mt-0.5").style(
            "color: var(--hw-warning);"
        )
        with ui.column().classes("gap-1 flex-1"):
            ui.label(reason or _DEFAULT_REASON).classes("text-xs").style("color: var(--hw-warning);")
            if not compact:
                ui.label(_EXPLAINER).classes("text-xs hw-text-muted")
            # Same static warning as the update dialog: shutdown does not save.
            ui.label("Unsaved work will be lost.").classes("text-xs").style("color: var(--hw-warning);")
            ui.label(f"Studio does not relaunch itself — run `{RESTART_COMMAND}` afterwards.").classes(
                "text-xs hw-text-dim"
            )

    return (
        ui.button("Restart Studio", on_click=_shutdown)
        .props("flat dense")
        .style("color: var(--hw-warning);")
    )


def _shutdown() -> None:
    """Quit Studio gracefully. Separate function so tests can patch it."""
    app.shutdown()
