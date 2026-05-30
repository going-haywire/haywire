"""Install progress modal — streaming log with spinner, success, and error states.

Opens immediately with a spinner and a live ``ui.log`` feed. The caller drives
state transitions via the returned :class:`InstallProgressModal` handle:

  modal = install_progress_modal(title="Installing haybale-foo")
  # stream output lines:
  modal.push("Resolving dependencies…")
  # on completion:
  modal.finish()          # success — spinner → "Done" button
  modal.finish(error="Install failed: …")  # failure — error banner + "Close"
"""

from __future__ import annotations

from typing import Optional

from nicegui import ui

from haywire.ui.components.popup import Popup


class InstallProgressModal:
    """Handle returned by :func:`install_progress_modal`.

    Use :meth:`push` to stream log lines and :meth:`finish` to transition
    from spinner to the terminal state (success or failure).
    """

    def __init__(self, popup: Popup, log: "ui.log", spinner_row, done_row, error_banner):
        self._popup = popup
        self._log = log
        self._spinner_row = spinner_row
        self._done_row = done_row
        self._error_banner = error_banner

    def push(self, line: str) -> None:
        """Append a line to the streaming log."""
        self._log.push(line)

    def finish(self, *, error: Optional[str] = None) -> None:
        """Transition to the terminal state.

        Args:
            error: When supplied, shows the error banner and a "Close" button.
                   When omitted (or None), shows a "Done" button (success).
        """
        self._spinner_row.set_visibility(False)
        if error:
            self._error_banner[0].set_text(error)
            self._error_banner[1].set_visibility(True)
            self._done_row[1].set_text("Close")
        self._done_row[0].set_visibility(True)

    def close(self) -> None:
        """Close the popup programmatically."""
        self._popup.close()


def install_progress_modal(
    *,
    title: str,
    width: str = "520px",
    log_max_lines: int = 200,
) -> InstallProgressModal:
    """Open an install progress modal and return an :class:`InstallProgressModal` handle.

    The modal shows a spinner and a live log feed. Call :meth:`~InstallProgressModal.push`
    to stream output lines and :meth:`~InstallProgressModal.finish` when the operation
    completes (success or failure).

    Args:
        title: Popup title (e.g. "Installing haybale-foo").
        width: CSS width of the popup card.
        log_max_lines: Maximum lines kept in the log widget.

    Returns:
        An :class:`InstallProgressModal` handle for driving state transitions.
    """
    popup = Popup(
        title=title,
        width=width,
        closable=False,
        backdrop_click_close=False,
        escape_close=False,
    )

    with popup:
        with ui.column().classes("w-full gap-2 p-1"):
            # Spinner row — visible during install
            spinner_row = ui.row().classes("items-center gap-2")
            with spinner_row:
                ui.spinner(size="sm")
                ui.label("Installing…").classes("text-xs hw-text-dim")

            # Error banner — hidden until finish(error=…) is called
            error_text = ui.label("").classes("text-xs hw-text-danger")
            error_container = (
                ui.row()
                .classes("w-full items-start gap-2 p-2 rounded")
                .style("border-left: 3px solid var(--hw-danger); background: var(--hw-danger-bg);")
            )
            with error_container:
                ui.icon("error", size="16px").classes("hw-text-danger flex-shrink-0 mt-0.5")
                error_text.move(error_container)
            error_container.set_visibility(False)

            # Streaming log
            log = (
                ui.log(max_lines=log_max_lines)
                .classes("w-full text-xs")
                .style("height: 200px; font-family: monospace;")
            )

            # Done/Close button row — hidden until finish() is called
            done_row = ui.row().classes("w-full justify-end")
            with done_row:
                done_btn = ui.button("Done", on_click=popup.close).props("flat dense")
            done_row.set_visibility(False)

    popup.open()

    return InstallProgressModal(
        popup=popup,
        log=log,
        spinner_row=spinner_row,
        done_row=(done_row, done_btn),
        error_banner=(error_text, error_container),
    )
