"""The one exception this feature raises.

Alone in its own module so that :mod:`roster` (the model) and :mod:`document`
(the I/O and rules) can both raise it without importing each other.
"""

from __future__ import annotations


class SecurityError(Exception):
    """The security document rejected a read or a write.

    Covers three cases that all mean "do not proceed on a guess": the file
    cannot be parsed, its version is not understood, or a requested change
    would violate an invariant. Never degraded into a default document —
    a default document means "authentication is off", and turning a disk
    problem into an open door is the one direction of error this feature
    must not make.
    """
