"""The studio's error safety net: UI handler failures and last-resort process hooks."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from types import TracebackType
from typing import Any, Callable, Optional

from nicegui import app, context, ui

from haywire.core.errors import Refusal, report_failure
from haywire.core.session.session import Session

logger = logging.getLogger(__name__)

FAILURE_TOAST = "Something went wrong — see Errors"


class ErrorHooks:
    """Record failures that escape NiceGUI handlers, threads and the event loop.

    ``on_ui_exception`` records the failure with the session's principal and toasts the
    clicking user; a leaked ``Refusal`` is toasted with its own message and not recorded.
    ``install`` also chains ``threading.excepthook``, ``sys.excepthook`` and, when called
    inside a running loop, the asyncio exception handler; each previous hook is still
    called. ``uninstall`` restores what ``install`` replaced.

    Args:
        session_of: Maps a NiceGUI ``client.id`` to its session, or ``None`` if unknown.
    """

    def __init__(self, session_of: Callable[[str], Optional[Session]]) -> None:
        self._session_of = session_of
        self._installed = False
        self._prev_thread_hook: Any = None
        self._prev_sys_hook: Any = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._prev_loop_handler: Any = None

    def on_ui_exception(self, exc: Exception) -> None:
        """Record a failure escaping a NiceGUI handler and toast the user who triggered it."""
        client = self._current_client()
        if isinstance(exc, Refusal):
            self._toast(client, str(exc), type="warning", multi_line=True)
            return
        context_fields: dict[str, Any] = {}
        session = self._session_for(client)
        if session is not None:
            context_fields = {"principal": session.context.principal, "session_id": session.session_id}
        report_failure(exc, operation="UI handler", **context_fields)
        self._toast(client, FAILURE_TOAST, type="negative")

    def install(self) -> None:
        """Register the UI handler and chain the process-wide hooks; idempotent."""
        if self._installed:
            return
        self._installed = True
        app.on_exception(self.on_ui_exception)
        self._prev_thread_hook = threading.excepthook
        threading.excepthook = self._on_thread_exception
        self._prev_sys_hook = sys.excepthook
        sys.excepthook = self._on_uncaught
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        if self._loop is not None:
            self._prev_loop_handler = self._loop.get_exception_handler()
            self._loop.set_exception_handler(self.on_loop_exception)

    def uninstall(self) -> None:
        """Restore the hooks ``install`` replaced; hooks someone else replaced since stay."""
        if not self._installed:
            return
        self._installed = False
        try:
            app._exception_handlers.remove(self.on_ui_exception)
        except ValueError:
            pass
        if threading.excepthook == self._on_thread_exception:
            threading.excepthook = self._prev_thread_hook
        if sys.excepthook == self._on_uncaught:
            sys.excepthook = self._prev_sys_hook
        if self._loop is not None and self._loop.get_exception_handler() == self.on_loop_exception:
            self._loop.set_exception_handler(self._prev_loop_handler)
        self._loop = None

    def on_loop_exception(self, loop: asyncio.AbstractEventLoop, ctx: dict[str, Any]) -> None:
        """Record an asyncio loop failure, then hand the context to the previous handler."""
        exc = ctx.get("exception")
        if isinstance(exc, Exception):
            report_failure(exc, operation="Asyncio", message=str(ctx.get("message") or "Asyncio failure"))
        if self._prev_loop_handler is not None:
            self._prev_loop_handler(loop, ctx)
        else:
            loop.default_exception_handler(ctx)

    def _on_thread_exception(self, args: Any) -> None:
        if isinstance(args.exc_value, Exception):
            report_failure(args.exc_value, operation="Thread")
        self._prev_thread_hook(args)

    def _on_uncaught(
        self, exc_type: type[BaseException], exc: BaseException, tb: Optional[TracebackType]
    ) -> None:
        if isinstance(exc, Exception):
            report_failure(exc, operation="Uncaught")
        self._prev_sys_hook(exc_type, exc, tb)

    @staticmethod
    def _current_client() -> Any:
        try:
            return context.client if context.slot_stack else None
        except Exception:
            return None

    def _session_for(self, client: Any) -> Optional[Session]:
        if client is None:
            return None
        try:
            return self._session_of(client.id)
        except Exception:
            logger.debug("session lookup failed", exc_info=True)
            return None

    @staticmethod
    def _toast(client: Any, text: str, **kwargs: Any) -> None:
        """Toast under ``client``; the client may be gone, so a failure here is swallowed."""
        if client is None:
            return
        try:
            with client:
                ui.notify(text, **kwargs)
        except Exception:
            logger.debug("error toast failed", exc_info=True)
