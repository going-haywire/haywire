"""
Unified HaywireException - UI-first exception for user-facing errors

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

from haywire.core.library.library_identity import LibraryIdentity


class ErrorSeverity(Enum):
    """Severity levels for UI display and filtering"""
    INFO = 'info'           # Informational (blue) - "Node reloaded"
    WARNING = 'warning'     # Warning (yellow) - "Using fallback widget"
    ERROR = 'error'         # Error (orange) - "Failed to render"
    CRITICAL = 'critical'   # Critical (red) - "System component failed"


@dataclass
class HaywireException(Exception):
    """
    Unified exception with structured error data for UI rendering.
    
    This is the single source of truth for all user-facing errors in Haywire.
    Combines the functionality of the old HaywireError and HaywireException.
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
        **kwargs
    ) -> 'HaywireException':
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
    def extract(cls, exception: Exception) -> Dict[str, Any]:
        """
        Extract technical details from a Python exception.
        
        This is a low-level method that extracts traceback, source location,
        error type, etc. without creating a HaywireException instance.
        
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
                traceback_frames.append({
                    'file': frame_summary.filename,
                    'line': frame_summary.lineno,
                    'function': frame_summary.name,
                    'code': frame_summary.line or ''
                })
        
        # Extract primary error location (last frame or from SyntaxError)
        filename = None
        line_number = None
        source_line = None
        source_context = []
        highlight_span = None
        
        # Special handling for SyntaxError
        if isinstance(exception, SyntaxError) and hasattr(exception, 'filename'):
            filename = exception.filename
            line_number = exception.lineno
        elif traceback_frames:
            # Use last frame
            last_frame = traceback_frames[-1]
            filename = last_frame['file']
            line_number = last_frame['line']
        
        # Try to read source context
        if filename and line_number:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
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
        
        # Generate message and category from exception if not provided
        # These will be used as defaults when creating the exception
        exc_message = str(exc_value) if exc_value else "Unknown error"
        exc_category = exc_type.__name__ if exc_type else "Error"
        
        return {
            'filename': filename,
            'line_number': line_number,
            'source_line': source_line,
            'source_context': source_context,
            'highlight_span': highlight_span,
            'traceback_frames': traceback_frames,
            'exc_message': exc_message,  # Will map to message if not set
            'exc_category': exc_category,  # Will map to category if not set
            'original_exception': exception,
        }
    
    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        message: str,
        *,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        operation: Optional[str] = None,
        **kwargs
    ) -> 'HaywireException':
        """
        Create from a caught Python exception with auto-extraction.
        
        This replaces the old generate_haywire_error() function.
        Automatically extracts: traceback, source location, error type, etc.
        
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
        extracted = cls.extract(exception)
        
        # Map exc_message and exc_category to message/category if not provided
        exc_message = extracted.pop('exc_message', None)
        exc_category = extracted.pop('exc_category', 'Error')
        
        # Use extracted category if not explicitly overridden in kwargs
        if 'category' not in kwargs:
            kwargs['category'] = exc_category
        
        # Merge with user-provided kwargs (user values take precedence)
        extracted.update(kwargs)
        
        return cls(
            message=message,
            severity=severity,
            operation=operation,
            **extracted
        )
    
    def enrich(
        self,
        *,
        exception: Optional[Exception] = None,
        registry_key: Optional[str] = None,
        library_identity: Optional[LibraryIdentity] = None,
        node_id: Optional[str] = None,
        suggestions: Optional[List[str]] = None,
        **kwargs
    ) -> 'HaywireException':
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
            extracted = self.__class__.extract(exception)
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
            ErrorSeverity.INFO: 'blue',
            ErrorSeverity.WARNING: 'yellow',
            ErrorSeverity.ERROR: 'orange',
            ErrorSeverity.CRITICAL: 'red'
        }
        return colors.get(self.severity, 'gray')
    
    def get_severity_icon(self) -> str:
        """Get icon for UI display"""
        icons = {
            ErrorSeverity.INFO: 'info',
            ErrorSeverity.WARNING: 'warning',
            ErrorSeverity.ERROR: 'error',
            ErrorSeverity.CRITICAL: 'dangerous'
        }
        return icons.get(self.severity, 'error')
    
    # ========================================================================
    # LOGGING / SERIALIZATION
    # ========================================================================
    
    def log(self, logger=None) -> 'HaywireException':
        """Log to console (fallback when UI not available)"""
        import logging
        logger = logger or logging.getLogger()
        logger.error(self.format_detailed())
        return self
    
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
            f"-----------------------------------",
        ]
        
        # Format technical error details if available
        if self.original_exception:
            exc_type_name = type(self.original_exception).__name__
            exc_message = str(self.original_exception)
            error_msg = f"{exc_type_name}: {exc_message}"
            
            if '\n' in error_msg:
                error_lines = error_msg.split('\n')
                lines.append(f"")
                lines.append(f"Error     : {error_lines[0]}")
                for line in error_lines[1:]:
                    lines.append(f"            {line}")
            else:
                lines.append(f"")
                lines.append(f"Error     : {error_msg}")
            lines.append(f"")
        
        # Add suggestions if available
        if self.suggestions:
            lines.append("Suggestion: " + self.suggestions[0])
            for suggestion in self.suggestions[1:]:
                lines.append(f"            {suggestion}")
            lines.append("")

        if self.library_identity:
            lines.append(f"Library   : {self.library_identity.label}")
            lines.append(f"Lib_Path  : {self.library_identity.folder_path}")
            
        if self.registry_key:
            lines.append(f"Registry  : {self.registry_key}")
        
        if self.module_name:
            lines.append(f"Module    : {self.module_name}")
        
        if self.filename:
            if self.library_identity and self.library_identity.folder_path and self.filename:
                try:
                    rel_path = os.path.relpath(self.filename, self.library_identity.folder_path)
                    # Only use relative path if it's not escaping the library folder
                    if not rel_path.startswith(".."):
                        lines.append(f"File      :╒══ ./{rel_path}")
                    else:
                        lines.append(f"File      :╒══ {self.filename}")
                except ValueError:
                    # relpath can fail if paths are on different drives (Windows)
                    lines.append(f"File      :╒══ {self.filename}")
            else:
                lines.append(f"File      :╒══ {self.filename}")
                
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
        
        # Add traceback information if available
        if self.traceback_frames:
            import os
            for i, frame in enumerate(self.traceback_frames):
                base_filename = os.path.basename(frame['file'])
                space_indent = "  " * i
                
                lines.append(f"           {space_indent}╘═╤═ {base_filename} in {frame['function']} | File \"{frame['file']}\"")
                lines.append(f"           {space_indent}  │    │   ┌─────┄┄┄")
                lines.append(f"           {space_indent}  │    └───┤ line {frame['line']}: {frame['code'].strip()} ")
                lines.append(f"           {space_indent}  │        └─────┄┄┄")
                lines.append(f"           {space_indent}  │")
                
        lines.extend([
            "",
            f"┏{horizontal_bar}┓",
            f"┃{category_text}┃",
            f"┗{horizontal_bar}┛",
            "\n"
        ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> dict:
        """
        Serialize for future event log system.
        
        This will be used when you implement the NiceGUI event log panel.
        """
        return {
            'message': self.message,
            'severity': self.severity.value,
            'category': self.category,
            'timestamp': self.timestamp,
            'operation': self.operation,
            'registry_key': self.registry_key,
            'filename': self.filename,
            'line_number': self.line_number,
            'source_line': self.source_line,
            'suggestions': self.suggestions,
            'tags': self.tags,
            'is_dismissible': self.is_dismissible,
            'is_actionable': self.is_actionable,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'HaywireException':
        """Reconstruct from serialized form (for event log persistence)"""
        # Convert severity string back to enum
        if 'severity' in data and isinstance(data['severity'], str):
            data['severity'] = ErrorSeverity(data['severity'])
        return cls(**data)
          

