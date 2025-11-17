from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.errors.detailed_error import ErrorContext

class HaywireException(Exception):
    """Custom exception with structured error data"""

    def __init__(self, context: 'ErrorContext', original_exception: Exception):
        super().__init__(context.message)
        self.context = context
        self.original_exception = original_exception