"""Error handling for Haywire.

Use ``HaywireException.from_exception()`` or ``HaywireException.create()``.
At an ``except`` site, call ``report_failure``; raise ``Refusal`` for expected rejections.
"""

from .boundary import report_failure, report_loss
from .haywire_exception import HaywireException, ErrorSeverity
from .refusal import Refusal

__all__ = [
    "HaywireException",
    "ErrorSeverity",
    "Refusal",
    "report_failure",
    "report_loss",
]
