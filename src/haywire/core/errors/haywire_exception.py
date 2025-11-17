from __future__ import annotations
from typing import TYPE_CHECKING


from haywire.core.errors.haywire_error import HaywireError

class HaywireException(Exception):
    """Custom exception with structured error data"""

    def __init__(self, error: 'HaywireError'):
        super().__init__(error.format_detailed())
        self.error: HaywireError = error
        self.original_exception = error.original_exception