"""Runnable panel harness for the Share flow.

    uv run python -m haybale_share._flow

Opens http://localhost:8091 with every screen in every state, side by side
with the scenario list. Nothing writes: each scenario hand-builds flow state
and calls the panel directly, never a pipeline step. See ``_harness.py`` for
why fixtures beat driving a real ``SharePipeline`` here.

Boots a real library system so the themes and ``hui`` elements resolve — the
point is to look at the panels as they will actually appear, not at unstyled
approximations. Mirrors ``tests/ui/harness/app.py``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from typing import Callable

from nicegui import app, ui

from haywire.core.di.config import (
    create_library_system_service,
    set_global_injector,
    set_library_system,
)
from haywire.core.di.context import set_workspace_root

from ._harness import Panel
from ._state import ShareFlow

_HERE = Path(__file__).resolve()
# _flow/ → haybale_share/ → haybale-share/ → barn/ → repo root
_REPO_ROOT = _HERE.parent.parent.parent.parent
_BARN = str(_REPO_ROOT / "barn")


def _render_scenario(container: ui.element, label: str, build, panel) -> None:
    """Render one scenario into *container*, inside the flow's real chrome.

    The progress bar, warning rows and error banner come from
    ``haywire.ui.components.stepper``, exactly as ``show_step_flow`` composes
    them — a panel judged without its chrome is judged in the wrong context.
    """
    from haywire.ui.components.stepper import render_error, render_progress, render_warnings

    from .panels import suppress_duplicate_error

    container.clear()
    flow = build()

    def _rerender() -> None:
        _render_scenario(container, label, build, panel)

    with container:
        ui.label(label).classes("text-sm font-medium")
        ui.label(f"step = {flow.step!r}").classes("text-xs font-mono hw-text-muted")

        # 640px: the width show_share_flow() opens the real popup at.
        with (
            ui.column()
            .classes("gap-2 p-3 rounded")
            .style("width: 640px; border: 1px solid var(--hw-border); background: var(--hw-bg-elevated);")
        ):
            render_progress(flow)
            render_warnings(flow)
            # The same error_detail show_share_flow passes. Rendering the banner
            # without it is how this harness first showed a duplicate the real
            # flow does not have — a harness that diverges from production
            # reports bugs that are its own.
            render_error(flow, _rerender, suppress_duplicate_error)
            panel(flow, _rerender)


def _inject_theme() -> None:
    """Put the workbench theme's --hw-* variables on :root.

    Without this every token resolves to empty and the panels render with
    browser defaults — borders vanish, `hw-text-dim` is plain black. The app
    shell normally does this (`shell.py`'s `_theme_css`), but the harness has
    no shell, so it did what a harness must never do: showed the panels
    looking materially different from production, and specifically hid the
    boundaries this screen relies on.
    """
    from haywire.core.di.config import get_library_system

    try:
        registry = get_library_system().get_theme_registry()
        keys = list(registry.list_workbench_keys())
        if not keys:
            return
        theme = registry.get_workbench(keys[0])
        css = " ".join(f"{k}: {v};" for k, v in theme.to_css_vars().items())
        # The page background too: the workbench themes are dark, and a dark
        # panel floating on a white page misrepresents every contrast
        # judgement this harness exists to support.
        body_css = "body { background: var(--hw-bg-page); color: var(--hw-text-body); }"
        ui.add_head_html(f"<style>:root {{ {css} }} {body_css}</style>")
    except Exception as exc:  # noqa: BLE001 — a themeless harness still renders
        print(f"harness: could not inject a workbench theme ({exc})")


def _page() -> None:
    from ._harness import SCENARIOS

    _inject_theme()
    ui.query("body").classes("hw-app")

    with ui.row().classes("w-full h-screen gap-0 items-stretch"):
        with (
            ui.column()
            .classes("gap-1 p-3 h-full overflow-auto")
            .style("width: 300px; border-right: 1px solid var(--hw-border);")
        ):
            ui.label("Share flow — panels").classes("text-sm font-medium")
            ui.label("Fixture state. Nothing writes.").classes("text-xs hw-text-muted")
            buttons: list[tuple[ui.button, str, Callable[[], ShareFlow], Panel]] = []

            with ui.scroll_area().classes("flex-1 w-full"):
                for group, entries in SCENARIOS.items():
                    ui.label(group).classes("text-xs hw-text-dim mt-2")
                    for label, build, panel in entries:
                        button = (
                            ui.button(label).props("flat dense align=left no-caps").classes("w-full text-xs")
                        )
                        buttons.append((button, label, build, panel))

        with ui.scroll_area().classes("flex-1 h-full"):
            stage = ui.column().classes("p-4 gap-2")

    for button, label, build, panel in buttons:
        button.on_click(lambda _e=None, la=label, b=build, p=panel: _render_scenario(stage, la, b, p))

    first_label, first_build, first_panel = next(iter(SCENARIOS.values()))[0]
    _render_scenario(stage, first_label, first_build, first_panel)


def main() -> None:
    library_paths = [_BARN] if os.path.isdir(_BARN) else []
    service = create_library_system_service(
        workspace_root=str(_REPO_ROOT),
        library_paths=library_paths,
        enable_file_watching=False,
        watch_settings=False,
    )
    set_library_system(service)
    set_global_injector(service.injector)
    set_workspace_root(str(_REPO_ROOT))

    ui.page("/")(_page)
    app.on_shutdown(lambda: service.cleanup() if hasattr(service, "cleanup") else None)

    ui.run(port=8091, show=False, title="Share flow — panel harness", reload=False)


if __name__ in {"__main__", "__mp_main__"}:
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    main()
