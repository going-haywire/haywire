"""
Detailed error handling utilities with structured error context.
"""

from dataclasses import dataclass
from typing import Optional, List, Any, TYPE_CHECKING

import sys
import traceback
import re
import logging

from haywire.core.errors.haywire_exception import HaywireException

from ..library.library_identity import LibraryIdentity

@dataclass
class ErrorContext:
    """Structured error information"""
    error_type: str
    error_message: str
    filename: str
    line_number: int
    source_line: str
    context_lines: List[str]
    message: str  # High-level error message for the user
    highlight_position: Optional[int] = None
    highlight_length: Optional[int] = None
    module_name: Optional[str] = None
    operation: Optional[str] = None  # 'import', 'instantiation', 'syntax_check'
    library_identity: Optional[LibraryIdentity] = None
    registry_key: Optional[str] = None
    class_name: Optional[str] = None
    context_info: Optional[List[tuple]] = None  # List of (line_number, line_content) tuples
    traceback_info: Optional[List[tuple]] = None  # List of (filename, line_number, function_name, source_line) tuples
    suggestions: Optional[List[str]] = None  # NEW: Actionable suggestions
    error_category: str = "Error"  # NEW: Error category for better organization
    
    def format_detailed_message(self) -> str:
        """Format the error as a detailed message"""
        # Calculate box width based on category text
        category_text = f"    {self.error_category}    "
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
        
        # Format error message with indentation if it's multiline
        error_msg = f"{self.error_type}: {self.error_message}"
        if '\n' in error_msg:
            # Indent each line of the error message
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
            
        if self.class_name:
            lines.append(f"Class     : {self.class_name}")
        
        if self.module_name:
            lines.append(f"Module    : {self.module_name}")
        
        if self.library_identity:
            rel_path = self.filename[len(self.library_identity.folder_path):]
            if rel_path == "":
                lines.append(f"File      :╒{self.filename}")
            else:               
                lines.append(f"File      :╒..{rel_path}")
        else:
            lines.append(f"File      :╒{self.filename}")

        lines.append("           ┆")
        
        # Add context lines with fancy box drawing
        # Use context_info if available (which has proper line numbers), otherwise fall back to old method
        context_to_use = self.context_info if self.context_info else [(self.line_number + i - len(self.context_lines) // 2, line) for i, line in enumerate(self.context_lines)]
        
        for i, (actual_line_num, line) in enumerate(context_to_use):
            if actual_line_num == self.line_number:  # This is the error line
                # Calculate content width: line prefix + line content + 6 padding
                line_prefix = f" »line {self.line_number:2d}: "
                content_line = f"{line_prefix}{line}"
                total_content_width = len(content_line) + 6
                
                # Create border patterns with gap in the middle
                left_pattern = "━━╍╍╍┅┅┅┅┉┉┉"
                right_pattern = "┉┉┅┅┅╍╍╍━━"
                gap_width = max(20, total_content_width - len(left_pattern) - len(right_pattern))
                gap_spaces = " " * gap_width
                
                top_border = left_pattern + gap_spaces + right_pattern
                bottom_border = left_pattern + gap_spaces + right_pattern
                
                # Format the error line content with padding
                padded_content = content_line + " " * 6
                content_width = len(top_border)
                
                # Add the box
                lines.append(f"Source    :┢{top_border}┓")
                lines.append(f"Source    :┃{padded_content:<{content_width}}┃")
                lines.append(f"Source    :┡{bottom_border}┛")
            else:
                # Use the actual line number from context_info
                lines.append(f"Source    :│  line {actual_line_num:2d}: {line}")
        
        lines.extend([
            "           ┆"
        ])
        
        # Add traceback information if available
        if self.traceback_info:
            import os
            for i, (filename, line_number, function_name, source_line) in enumerate(self.traceback_info):
                # Extract just the filename from the full path
                base_filename = os.path.basename(filename)

                # Subsequent entries - note the pattern: base + (i-1)*tab + spaces
                space_indent = "  " * i  # Add spaces for each level
                lines.append(f"           {space_indent}╘═╤═ {base_filename} in {function_name} | File \"{filename}\"")
                lines.append(f"           {space_indent}  │    │   ┌─────┄┄┄")
                lines.append(f"           {space_indent}  │    └───┤ line {line_number}: {source_line.strip()} ")
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


def analyze_exception(exception: Exception, 
                     operation: str = None,
                     module_name: str = None,
                     library_identity: LibraryIdentity = None,
                     registry_key: str = None,
                     class_name: str = None,
                     message: str = None) -> ErrorContext:
    """
    Analyze an exception and extract detailed error context.
    
    Special handling for HaywireException types which carry rendering metadata.
    
    Args:
        exception: The caught exception
        operation: Description of what operation failed ('import', 'instantiation', etc.)
        module_name: The module being processed when error occurred
        library_identity: LibraryIdentity instance of the library (if available)
        registry_key: Registry ID of the node/class (if available)
        class_name: Name of the class (if available)
        message: High-level error message for the user
        
    Returns:
        ErrorContext with detailed error information
    """
    from .custom_exception import CustomException
    
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    # Check if this is a self-describing Haywire custom exception
    is_custom_exception = isinstance(exception, CustomException)
    
    if is_custom_exception:
        # Use exception's metadata for primary error location
        filename = exception.error_filename
        line_number = exception.error_line_number
        error_category = exception.error_category
        suggestions = exception.suggestions
        skip_functions = set(exception.skip_frame_functions)
        skip_files = set(exception.skip_frame_files)
        skip_tb_steps = exception.skip_traceback_steps
        show_full = exception.show_full_traceback
        # override operation,
        module_name = exception.module_name if exception.module_name is not None else module_name
        library_identity = exception.library_identity if exception.library_identity is not None else library_identity
    else:
        filename = None
        line_number = None
        error_category = "Error"
        suggestions = None
        skip_functions = set()
        skip_files = set()
        skip_tb_steps = 0
        show_full = True
    
    # Extract traceback information
    traceback_info = []
    if exc_tb:
        # Build traceback from bottom to top (reverse order for display)
        tb_list = []
        current_tb = exc_tb
        while current_tb:
            tb_list.append(current_tb)
            current_tb = current_tb.tb_next
        
        # Process traceback frames (reverse to show call stack top-down)
        for i, tb_frame in enumerate(reversed(tb_list[:-1])):  # Skip the last frame as it's the error location
            frame = tb_frame.tb_frame
            tb_filename = frame.f_code.co_filename
            tb_line_number = tb_frame.tb_lineno
            tb_function_name = frame.f_code.co_name
            
            # For HaywireException, skip the specified number of initial stacktrace frames
            if is_custom_exception and i < skip_tb_steps:
                continue  # Skip this frame based on skip_stacktrace_steps
            
            # Filter frames if this is a HaywireException
            if is_custom_exception and not show_full:
                # Skip frames based on function name or filename
                import os
                base_filename = os.path.basename(tb_filename)
                
                if tb_function_name in skip_functions or base_filename in skip_files:
                    continue  # Skip this frame
            
            # Try to get the source line
            try:
                with open(tb_filename, 'r', encoding='utf-8') as f:
                    tb_lines = f.readlines()
                    if tb_line_number <= len(tb_lines):
                        tb_source_line = tb_lines[tb_line_number - 1].rstrip()
                    else:
                        tb_source_line = "<line not available>"
            except (IOError, OSError):
                tb_source_line = "<source not available>"
            
            traceback_info.append((tb_filename, tb_line_number, tb_function_name, tb_source_line))
    

    if not filename or not line_number:
        # First try to use the first frame from traceback_info if available
        if isinstance(exception, SyntaxError) and hasattr(exception, 'filename') and hasattr(exception, 'lineno'):
            filename = exception.filename
            line_number = exception.lineno
        elif traceback_info:
            filename, line_number, _, _ = traceback_info[0]
        else:
            # Fall back to raw traceback
            tb_for_location = exc_tb
            while tb_for_location and tb_for_location.tb_next:
                tb_for_location = tb_for_location.tb_next
            
            if tb_for_location:
                frame = tb_for_location.tb_frame
                filename = frame.f_code.co_filename
                line_number = tb_for_location.tb_lineno
    
    # Try to read source context
    context_lines = []
    source_line = ""
    highlight_position = None
    highlight_length = None
    context_info = None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if line_number <= len(lines):
            # Get context around the error
            context_range = 2
            start_line = max(0, line_number - context_range - 1)
            end_line = min(len(lines), line_number + context_range)
            
            # Store both the line content and the actual line number for proper formatting
            context_info = []
            for i in range(start_line, end_line):
                context_info.append((i + 1, lines[i].rstrip()))  # Store 1-based line number and content
            
            # Extract just the lines for backward compatibility
            context_lines = [content for _, content in context_info]
            
            source_line = lines[line_number - 1].rstrip()
            
            # Look for strings enclosed in single quotes in the error message
            quoted_matches = re.findall(r"'([^']+)'", str(exception))
            for quoted_string in quoted_matches:
                if quoted_string in source_line:
                    highlight_position = source_line.find(quoted_string)
                    highlight_length = len(quoted_string)
                    break
                        
    except (IOError, OSError, IndexError):
        # Fallback if we can't read the file
        context_lines = [f"<Could not read source from {filename}>"]
        source_line = "<unavailable>"
        context_info = None
    
    # Generate default message if not provided
    if message is None:
        if operation and module_name:
            message = f"Failed to {operation} module '{module_name}'"
        elif operation:
            message = f"Failed to {operation}"
        else:
            message = f"Operation failed: {exception}"
    
    return ErrorContext(
        error_type=exc_type.__name__,
        error_message=str(exc_value),
        filename=filename,
        line_number=line_number,
        source_line=source_line,
        context_lines=context_lines,
        message=message,
        highlight_position=highlight_position,
        highlight_length=highlight_length,
        module_name=module_name,
        operation=operation,
        library_identity=library_identity,
        registry_key=registry_key,
        class_name=class_name,
        context_info=context_info,
        traceback_info=traceback_info,
        suggestions=suggestions,  # NEW
        error_category=error_category  # NEW
    )

def log_detailed_error(exception: Exception,
                      operation: str = None,
                      module_name: str = None,
                      message: str = None,
                      logger: logging.Logger = None,
                      library_identity: LibraryIdentity = None,
                      registry_key: str = None,
                      class_name: str = None) -> HaywireException:
    """
    Create and log a detailed error.
    
    Args:
        exception: The original exception
        operation: What operation was being performed
        module_name: Module being processed
        message: Custom error message
        logger: Logger to use (defaults to root logger)
        library_identity: LibraryIdentity instance of the library (if available)
        registry_key: Registry ID of the node/class (if available)
        class_name: Name of the class (if available)
        
    Returns:
        DetailedError with structured context
    """

    context = analyze_exception(exception, operation, module_name, library_identity, registry_key, class_name, message)

    detailed_error = HaywireException(
        context=context,
        original_exception=exception
    )

    if logger is None:
        logger = logging.getLogger()
    
    logger.error(context.format_detailed_message())
    
    return detailed_error