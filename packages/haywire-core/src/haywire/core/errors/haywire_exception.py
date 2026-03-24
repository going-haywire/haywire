"""
Unified HaywireException - UI-first exception for user-facing errors

HaywireException (User-facing)

    Audience: End users of the Haywire visual editor
    Purpose: Runtime failures during graph execution/hot-reload
    Display: UI widgets, event panels, notification system
    Example: Node failed to load, widget crash, renderer error

This exception is designed for runtime failures that end users need to understand.
It's primarily a UI event that can also be raised/caught like a normal exception.

Design Philosophy:
- Stores ALL data needed for rich UI rendering (ErrorWidget, event log panel)
- Can be stored in state (LifeCycleEvent, NodeWrapper, BaseWidget)
- Can be raised/caught like normal exception
- Provides query methods for filtering in UI
- Console logging is fallback - primary display is UI

Usage:
    # Pattern 1: Create from exception and store (most common)
    error = HaywireException.from_exception(
        exc,
        message="Failed to load node",
        operation="hot_reload"
    ).enrich(registry_key="mylib:MyNode")

    lifecycle_event.error = error

    # Pattern 2: Create and raise (immediate failure)
    raise HaywireException.create(
        "Critical failure",
        severity=ErrorSeverity.CRITICAL
    )

    # Pattern 3: Query for UI
    if error.should_notify_user():
        show_notification(error.get_summary())

    # Pattern 4: Extract technical details separately
    extracted = HaywireException.extract(exc)
    error = HaywireException.create(
        "Custom message",
        **extracted
    )

    # Pattern 5: Enrich with exception after creation
    error = HaywireException.create("Base error")
    error.enrich(exception=exc, registry_key="lib:Node")
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
import sys
import traceback as tb_module
import re
import time
import os

from ..library.identity import LibraryIdentity


class ErrorSeverity(Enum):
    """Severity levels for UI display and filtering"""

    INFO = "info"  # Informational (blue) - "Node reloaded"
    WARNING = "warning"  # Warning (yellow) - "Using fallback widget"
    ERROR = "error"  # Error (orange) - "Failed to render"
    CRITICAL = "critical"  # Critical (red) - "System component failed"


# ============================================================================
# UTILITY FUNCTIONS FOR SMART FRAME DETECTION
# ============================================================================


def is_framework_code(filepath: str, framework_paths: Optional[List[str]] = None) -> bool:
    """
    Check if a file is part of the framework (not user code).

    Args:
        filepath: Path to the file
        framework_paths: List of framework package paths to exclude
                        (defaults to haywire core packages)

    Returns:
        True if this is framework code, False if user code
    """
    if framework_paths is None:
        # Default framework paths to exclude
        framework_paths = [
            "/src/haywire/core",  # All Haywire core code
            "/src/haywire/ui",  # All Haywire UI code
            "site-packages",  # Python packages
            "<frozen",  # Python internals
            "<string>",  # Dynamically generated code (dataclasses, etc.)
            "/lib/python",  # Python standard library
            "/Library/Frameworks/Python.framework",  # macOS Python framework
            "\\lib\\python",  # Windows Python stdlib
        ]

    # Normalize path
    filepath = os.path.normpath(filepath)

    # Check if it's in any framework path
    for framework_path in framework_paths:
        if framework_path in filepath:
            return True

    return False


def _find_decorator_frame(
    traceback_frames: List[Dict[str, Any]], framework_paths: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Find a frame that contains a decorator application.

    Returns the last (deepest) frame with a decorator, prioritizing user code.
    """
    decorator_frames = []

    for frame in traceback_frames:
        code = frame.get("code", "").strip()
        filepath = frame.get("file", "")

        # Look for decorator syntax
        if code.startswith("@"):
            # Prefer user code decorators
            if not is_framework_code(filepath, framework_paths):
                decorator_frames.append(frame)

    # Return the last (deepest) decorator frame
    return decorator_frames[-1] if decorator_frames else None


def find_most_relevant_user_frame(
    traceback_frames: List[Dict[str, Any]], exception: Exception, framework_paths: Optional[List[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Find the most relevant user code frame.

    This is smarter than just finding the first user code:
    1. For decorator errors, find the decorator application
    2. For import errors at module level, find the problematic module
    3. For runtime errors, find the first user code in the call stack

    Args:
        traceback_frames: List of traceback frames
        exception: The original exception
        framework_paths: Framework paths to exclude

    Returns:
        Most relevant user code frame
    """
    if not traceback_frames:
        return None

    # Strategy 1: Look for decorator patterns (highest priority)
    # Decorators typically appear as @something at the start of a line
    decorator_frame = _find_decorator_frame(traceback_frames, framework_paths)
    if decorator_frame:
        return decorator_frame

    # Strategy 2: For errors at module level (<module> function),
    # find the LAST user code frame (deepest in import chain)
    module_level_frames = [
        f
        for f in traceback_frames
        if f.get("function") == "<module>" and not is_framework_code(f.get("file", ""), framework_paths)
    ]

    if module_level_frames:
        # Get the last (deepest) module-level frame
        # This is the actual file with the problem, not the file importing it
        last_module_frame = module_level_frames[-1]

        # Check if this looks like a decorator/class definition
        code = last_module_frame.get("code", "").strip()
        if code.startswith("@") or code.startswith("class ") or code.startswith("def "):
            return last_module_frame

    # Strategy 3: For runtime errors, find first user code walking backwards
    for i in range(len(traceback_frames) - 1, -1, -1):
        frame = traceback_frames[i]
        filepath = frame.get("file", "")

        if not is_framework_code(filepath, framework_paths):
            return frame

    return None


def extract_extended_context(
    filename: str, line_number: int, context_lines: int = 10
) -> tuple[str, List[tuple[int, str]], Optional[str], Optional[int]]:
    """
    Extract extended context around an error line.

    Tries to identify what the user was doing:
    - Class definition
    - Function definition
    - Decorator application
    - Method call

    Args:
        filename: File containing the error
        line_number: Line number of error
        context_lines: Lines of context to show

    Returns:
        Tuple of (context_type, source_context, highlighted_item, code_block_start)
        - context_type: 'class', 'function', 'method_call', 'decorator', 'statement'
        - source_context: [(line_num, line_text), ...]
        - highlighted_item: Name of class/function/etc being defined
        - code_block_start: Line number where the code block starts
    """
    try:
        with open(filename, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if line_number > len(lines) or line_number < 1:
            return "unknown", [], None, None

        # Calculate context range
        start = max(0, line_number - context_lines - 1)
        end = min(len(lines), line_number + context_lines)

        source_context = []
        for i in range(start, end):
            source_context.append((i + 1, lines[i].rstrip()))

        # Analyze what's happening at the error line and before
        error_line_text = lines[line_number - 1].strip()

        # Look backwards to find the context
        context_type = "statement"
        highlighted_item = None
        code_block_start = None

        # Look for decorator (starts with @)
        if error_line_text.startswith("@"):
            context_type = "decorator"
            # Extract decorator name
            match = re.match(r"@(\w+)", error_line_text)
            if match:
                highlighted_item = match.group(1)
            code_block_start = line_number

        # Look backwards for class/function definition
        for i in range(line_number - 1, max(0, line_number - 20), -1):
            line = lines[i].strip()

            # Check for class definition
            if line.startswith("class "):
                match = re.match(r"class\s+(\w+)", line)
                if match:
                    context_type = "class"
                    highlighted_item = match.group(1)
                    code_block_start = i + 1
                    break

            # Check for function/method definition
            elif line.startswith("def "):
                match = re.match(r"def\s+(\w+)", line)
                if match:
                    context_type = "function"
                    highlighted_item = match.group(1)
                    code_block_start = i + 1
                    break

            # Check for decorator before class/function
            elif line.startswith("@"):
                match = re.match(r"@(\w+)", line)
                if match:
                    context_type = "decorator"
                    highlighted_item = match.group(1)
                    code_block_start = i + 1
                    # Keep looking for the class/function it decorates
                    continue

        # If error line contains a method call, try to identify it
        if context_type == "statement":
            # Look for method calls like .as_inlet(...), .add_inlet(...)
            method_match = re.search(r"\.(\w+)\(", error_line_text)
            if method_match:
                context_type = "method_call"
                highlighted_item = method_match.group(1)

        return context_type, source_context, highlighted_item, code_block_start

    except (IOError, OSError):
        return "unknown", [], None, None


def analyze_error_context(
    traceback_frames: List[Dict[str, Any]], selected_frame: Dict[str, Any], exception: Exception
) -> Dict[str, Any]:
    """
    Analyze the error context to provide better insights.

    Looks at the relationship between frames to understand:
    - Is this an import-time error?
    - What was the user trying to do?
    - Where did the error chain start?

    Returns:
        Dictionary with analysis results
    """
    function_name = selected_frame.get("function", "")
    code = selected_frame.get("code", "").strip()
    filename = selected_frame.get("file", "")

    # Find the frame that triggered this
    trigger_frame = None
    selected_idx = None

    for i, frame in enumerate(traceback_frames):
        if frame == selected_frame:
            selected_idx = i
            break

    if selected_idx is not None and selected_idx > 0:
        trigger_frame = traceback_frames[selected_idx - 1]

    # Determine the context
    is_import_error = function_name == "<module>"
    is_decorator_error = code.startswith("@")
    is_class_definition = "class " in code

    # Build context info
    context = {
        "is_import_error": is_import_error,
        "is_decorator_error": is_decorator_error,
        "is_class_definition": is_class_definition,
        "trigger_frame": trigger_frame,
        "error_origin": "import_time" if is_import_error else "runtime",
    }

    # Add helpful explanation
    if is_import_error and trigger_frame:
        trigger_code = trigger_frame.get("code", "").strip()
        if trigger_code.startswith("from ") or trigger_code.startswith("import "):
            context["explanation"] = (
                f"Error occurred while importing. "
                f"The problematic code is in '{os.path.basename(filename)}', "
                f"which was being imported."
            )

    return context


def enhance_error_message_for_context(
    context_type: str, highlighted_item: Optional[str], original_message: str, error_context: Dict[str, Any]
) -> tuple[str, List[str]]:
    """
    Generate contextual error message and suggestions.

    Args:
        context_type: Type of code context ('class', 'function', etc.)
        highlighted_item: Name of the item (class name, function name, etc.)
        original_message: Original exception message
        error_context: Additional context from analyze_error_context()

    Returns:
        Tuple of (enhanced_message, suggestions)
    """
    suggestions = []
    message_parts = []

    # Add import context if relevant
    if error_context.get("explanation"):
        message_parts.append(error_context["explanation"])

    # Add context-specific message
    if context_type == "class" and highlighted_item:
        message_parts.append(f"Error in class '{highlighted_item}': {original_message}")
        suggestions.append(f"Check the '{highlighted_item}' class definition")
        suggestions.append("Review decorator parameters and class attributes")

    elif context_type == "decorator" and highlighted_item:
        message_parts.append(f"Error in @{highlighted_item} decorator: {original_message}")
        suggestions.append(f"Check the @{highlighted_item} decorator parameters")
        suggestions.append("Ensure all required parameters are provided")

    elif context_type == "function" and highlighted_item:
        message_parts.append(f"Error in function '{highlighted_item}': {original_message}")
        suggestions.append(f"Check the '{highlighted_item}' function definition")

    elif context_type == "method_call" and highlighted_item:
        message_parts.append(f"Error calling .{highlighted_item}(): {original_message}")
        suggestions.append(f"Check the arguments passed to .{highlighted_item}()")
        suggestions.append("Verify the parameter types and values")

    else:
        message_parts.append(original_message)
        suggestions.append("Review the highlighted line in your code")

    message = "\n".join(message_parts)

    return message, suggestions


# ============================================================================
# MAIN EXCEPTION CLASS
# ============================================================================


@dataclass
class HaywireException(Exception):
    """
    Unified exception with structured error data for UI rendering.

    This is the single source of truth for all user-facing errors in Haywire.
    Combines the functionality of the old HaywireError and HaywireException.

    Usage:
        ```
        HaywireException.create(
            "Node failed to load",
            severity=ErrorSeverity.ERROR,
            category="Node Load Error"
        )
        HaywireException.from_exception(
            exc,
            message="Widget rendering failed",
            operation="render"
        ).enrich(registry_key="mylib:MyWidget")
        ```
    """

    # ========================================================================
    # USER-FACING CONTENT (for UI display)
    # ========================================================================

    message: str
    """Primary user-facing message (shown in notifications, widget headers)"""

    severity: ErrorSeverity = ErrorSeverity.ERROR
    """Severity for UI styling and filtering"""

    category: str = "Error"
    """Human-readable category (e.g., "Import Error", "Render Failed")"""

    suggestions: List[str] = field(default_factory=list)
    """User actions they can take (shown in UI as action items)"""

    # ========================================================================
    # SOURCE LOCATION (for ErrorWidget code display)
    # ========================================================================

    filename: Optional[str] = None
    """File where error occurred"""

    line_number: Optional[int] = None
    """Line number in file"""

    source_line: Optional[str] = None
    """The actual line of code"""

    source_context: List[tuple] = field(default_factory=list)
    """Context lines: [(line_num, content), ...]"""

    highlight_span: Optional[tuple] = None
    """(start_col, length) for highlighting specific text"""

    # ========================================================================
    # HAYWIRE CONTEXT (what was happening in the system)
    # ========================================================================

    operation: Optional[str] = None
    """Operation being performed: 'import', 'render', 'hot_reload', 'execute'"""

    library_identity: Optional[LibraryIdentity] = None
    """Which library this relates to"""

    registry_key: Optional[str] = None
    """Node/widget/renderer registry key"""

    module_name: Optional[str] = None
    """Python module name"""

    # ========================================================================
    # TECHNICAL DETAILS (for advanced users / debugging)
    # ========================================================================

    traceback_frames: List[Dict[str, Any]] = field(default_factory=list)
    """Simplified traceback for UI: [{'file', 'line', 'function', 'code'}, ...]"""

    original_exception: Optional[Exception] = None
    """Original Python exception (for re-raising or advanced inspection)"""

    context_type: Optional[str] = None
    """Type of code context: 'class', 'function', 'decorator', 'method_call', etc."""

    highlighted_item: Optional[str] = None
    """Name of class/function/decorator being worked on"""

    error_context: Dict[str, Any] = field(default_factory=dict)
    """Additional context metadata from analysis"""

    # ========================================================================
    # METADATA (for UI behavior and filtering)
    # ========================================================================

    timestamp: Optional[float] = None
    """When error occurred (for event log sorting)"""

    is_dismissible: bool = True
    """Can user dismiss this? (Critical errors might not be)"""

    is_actionable: bool = False
    """Does this have user actions? (auto-set from suggestions)"""

    auto_retry: bool = False
    """Should system auto-retry on hot-reload?"""

    tags: List[str] = field(default_factory=list)
    """Tags for filtering: ['hot-reload', 'widget', 'import', etc.]"""

    def __post_init__(self):
        """Initialize exception and compute derived fields"""
        super().__init__(self.message)

        # Auto-compute derived fields
        if self.suggestions:
            self.is_actionable = True

        if self.timestamp is None:
            self.timestamp = time.time()

        # Auto-tag based on context
        if self.operation:
            self.tags.append(self.operation)
        if self.severity:
            self.tags.append(self.severity.value)

    # ========================================================================
    # BUILDER METHODS (fluent API for construction)
    # ========================================================================

    @classmethod
    def create(
        cls,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: str = "Error",
        **kwargs,
    ) -> "HaywireException":
        """
        Create a new exception with minimal information.

        Use this when you're creating an error from scratch (not from exception).

        Args:
            message: User-facing error message
            severity: Error severity level
            category: Human-readable category
            **kwargs: Additional fields

        Returns:
            New HaywireException instance
        """
        return cls(message=message, severity=severity, category=category, **kwargs)

    @classmethod
    def _extract(cls, exception: Exception) -> Dict[str, Any]:
        """
        Extract technical details from a Python exception.

        This is a low-level method that extracts traceback, source location,
        error type, etc. without creating a HaywireException instance.

        Enhanced with smart frame detection to find the most relevant user code.

        Useful for:
        - Custom exception creation logic
        - Enriching existing exceptions with extracted data
        - Advanced error handling scenarios

        Args:
            exception: The caught exception to extract from

        Returns:
            Dictionary with extracted fields:
            - filename, line_number, source_line, source_context
            - highlight_span, traceback_frames, original_exception
            - exc_message, exc_category (for mapping to message/category if not set)
            - context_type, highlighted_item, error_context
            - suggestions (auto-generated based on context)

        Example:
            try:
                risky_operation()
            except Exception as exc:
                extracted = HaywireException.extract(exc)
                error = HaywireException.create(
                    "Operation failed",
                    **extracted
                )
        """
        # Get exception info
        exc_type, exc_value, exc_tb = sys.exc_info()
        if exc_type is None and exception is not None:
            exc_type = type(exception)
            exc_value = exception

        # Build simplified traceback for UI
        traceback_frames = []
        if exc_tb:
            for frame_summary in tb_module.extract_tb(exc_tb):
                traceback_frames.append(
                    {
                        "file": frame_summary.filename,
                        "line": frame_summary.lineno,
                        "function": frame_summary.name,
                        "code": frame_summary.line or "",
                    }
                )

        # Find the most relevant user code frame (SMART DETECTION)
        user_frame = find_most_relevant_user_frame(traceback_frames, exception)

        filename = None
        line_number = None
        source_line = None
        source_context = []
        highlight_span = None
        context_type = "unknown"
        highlighted_item = None
        error_context = {}

        if user_frame:
            # Analyze the context
            error_context = analyze_error_context(traceback_frames, user_frame, exception)

            # Extract extended context
            filename = user_frame["file"]
            line_number = user_frame["line"]

            context_type, source_context, highlighted_item, code_block_start = extract_extended_context(
                filename, line_number, context_lines=10
            )

            # Find the source line to display
            for ln, text in source_context:
                if ln == line_number:
                    source_line = text

                    # Try to highlight the problematic part
                    if highlighted_item and highlighted_item in text:
                        pos = text.find(highlighted_item)
                        highlight_span = (pos, len(highlighted_item))
                    break

        # Fallback to standard extraction
        elif isinstance(exception, SyntaxError) and hasattr(exception, "filename"):
            filename = exception.filename
            line_number = exception.lineno
            context_type, source_context, highlighted_item, _ = extract_extended_context(
                filename, line_number
            )

        elif traceback_frames:
            # Last resort - use last frame
            last_frame = traceback_frames[-1]
            filename = last_frame["file"]
            line_number = last_frame["line"]
            source_line = last_frame["code"]

            # Try to get some context
            if filename and line_number:
                try:
                    with open(filename, "r", encoding="utf-8") as f:
                        lines = f.readlines()

                    if line_number <= len(lines):
                        # Get context around error
                        context_range = 2
                        start = max(0, line_number - context_range - 1)
                        end = min(len(lines), line_number + context_range)

                        for i in range(start, end):
                            source_context.append((i + 1, lines[i].rstrip()))

                        source_line = lines[line_number - 1].rstrip()

                        # Try to find highlighted text
                        quoted_matches = re.findall(r"'([^']+)'", str(exception))
                        for quoted_string in quoted_matches:
                            if quoted_string in source_line:
                                pos = source_line.find(quoted_string)
                                highlight_span = (pos, len(quoted_string))
                                break
                except (IOError, OSError, IndexError):
                    pass

        # Generate base messages
        exc_message = str(exc_value) if exc_value else "Unknown error"
        exc_category = exc_type.__name__ if exc_type else "Error"

        # Enhance message with context
        enhanced_message, suggestions = enhance_error_message_for_context(
            context_type, highlighted_item, exc_message, error_context
        )

        return {
            "filename": filename,
            "line_number": line_number,
            "source_line": source_line,
            "source_context": source_context,
            "highlight_span": highlight_span,
            "traceback_frames": traceback_frames,
            "exc_message": enhanced_message,  # Enhanced with context
            "exc_category": exc_category,
            "original_exception": exception,
            "suggestions": suggestions,  # Auto-generated suggestions
            "context_type": context_type,  # For UI rendering decisions
            "highlighted_item": highlighted_item,  # Class/function name
            "error_context": error_context,  # Additional context info
        }

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        operation: Optional[str] = None,
        **kwargs,
    ) -> "HaywireException":
        """
        Create from a caught Python exception with auto-extraction.

        This replaces the old generate_haywire_error() function.
        Automatically extracts: traceback, source location, error type, etc.
        Uses smart frame detection to find the most relevant user code.

        Args:
            exception: The caught exception
            message: User-facing error message
            severity: Error severity level
            operation: Operation being performed
            **kwargs: Additional fields

        Returns:
            New HaywireException with extracted context
        """
        # Extract technical details
        extracted = cls._extract(exception)

        # Map exc_message and exc_category to message/category if not provided
        exc_message = extracted.pop("exc_message", None)
        exc_category = extracted.pop("exc_category", "Error")

        # Use extracted category if not explicitly overridden in kwargs
        if "category" not in kwargs:
            kwargs["category"] = exc_category

        # Merge extracted suggestions with user-provided ones
        extracted_suggestions = extracted.pop("suggestions", [])
        if "suggestions" in kwargs:
            kwargs["suggestions"].extend(extracted_suggestions)
        else:
            kwargs["suggestions"] = extracted_suggestions

        # Merge with user-provided kwargs (user values take precedence)
        extracted.update(kwargs)

        return cls(
            message=message or exc_message or exc_category or "Unknown Error",
            severity=severity,
            operation=operation,
            **extracted,
        )

    def enrich(
        self,
        *,
        exception: Optional[Exception] = None,
        registry_key: Optional[str] = None,
        library_identity: Optional[LibraryIdentity] = None,
        node_id: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        **kwargs,
    ) -> "HaywireException":
        """
        Add context as error propagates (chainable).

        Can also extract and add technical details from an exception.

        Examples:
            # Add context metadata
            error.enrich(registry_key="lib:Node", node_id="node_123")

            # Extract from exception if technical details missing
            error.enrich(exception=exc, registry_key="lib:Node")

            # Chain multiple enrichments
            error.enrich(registry_key="lib:Node").enrich(suggestions=["Try X"])

        Args:
            exception: Optional exception to extract technical details from
            registry_key: Registry key to add
            library_identity: Library identity to add
            node_id: Node ID to add
            suggestions: Suggestions to add
            **kwargs: Other attributes to set

        Returns:
            Self for chaining
        """
        # Extract from exception if provided and we don't have technical details yet
        if exception and not self.has_source_location():
            extracted = self.__class__._extract(exception)
            for key, value in extracted.items():
                if not getattr(self, key, None):  # Only set if not already present
                    setattr(self, key, value)

        if registry_key:
            self.registry_key = registry_key
        if library_identity:
            self.library_identity = library_identity
        if suggestions:
            self.suggestions.extend(suggestions)
            self.is_actionable = True

        for key, value in kwargs.items():
            if hasattr(self, key) and value is not None:
                setattr(self, key, value)

        return self

    # ========================================================================
    # QUERY METHODS (for UI filtering and display logic)
    # ========================================================================

    def is_info(self) -> bool:
        """Informational - typically not shown as error"""
        return self.severity == ErrorSeverity.INFO

    def is_warning(self) -> bool:
        """Warning - shown but not critical"""
        return self.severity == ErrorSeverity.WARNING

    def is_error(self) -> bool:
        """Error - operation failed"""
        return self.severity == ErrorSeverity.ERROR

    def is_critical(self) -> bool:
        """Critical - system cannot continue"""
        return self.severity == ErrorSeverity.CRITICAL

    def should_notify_user(self) -> bool:
        """Should we show a notification/toast?"""
        return self.severity in (ErrorSeverity.ERROR, ErrorSeverity.CRITICAL)

    def should_show_in_event_log(self) -> bool:
        """Should appear in the future event log panel?"""
        return True  # All errors go to event log

    def has_source_location(self) -> bool:
        """Do we have source code to display?"""
        return self.filename is not None and self.line_number is not None

    def has_suggestions(self) -> bool:
        """Do we have user actions?"""
        return len(self.suggestions) > 0

    def matches_registry_key(self, key: str) -> bool:
        """Is this error related to a specific registry key?"""
        return self.registry_key == key

    def matches_operation(self, operation: str) -> bool:
        """Did this occur during a specific operation?"""
        return self.operation == operation

    def matches_tag(self, tag: str) -> bool:
        """Does this have a specific tag?"""
        return tag in self.tags

    # ========================================================================
    # UI HELPERS (convenience methods for widgets)
    # ========================================================================

    def get_summary(self) -> str:
        """Get short summary for notifications/toasts"""
        return self.message

    def get_title(self) -> str:
        """Get title for error displays"""
        return f"{self.category}: {self.severity.value.upper()}"

    def get_severity_color(self) -> str:
        """Get color for UI styling"""
        colors = {
            ErrorSeverity.INFO: "blue",
            ErrorSeverity.WARNING: "yellow",
            ErrorSeverity.ERROR: "orange",
            ErrorSeverity.CRITICAL: "red",
        }
        return colors.get(self.severity, "gray")

    def get_severity_icon(self) -> str:
        """Get icon for UI display"""
        icons = {
            ErrorSeverity.INFO: "info",
            ErrorSeverity.WARNING: "warning",
            ErrorSeverity.ERROR: "error",
            ErrorSeverity.CRITICAL: "dangerous",
        }
        return icons.get(self.severity, "error")

    # ========================================================================
    # LOGGING / SERIALIZATION
    # ========================================================================

    def log(self, logger=None) -> "HaywireException":
        """Log to console (fallback when UI not available)"""
        import logging

        logger = logger or logging.getLogger()
        logger.error(self.format_detailed())
        return self

    def is_interesting_frame(self, frame: Dict[str, Any]) -> bool:
        """Filter out uninteresting frames"""
        filepath = frame["file"]

        # Skip Python internals
        if filepath.startswith("<frozen"):
            return False
        if "_bootstrap" in filepath:
            return False
        if "importlib" in filepath and "site-packages" not in filepath:
            return False

        return True

    def format_detailed(self) -> str:
        """
        Format for detailed console output.

        This is the FALLBACK - primary display is ErrorWidget.
        Maintains the beautiful formatting from the original HaywireError.
        """
        # Calculate box width based on category text
        category_text = f"    {self.category}    "
        box_width = len(category_text)
        horizontal_bar = "━" * box_width

        lines = [
            "\n",
            f"┏{horizontal_bar}┓",
            f"┃{category_text}┃",
            f"┗{horizontal_bar}┛\n",
            f"Operation : {self.operation or 'Unknown'}",
            f"Message   : {self.message}",
            "-----------------------------------",
        ]

        if self.library_identity:
            lines.append(f"Library   : {self.library_identity.label}")
            lines.append(f"Lib_Path  : {self.library_identity.folder_path}")

        if self.registry_key:
            lines.append(f"Registry  : {self.registry_key}")

        if self.module_name:
            lines.append(f"Module    : {self.module_name}")

        if self.context_type:
            lines.append(f"Context   : {self.context_type}")

        if self.highlighted_item:
            lines.append(f"Item      : {self.highlighted_item}")

        lines.append("")

        # Find the user frame index in traceback_frames
        user_frame_index = None
        if self.filename and self.line_number and self.traceback_frames:
            for i, frame in enumerate(self.traceback_frames):
                if frame["file"] == self.filename and frame["line"] == self.line_number:
                    user_frame_index = i
                    break

        # Split traceback into: before user frame, user frame, after user frame
        frames_before = []
        frames_after = []

        if user_frame_index is not None:
            frames_before = self.traceback_frames[:user_frame_index]
            # Skip the user frame itself
            frames_after = self.traceback_frames[user_frame_index + 1 :]
        elif self.traceback_frames:
            # Fallback: if we can't find user frame, show all as "after"
            frames_after = self.traceback_frames

        # Display call chain BEFORE the user code (reversed order, going down)
        if frames_before:
            lines.append("Call Chain:")

            # Filter out uninteresting frames
            interesting_frames_before = [f for f in frames_before if self.is_interesting_frame(f)]
            for i, frame in enumerate(interesting_frames_before):
                base_filename = os.path.basename(frame["file"])
                indent_spaces = "  " * (len(interesting_frames_before) - i - 1)

                # Use reversed box drawing (going down instead of up)
                lines.append(
                    f"             {indent_spaces}╒═╧═ {base_filename} in "
                    f'{frame["function"]} | File "{frame["file"]}"'
                )
                lines.append(f"             {indent_spaces}│    │   ┌─────┄┄┄")
                lines.append(
                    f"             {indent_spaces}│    └───┤ line {frame['line']}: {frame['code'].strip()}"
                )
                lines.append(f"             {indent_spaces}│        └─────┄┄┄")
                lines.append(f"             {indent_spaces}│")

        # Display the focused user code section
        if self.filename:
            if frames_before:
                lines.append(f"File      :╒═╧═ {self.filename}")
            else:
                lines.append(f"File      :╒══ {self.filename}")

            lines.append("           ┆")

            # Format technical error details if available
            if self.original_exception:
                exc_type_name = type(self.original_exception).__name__
                exc_message = str(self.original_exception)
                error_msg = f"{exc_type_name}: {exc_message}"

                if "\n" in error_msg:
                    error_lines = error_msg.split("\n")
                    lines.append(f"Error     : {error_lines[0]}")
                    for line in error_lines[1:]:
                        lines.append(f"            {line}")
                else:
                    lines.append("")
                    lines.append(f"Error     : {error_msg}")
                lines.append("")

            # Add suggestions if available
            if self.suggestions:
                lines.append("Suggestion: " + self.suggestions[0])
                for suggestion in self.suggestions[1:]:
                    lines.append(f"            {suggestion}")

            lines.append("           ┆")

            # Add context lines with fancy box drawing
            if self.source_context:
                for actual_line_num, line in self.source_context:
                    if actual_line_num == self.line_number:  # This is the error line
                        line_prefix = f" »line {self.line_number:2d}: "
                        content_line = f"{line_prefix}{line}"
                        total_content_width = len(content_line) + 6

                        # Create border patterns
                        left_pattern = "━━╍╍╍┅┅┅┅┉┉┉"
                        right_pattern = "┉┉┅┅┅╍╍╍━━"
                        gap_width = max(20, total_content_width - len(left_pattern) - len(right_pattern))
                        gap_spaces = " " * gap_width

                        top_border = left_pattern + gap_spaces + right_pattern
                        bottom_border = left_pattern + gap_spaces + right_pattern

                        padded_content = content_line + " " * 6
                        content_width = len(top_border)

                        lines.append(f"Source    :┢{top_border}┓")
                        lines.append(f"Source    :┃{padded_content:<{content_width}}┃")
                        lines.append(f"Source    :┡{bottom_border}┛")
                    else:
                        lines.append(f"Source    :│  line {actual_line_num:2d}: {line}")

            lines.append("           ┆")

        # Display traceback continuation AFTER user frame (original order, going up)
        if frames_after:
            # Filter out uninteresting frames and remove duplicates
            seen_frames = set()
            interesting_frames_after = []

            for frame in frames_after:
                # Create a unique key for this frame
                frame_key = (frame["file"], frame["line"], frame["function"])

                # Only add if it's interesting and we haven't seen it before
                if self.is_interesting_frame(frame) and frame_key not in seen_frames:
                    interesting_frames_after.append(frame)
                    seen_frames.add(frame_key)

            for i, frame in enumerate(interesting_frames_after):
                base_filename = os.path.basename(frame["file"])
                space_indent = "  " * i

                lines.append(
                    f"           {space_indent}╘═╤═ {base_filename} in "
                    f'{frame["function"]} | File "{frame["file"]}"'
                )
                lines.append(f"           {space_indent}  │    │   ┌─────┄┄┄")
                lines.append(
                    f"           {space_indent}  │    └───┤ line {frame['line']}: {frame['code'].strip()}"
                )
                lines.append(f"           {space_indent}  │        └─────┄┄┄")
                lines.append(f"           {space_indent}  │")

        lines.extend(["", f"┏{horizontal_bar}┓", f"┃{category_text}┃", f"┗{horizontal_bar}┛", "\n"])

        # self.debug_traceback(lines, user_frame_index)

        return "\n".join(lines)

    def debug_traceback(self, lines: list[str], user_frame_index: int) -> str:
        # =======================================================================
        # DEBUG SECTION - Complete traceback analysis
        # =======================================================================
        lines.append("")
        lines.append("=" * 80)
        lines.append("DEBUG: COMPLETE TRACEBACK ANALYSIS")
        lines.append("=" * 80)
        lines.append("")

        lines.append(f"Selected user frame index: {user_frame_index}")
        lines.append(f"Selected file: {self.filename}")
        lines.append(f"Selected line: {self.line_number}")
        lines.append(f"Context type: {self.context_type}")
        lines.append(f"Highlighted item: {self.highlighted_item}")
        lines.append("")

        lines.append("All traceback frames:")
        lines.append("-" * 80)
        for i, frame in enumerate(self.traceback_frames):
            is_user = not is_framework_code(frame["file"])
            is_selected = i == user_frame_index
            marker = " >>> SELECTED" if is_selected else ""
            user_marker = " [USER CODE]" if is_user else " [FRAMEWORK]"

            lines.append(f"Frame {i}{marker}{user_marker}:")
            lines.append(f"  File: {frame['file']}")
            lines.append(f"  Line: {frame['line']}")
            lines.append(f"  Function: {frame['function']}")
            lines.append(f"  Code: {frame['code'].strip()}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("")

        return

    def to_dict(self) -> dict:
        """
        Serialize for future event log system.

        This will be used when you implement the NiceGUI event log panel.
        """
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category,
            "timestamp": self.timestamp,
            "operation": self.operation,
            "registry_key": self.registry_key,
            "filename": self.filename,
            "line_number": self.line_number,
            "source_line": self.source_line,
            "suggestions": self.suggestions,
            "tags": self.tags,
            "is_dismissible": self.is_dismissible,
            "is_actionable": self.is_actionable,
            "context_type": self.context_type,
            "highlighted_item": self.highlighted_item,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HaywireException":
        """Reconstruct from serialized form (for event log persistence)"""
        # Convert severity string back to enum
        if "severity" in data and isinstance(data["severity"], str):
            data["severity"] = ErrorSeverity(data["severity"])
        return cls(**data)
