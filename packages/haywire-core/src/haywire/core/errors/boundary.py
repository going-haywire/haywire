"""Error-boundary helpers: record failures and detected losses in the error ledger."""

from __future__ import annotations

import logging
from typing import Any

from haywire.core.errors.haywire_exception import ErrorSeverity, HaywireException
from haywire.core.errors.refusal import Refusal

logger = logging.getLogger(__name__)

_ENRICH_FIELDS = ("graph_id", "node_id", "edge_id", "registry_key", "library_identity")


def _split_context(context: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split boundary context into ``enrich`` keywords and extra ``error_context`` entries."""
    known = {k: v for k, v in context.items() if k in _ENRICH_FIELDS and v is not None}
    extra = {k: v for k, v in context.items() if k not in _ENRICH_FIELDS}
    return known, extra


def report_failure(
    exc: BaseException,
    *,
    operation: str,
    message: str | None = None,
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    refusals_fail: bool = False,
    **context: Any,
) -> HaywireException | None:
    """Record a caught exception in the error ledger; call it from an ``except`` block.

    A ``Refusal`` is not recorded and yields ``None``, unless ``refusals_fail`` is
    set, in which case it is recorded like any other exception. A
    ``HaywireException`` is reused and keeps the context it already holds; only its
    empty fields are filled. Any other exception is wrapped. Recording the same
    exception twice adds no second entry. Never raises.

    Args:
        exc: The caught exception.
        operation: What was being attempted, e.g. ``"Apply edit"``.
        message: Entry message for a wrapped exception; defaults to ``"<operation> failed"``.
        severity: Severity of a wrapped exception.
        refusals_fail: Record a ``Refusal`` instead of letting it through.
        **context: ``graph_id``, ``node_id``, ``edge_id``, ``registry_key`` and
            ``library_identity`` set the matching fields; any other key goes into
            ``error_context``.

    Returns:
        The logged ``HaywireException``, or ``None`` for a refusal or if recording failed.
    """
    try:
        if isinstance(exc, Refusal) and not refusals_fail:
            return None
        known, extra = _split_context(context)
        if isinstance(exc, HaywireException):
            logged = exc
            fill = {k: v for k, v in known.items() if not getattr(logged, k, None)}
            logged.enrich(**fill)
            if not logged.operation:
                logged.operation = operation
            for key, value in extra.items():
                logged.error_context.setdefault(key, value)
        else:
            assert isinstance(exc, Exception)
            logged = HaywireException.from_exception(
                exc, message or f"{operation} failed", operation=operation, severity=severity
            )
            logged.enrich(**known)
            logged.error_context.update(extra)
        return logged.log()
    except Exception:
        logger.debug("report_failure failed for %r", exc, exc_info=True)
        return None


def report_loss(message: str, *, operation: str, **context: Any) -> HaywireException:
    """Record a detected loss (something silently dropped) as a ``WARNING`` in the error ledger.

    Args:
        message: What was lost.
        operation: What was being attempted.
        **context: As for ``report_failure``.

    Returns:
        The logged ``HaywireException``.
    """
    known, extra = _split_context(context)
    loss = HaywireException.create(message, severity=ErrorSeverity.WARNING, operation=operation)
    loss.enrich(**known)
    loss.error_context.update(extra)
    return loss.log()
