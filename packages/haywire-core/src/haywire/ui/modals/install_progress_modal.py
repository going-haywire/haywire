"""Library operation progress modal — streaming log with spinner, success, and error states.

Opens immediately with a spinner and a live ``ui.log`` feed. The caller drives
state transitions via the returned :class:`LibraryOperationProgressModal` handle:

  modal = library_operation_progress_modal(title="Installing haybale-foo")
  modal.push("Resolving dependencies…")
  modal.finish(hints=PostInstallHints(needs_refresh=True))
  modal.finish(error="Install failed: …", hints=PostInstallHints(needs_restart=True))

The terminal state is driven by ``hints`` (and optionally ``error``):
  * No flags, no error → "Done" button, closes popup.
  * ``needs_refresh=True``, no error → "Reload the page" button that calls
    ``ui.navigate.reload()``.
  * ``needs_restart=True`` → "How to restart Studio" button that reveals a
    manual-restart instructions panel (no auto-quit; restart subsumes refresh).
  * ``error=…`` → red banner stays visible; button label becomes "Close" unless
    ``needs_restart`` is also set, in which case the restart button takes over.

See docs/reference/glossary.md → "Post-install requirements".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from nicegui import ui

from haywire.ui.components.popup import Popup


@dataclass(frozen=True)
class PostInstallHints:
    """Post-install user-action requirements computed by ``LibraryManager``.

    Author-declared on ``LibraryIdentity`` via ``@library(needs_refresh=True,
    needs_restart=True)``. Unioned across newly-imported and evicted libraries
    by the install/uninstall flow and consumed by
    :meth:`LibraryOperationProgressModal.finish` to render the terminal state.

    See docs/reference/glossary.md → "Post-install requirements".
    """

    needs_refresh: bool = False
    needs_restart: bool = False

    def merge(self, other: "PostInstallHints") -> "PostInstallHints":
        """Return a new hints with each flag OR'd between self and other."""
        return PostInstallHints(
            needs_refresh=self.needs_refresh or other.needs_refresh,
            needs_restart=self.needs_restart or other.needs_restart,
        )


_RESTART_INSTRUCTIONS = "Quit Studio in your terminal (Ctrl+C) and run `uv run haywire` again."


class LibraryOperationProgressModal:
    """Handle returned by :func:`library_operation_progress_modal`.

    Use :meth:`push` to stream log lines and :meth:`finish` to transition
    from spinner to the terminal state (success or failure, possibly with
    post-install requirements).
    """

    def __init__(
        self,
        popup: Popup,
        log: "ui.log",
        spinner_row,
        done_row,
        error_banner,
        reload_notice,
        restart_instructions,
    ):
        self._popup = popup
        self._log = log
        self._spinner_row = spinner_row
        self._done_row = done_row  # (row_element, button_element)
        self._error_banner = error_banner  # (text_label, container_row)
        self._reload_notice = reload_notice  # ui.label
        self._restart_instructions = restart_instructions  # ui.label

    def push(self, line: str) -> None:
        """Append a line to the streaming log."""
        self._log.push(line)

    def finish(
        self,
        *,
        error: Optional[str] = None,
        hints: Optional[PostInstallHints] = None,
    ) -> None:
        """Transition to the terminal state.

        Args:
            error: When supplied, shows the error banner. Combines with ``hints``:
                if ``hints.needs_restart`` is True, the restart button still
                appears alongside the error banner (per Q12.A).
                When ``error`` and ``hints.needs_refresh`` are both set without
                ``needs_restart``, the refresh state takes precedence (the user
                still needs to reload to see the partial result, and the banner
                stays visible to explain what failed).
            hints: Post-install requirements that drive button label + extra
                notice / instructions. When None, treated as ``PostInstallHints()``.
        """
        # Idempotency guard — finish() must only transition once. The spinner
        # is hidden as the first side effect below; if it's already hidden, a
        # prior finish() call already wired the terminal button, and a second
        # call would stack click handlers via ``button.on(...)``.
        if not self._spinner_row.visible:
            return

        hints = hints or PostInstallHints()
        self._spinner_row.set_visibility(False)

        if error:
            self._error_banner[0].set_text(error)
            self._error_banner[1].set_visibility(True)

        button = self._done_row[1]

        # Restart subsumes refresh: check restart first.
        if hints.needs_restart:
            button.set_text("How to restart Studio")
            button.on("click", lambda: self._restart_instructions.set_visibility(True))
        elif hints.needs_refresh:
            button.set_text("Reload the page")
            self._reload_notice.set_visibility(True)
            button.on("click", lambda: ui.navigate.reload())
        elif error:
            button.set_text("Close")
            button.on("click", self._popup.close)
        else:
            # Default success state — clicking closes the popup.
            button.on("click", self._popup.close)

        self._done_row[0].set_visibility(True)

    def close(self) -> None:
        """Close the popup programmatically."""
        self._popup.close()


def library_operation_progress_modal(
    *,
    title: str,
    width: str = "520px",
    log_max_lines: int = 200,
) -> LibraryOperationProgressModal:
    """Open a library-operation progress modal and return a handle.

    The modal shows a spinner and a live log feed. Call
    :meth:`~LibraryOperationProgressModal.push` to stream output lines and
    :meth:`~LibraryOperationProgressModal.finish` when the operation completes.

    Args:
        title: Popup title (e.g. "Installing haybale-foo").
        width: CSS width of the popup card.
        log_max_lines: Maximum lines kept in the log widget.

    Returns:
        A :class:`LibraryOperationProgressModal` handle for driving state transitions.
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
            # Spinner row — visible during the operation
            spinner_row = ui.row().classes("items-center gap-2")
            with spinner_row:
                ui.spinner(size="sm")
                ui.label("Working…").classes("text-xs hw-text-dim")

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

            # Refresh-required notice — hidden unless needs_refresh fires
            reload_notice = ui.label("Reload the page to use the new library.").classes(
                "text-xs hw-text-muted"
            )
            reload_notice.set_visibility(False)

            # Restart instructions panel — hidden until the restart button is clicked
            restart_instructions = (
                ui.label(_RESTART_INSTRUCTIONS)
                .classes("text-xs hw-text-muted p-2 rounded")
                .style("background: var(--hw-bg-surface); font-family: monospace;")
            )
            restart_instructions.set_visibility(False)

            # Done/Close/Reload/Restart button row — hidden until finish() is called.
            # No on_click wired here: finish() picks the right handler per terminal
            # state (closes popup, reloads page, or reveals restart instructions).
            done_row = ui.row().classes("w-full justify-end")
            with done_row:
                done_btn = ui.button("Done").props("flat dense")
            done_row.set_visibility(False)

    popup.open()

    return LibraryOperationProgressModal(
        popup=popup,
        log=log,
        spinner_row=spinner_row,
        done_row=(done_row, done_btn),
        error_banner=(error_text, error_container),
        reload_notice=reload_notice,
        restart_instructions=restart_instructions,
    )
