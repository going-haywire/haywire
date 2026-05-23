"""Install safety modal — spec §7.4 first-install confirmation.

Three-button modal interposing between Install click and actual `uv pip install`.
Cancel / Block / Install. Includes safety copy and a source-URL link button.
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from haywire.ui.components.popup import Popup


_SAFETY_COPY = (
    "You are about to install third-party code. You are responsible for "
    "verifying this library is safe before installing. Review the source "
    "first if you don't recognize the author."
)


def install_safety_modal(
    *,
    haybale_name: str,
    source_url: str,
    on_install: Callable[[], None],
    on_block: Callable[[], None],
    on_cancel: Callable[[], None] | None = None,
) -> Popup:
    """Open the first-install safety modal and return the opened Popup.

    Args:
        haybale_name: The haybale's distribution name (e.g. "haybale-foo").
        source_url: The haybale's source_url field. If empty, the source-link
            button is disabled with explanatory text.
        on_install: Called when the user clicks Install. Popup closes after.
        on_block: Called when the user clicks Block. Popup closes after.
        on_cancel: Called when the user cancels (Cancel button, backdrop click,
            escape). Optional.
    """
    popup = Popup(
        title=f"Install {haybale_name}?",
        width="420px",
        closable=True,
        backdrop_click_close=True,
        escape_close=True,
        backdrop_color="transparent",
    )

    decided = {"value": False}

    if on_cancel is not None:

        def _maybe_cancel() -> None:
            if not decided["value"]:
                on_cancel()

        popup.on_close(_maybe_cancel)

    with popup:
        ui.label(_SAFETY_COPY).classes("text-sm")

        # Source link row.
        with ui.row().classes("w-full items-center mt-3 gap-2"):
            if source_url:
                ui.button(
                    "Review source",
                    icon="open_in_new",
                    on_click=lambda: ui.run_javascript(f"window.open({source_url!r}, '_blank')"),
                ).props("flat dense size=sm")
                ui.label(source_url).classes("text-xs hw-text-dim font-mono truncate")
            else:
                ui.button(
                    "Review source",
                    icon="open_in_new",
                ).props("flat dense size=sm disable").tooltip("No source URL provided")
                ui.label("(no source URL provided)").classes("text-xs hw-text-dim italic")

        # Action buttons.
        def _do_install() -> None:
            decided["value"] = True
            on_install()
            popup.close()

        def _do_block() -> None:
            decided["value"] = True
            on_block()
            popup.close()

        with ui.row().classes("w-full justify-end gap-2 mt-4"):
            ui.button("Cancel", on_click=popup.close).props("flat dense")
            ui.button("Block", on_click=_do_block).props("flat dense").style("color: var(--hw-warning);")
            ui.button("Install", on_click=_do_install).props("flat dense").style(
                "color: var(--hw-positive);"
            )

    popup.open()
    return popup
