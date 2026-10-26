"""The exception type for an expected, user-correctable rejection."""

from __future__ import annotations


class Refusal(Exception):
    """An expected rejection: correct code can reach it (bad input, a stale id, a name collision).

    A refusal is reported to the caller but is not a failure, so it never reaches
    the error ledger. Any other exception, ``ValueError`` included, is a failure.

    Args:
        message: Text shown to the person or agent whose request was refused.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
