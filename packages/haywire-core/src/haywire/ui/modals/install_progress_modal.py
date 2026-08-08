"""Library operation progress modal — streaming log with spinner, success, and error states.

Opens immediately with a spinner and a live ``ui.log`` feed. The caller drives
state transitions via the returned :class:`LibraryOperationProgressModal` handle:

  modal = library_operation_progress_modal(title="Installing haybale-foo")
  modal.push("Resolving dependencies…")
  modal.finish(hints=PostInstallHints(LibraryReloadAction.REFRESH))
  modal.finish(error="Install failed: …", hints=PostInstallHints(LibraryReloadAction.RESTART))

The terminal state is driven by ``hints`` (and optionally ``error``):
  * ``NONE``, no error → "Done" button, closes popup.
  * ``REFRESH``, no error → "Reload the page" button that calls
    ``ui.navigate.reload()``.
  * ``RESTART`` → the shared restart affordance (stale-registry notice +
    "Restart Studio" button that quits gracefully). The quit is never forced —
    the popup's own button still closes it.
  * ``error=…`` → red banner stays visible; button label becomes "Close" unless
    the action is ``RESTART``, in which case the restart button takes over.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from nicegui import ui

from haywire.core.library.identity import LibraryReloadAction
from haywire.ui.components.popup import Popup
from haywire.ui.modals.restart_affordance import restart_affordance


@dataclass(frozen=True)
class PostInstallHints:
    """The post-change user action computed by ``LibraryManager``.

    Author-declared on ``LibraryIdentity`` via ``@library(on_reload="restart")``.
    An install can bring several libraries into the registry at once (the named
    package plus any haybale dependencies it pulls in), so the flow combines
    their declarations with :meth:`merge` before handing the result to
    :meth:`LibraryOperationProgressModal.finish`. Uninstall touches exactly one
    library — ``uv pip uninstall`` never cascades to dependencies — so nothing
    is combined there.
    """

    action: LibraryReloadAction = LibraryReloadAction.NONE

    def merge(self, other: "PostInstallHints") -> "PostInstallHints":
        """Return the more demanding of the two actions.

        ``RESTART`` outranks ``REFRESH`` outranks ``NONE``: if any library in
        one operation needs the heavier action, the user is told to take it.
        """
        return PostInstallHints(max(self.action, other.action))


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
        restart_slot,
    ):
        self._popup = popup
        self._log = log
        self._spinner_row = spinner_row
        self._done_row = done_row  # (row_element, button_element)
        self._error_banner = error_banner  # (text_label, container_row)
        self._reload_notice = reload_notice  # ui.label
        # Empty container reserved at build time; finish() fills it with the
        # restart affordance. Built up-front because by the time finish() runs
        # the popup's slot is no longer the active one.
        self._restart_slot = restart_slot  # ui.column

    def push(self, line: str) -> None:
        """Append a line to the streaming log."""
        self._log.push(line)

    def finish(
        self,
        *,
        error: Optional[str] = None,
        hints: Optional[PostInstallHints] = None,
        restart_reason: Optional[str] = None,
    ) -> None:
        """Transition to the terminal state.

        Args:
            error: When supplied, shows the error banner. Combines with ``hints``:
                if restart is required, the restart affordance still appears
                alongside the error banner (per Q12.A).
                When ``error`` and a ``REFRESH`` action are both present, the
                refresh state takes precedence (the user still needs to reload
                to see the partial result, and the banner stays visible to
                explain what failed).
            hints: The post-change action that drives button label + extra
                notice / instructions. When None, treated as ``PostInstallHints()``.
            restart_reason: Overrides the affordance's leading sentence, so the
                caller can name what actually went stale.
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

        action = hints.action

        if action is LibraryReloadAction.RESTART:
            # The affordance carries its own "Restart Studio" button, so the
            # terminal button stays a plain dismiss — the quit is never the
            # only way out of the popup.
            with self._restart_slot:
                restart_affordance(reason=restart_reason)
            self._restart_slot.set_visibility(True)
            button.set_text("Close")
            button.on("click", self._popup.close)
        elif action is LibraryReloadAction.REFRESH:
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

            # Refresh-required notice — hidden unless the REFRESH action fires
            reload_notice = ui.label("Reload the page to use the new library.").classes(
                "text-xs hw-text-muted"
            )
            reload_notice.set_visibility(False)

            # Reserved slot for the restart affordance. Built empty here because
            # finish() runs outside this slot context; it fills and reveals it.
            restart_slot = ui.column().classes("w-full gap-2")
            restart_slot.set_visibility(False)

            # Done/Close/Reload button row — hidden until finish() is called.
            # No on_click wired here: finish() picks the right handler per terminal
            # state (closes popup or reloads page).
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
        restart_slot=restart_slot,
    )
