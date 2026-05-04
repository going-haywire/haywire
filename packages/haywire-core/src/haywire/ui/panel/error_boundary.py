"""Error boundary helper for panel hosts.

Hosts call `safe_call_panel_method` to invoke a panel's poll() or draw().
Any exception is caught, wrapped as HaywireException, and returned as
(None, exception). The host then renders an error widget inline rather
than crashing.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from haywire.core.errors.haywire_exception import HaywireException

logger = logging.getLogger(__name__)


def safe_call_panel_method(
    fn: Callable[[], Any],
    *,
    panel_name: str,
    method_name: str,
) -> tuple[Any, HaywireException | None]:
    """Call fn(), returning (result, None) on success or (None, exception) on failure.

    HaywireException instances are passed through unchanged. Other
    exceptions are wrapped with context about the panel and method.
    The error is also logged.
    """
    try:
        return fn(), None
    except HaywireException as exc:
        logger.warning("Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True)
        return None, exc
    except Exception as exc:
        wrapped = HaywireException(
            f"Panel {panel_name}.{method_name} raised {type(exc).__name__}: {exc}",
        )
        wrapped.__cause__ = exc
        logger.warning("Panel error in %s.%s: %s", panel_name, method_name, exc, exc_info=True)
        return None, wrapped
