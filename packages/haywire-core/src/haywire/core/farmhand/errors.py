"""SDK-free tool error contract: stable code + actionable message + offending ids."""

from __future__ import annotations

from typing import Optional


class FarmhandError(Exception):
    """Expected tool failure. The host renders it as an MCP tool error;
    clients see '[code] message (id=..., ...)' — never a stack trace."""

    def __init__(self, code: str, message: str, ids: Optional[dict[str, str]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.ids = ids or {}
