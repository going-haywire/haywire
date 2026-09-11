"""SDK-free tool error contract: stable code + actionable message + offending ids."""

from __future__ import annotations

from typing import Optional


class FarmhandError(Exception):
    """An expected tool failure, raised instead of letting an exception escape.

    The host renders it as an MCP tool error, never a stack trace: clients see
    ``[code] message (id=..., ...)``, followed by a ``help: ...`` line when a
    hint is given.

    Args:
        code: Stable machine-readable identifier for this failure.
        ids: The offending ids, shown in parentheses after the message.
        help: One command or concrete next step that resolves the failure, so
            an agent self-corrects in one turn. Pass it whenever the fix is
            knowable where the error is raised.
    """

    def __init__(
        self,
        code: str,
        message: str,
        ids: Optional[dict[str, str]] = None,
        help: Optional[str] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.ids = ids or {}
        self.help = help
