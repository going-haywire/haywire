"""The ``haywire`` command line — one module per subcommand.

Each subcommand module exposes a single ``register(subparsers)`` function
that adds its parser, its flags, and — via ``set_defaults(handler=...)`` —
the function to run. :func:`haywire_studio.app.main` iterates
:data:`SUBCOMMANDS` and dispatches through whatever handler argparse leaves
on the parsed namespace, so adding another subcommand means adding one
module and one entry here; ``app.py`` is never touched again.

Handlers return a process exit code and take the parsed ``Namespace``. They
never call :func:`sys.exit` themselves, which keeps them callable from
tests without catching ``SystemExit``.

The split from :mod:`haywire_studio.packaging` is by *role*: argument
parsing, prompting and exit codes live here; the domain logic they drive
lives there.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Protocol

from haywire_studio.cli import (
    authcmd,
    deps,
    docs,
    init,
    rename,
    securitycmd,
    share,
    sslcmd,
    user,
    verify,
)


class _SubcommandModule(Protocol):
    """The shape every module in this package satisfies."""

    def register(self, subparsers: argparse._SubParsersAction) -> None: ...


SUBCOMMANDS: Sequence[_SubcommandModule] = (
    init,
    share,
    rename,
    deps,
    docs,
    verify,
    user,
    authcmd,
    sslcmd,
    securitycmd,
)

__all__ = ["SUBCOMMANDS"]
