"""
Base exception classes for Haywire with rendering metadata.

These exceptions carry information about how they should be rendered by detailed_error.py,
allowing for better error messages that point to the right location and hide implementation details.
"""

from dataclasses import dataclass, field
from typing import Optional, List

from haywire.core.library.library_identity import LibraryIdentity


@dataclass
class HaywireException(Exception):
    """
    Base exception for Haywire with rendering metadata.
    
    This exception carries information about how detailed_error.py should render it:
    - Where the error actually occurred (user code, not framework internals)
    - What traceback frames to skip
    - Actionable suggestions for fixing the error
    - How to present the error (category, highlights, etc.)
    
    Attributes:
        message: The error message (can be set in subclass __post_init__)
        error_filename: Primary error location - filename where developer should look
        error_line_number: Primary error location - line number
        error_source_line: The actual source line with the error
        skip_frame_functions: Function names to skip in traceback (e.g., ['__init_subclass__'])
        skip_frame_files: Filenames to skip in traceback (e.g., ['decorators.py'])
        skip_backtrace_steps: Number of traceback frames to skip from the start (0 = show all)
        context_range: Number of lines before/after error to show
        show_full_traceback: Whether to show all frames (False hides internal implementation)
        highlight_text: Specific text to highlight in source
        error_category: Category for grouping errors (e.g., "Type Definition Error")
        suggestions: List of actionable suggestions for user
    """
    message: str = ""
    module_name: Optional[str] = None
    library_identity: Optional[LibraryIdentity] = None
    error_filename: Optional[str] = None
    error_line_number: Optional[int] = None
    error_source_line: Optional[str] = None
    skip_frame_functions: List[str] = field(default_factory=list)
    skip_frame_files: List[str] = field(default_factory=list)
    skip_traceback_steps: int = 0
    context_range: int = 2
    show_full_traceback: bool = False
    highlight_text: Optional[str] = None
    error_category: str = "Error"
    suggestions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        # Call Exception.__init__ with the message
        super().__init__(self.message)


