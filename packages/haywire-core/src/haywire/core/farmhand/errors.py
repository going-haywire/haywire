"""SDK-free tool error contract: stable code + actionable message + offending ids."""

from __future__ import annotations

from typing import Optional


class FarmhandError(Exception):
    """Expected tool failure. The host renders it as an MCP tool error;
    clients see '[code] message (id=..., ...)' followed by a 'help: ...' line
    when a recovery hint is known — never a stack trace.

    `help` is the single command (or concrete next step) that resolves this
    failure, e.g. "Run haystack_list_graphs to see open graphs." Supply it
    whenever the fix is knowable at the throw site: an agent that gets a hint
    self-corrects in one turn instead of guessing at the tool surface.
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
