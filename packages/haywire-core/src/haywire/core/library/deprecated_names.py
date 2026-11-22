"""Deprecated Author API names: how one is served, and how a library's use of it is recorded.

A name that leaves ``haywire.api`` or ``haywire.api.workbench`` stays importable
for a deprecation window (ADR 0085). The module's ``__getattr__`` serves it
through ``serve_deprecated``, which warns with a ``HaywireDeprecationWarning``.
The library loader imports each library module inside ``recorded_deprecations``,
which writes every notice raised by that import to the error ledger.
"""

from __future__ import annotations

import importlib
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from haywire.core.errors import report_loss


class HaywireDeprecationWarning(DeprecationWarning):
    """A library imported a deprecated Author API name."""


@dataclass(frozen=True)
class DeprecatedName:
    """Where a deprecated Author API name is served from, and what its notice says.

    Attributes:
        target: ``"module.path:attribute"`` of the object the name still resolves to.
        replacement: What to use instead, as the author writes it, e.g.
            ``"haywire.api.NewName"``. Empty when there is none.
        removed_in: The release that removes the name, e.g. ``"0.5.0"``.
    """

    target: str
    replacement: str
    removed_in: str


_notices: ContextVar[list[str] | None] = ContextVar("haywire_deprecation_notices", default=None)


def serve_deprecated(api_module: str, name: str, entry: DeprecatedName) -> Any:
    """Resolve a deprecated name and raise its notice; called from a module ``__getattr__``."""
    message = f"{api_module}.{name} is deprecated and will be removed in {entry.removed_in}."
    if entry.replacement:
        message += f" Use {entry.replacement} instead."
    notices = _notices.get()
    # `from module import name` asks twice (once to check, once to bind).
    if notices is not None and message not in notices:
        notices.append(message)
    warnings.warn(message, HaywireDeprecationWarning, stacklevel=3)
    module_path, _, attribute = entry.target.partition(":")
    return getattr(importlib.import_module(module_path), attribute)


@contextmanager
def recorded_deprecations(module_name: str, **context: Any) -> Iterator[None]:
    """Write each deprecation notice raised inside the block to the error ledger.

    Wrap the import of a library module. The entry is a ``WARNING`` naming the
    module; ``context`` takes what ``report_loss`` takes (``library_identity``).
    The notices are written even when the import raises. Never raises itself.
    """
    notices: list[str] = []
    token = _notices.set(notices)
    try:
        yield
    finally:
        _notices.reset(token)
        for message in notices:
            report_loss(message, operation="Load library", module_name=module_name, **context)
