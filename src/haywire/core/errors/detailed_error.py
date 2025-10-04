"""
Detailed error handling utilities with structured error context.
"""

from dataclasses import dataclass
from typing import Optional, List, Any
import sys
import traceback
import re
import logging


@dataclass
class ErrorContext:
    """Structured error information"""
    error_type: str
    error_message: str
    filename: str
    line_number: int
    source_line: str
    context_lines: List[str]
    highlight_position: Optional[int] = None
    module_name: Optional[str] = None
    operation: Optional[str] = None  # 'import', 'instantiation', 'syntax_check'


class DetailedError(Exception):
    """Custom exception with structured error data"""
    
    def __init__(self, message: str, context: ErrorContext, original_exception: Exception):
        super().__init__(message)
        self.context = context
        self.original_exception = original_exception
    
    def format_detailed_message(self) -> str:
        """Format the error as a detailed message"""
        lines = [
            "\n",
            "========= Error Details ============",
            f"Operation: {self.context.operation or 'Unknown'}",
        ]
        
        if self.context.module_name:
            lines.append(f"Module: {self.context.module_name}")
            
        lines.extend([
            f"File  : {self.context.filename}",
            "",
            "       ┆"
        ])
        
        # Add context lines with fancy box drawing
        for i, line in enumerate(self.context.context_lines):
            if i == len(self.context.context_lines) // 2:  # Middle line is the error line
                # Calculate content width: line prefix + line content + 6 padding
                line_prefix = f" »line {self.context.line_number:2d}: "
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
                lines.append(f"Source:┢{top_border}┓")
                lines.append(f"Source:┃{padded_content:<{content_width}}┃")
                lines.append(f"Source:┡{bottom_border}┛")
            else:
                # Calculate actual line number for context
                offset = i - len(self.context.context_lines) // 2
                actual_line_num = self.context.line_number + offset
                lines.append(f"Source:│  line {actual_line_num:2d}: {line}")
        
        lines.extend([
            "       ┆",
            "",
            f"Error : {self.context.error_type}: {self.context.error_message}",
            "========= Error Details ============"
        ])
        
        return "\n".join(lines)


def analyze_exception(exception: Exception, 
                     operation: str = None,
                     module_name: str = None) -> ErrorContext:
    """
    Analyze an exception and extract detailed error context.
    
    Args:
        exception: The caught exception
        operation: Description of what operation failed ('import', 'instantiation', etc.)
        module_name: The module being processed when error occurred
        
    Returns:
        ErrorContext with detailed error information
    """
    exc_type, exc_value, exc_tb = sys.exc_info()
    
    # For SyntaxError, use the error's own location info instead of traceback
    if isinstance(exception, SyntaxError) and hasattr(exception, 'filename') and hasattr(exception, 'lineno'):
        filename = exception.filename
        line_number = exception.lineno
    else:
        # Get the last frame where the error occurred
        while exc_tb and exc_tb.tb_next:
            exc_tb = exc_tb.tb_next
        
        frame = exc_tb.tb_frame
        filename = frame.f_code.co_filename
        line_number = exc_tb.tb_lineno
    
    # Try to read source context
    context_lines = []
    source_line = ""
    highlight_position = None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if line_number <= len(lines):
            # Get context around the error
            context_range = 2
            start_line = max(0, line_number - context_range - 1)
            end_line = min(len(lines), line_number + context_range)
            
            for i in range(start_line, end_line):
                context_lines.append(lines[i].rstrip())
            
            source_line = lines[line_number - 1].rstrip()
            
            # Try to find highlight position for specific error types
            if isinstance(exception, SyntaxError) and hasattr(exception, 'offset') and exception.offset:
                highlight_position = exception.offset - 1
            elif isinstance(exception, NameError):
                # Extract undefined name from error message
                match = re.search(r"name '([^']+)' is not defined", str(exception))
                if match:
                    undefined_name = match.group(1)
                    pos = source_line.find(undefined_name)
                    if pos != -1:
                        highlight_position = pos
            else:
                # Look for strings enclosed in single quotes in the error message
                quoted_matches = re.findall(r"'([^']+)'", str(exception))
                for quoted_string in quoted_matches:
                    if quoted_string in source_line:
                        highlight_position = source_line.find(quoted_string)
                        break
                        
    except (IOError, OSError, IndexError):
        # Fallback if we can't read the file
        context_lines = [f"<Could not read source from {filename}>"]
        source_line = "<unavailable>"
    
    return ErrorContext(
        error_type=exc_type.__name__,
        error_message=str(exc_value),
        filename=filename,
        line_number=line_number,
        source_line=source_line,
        context_lines=context_lines,
        highlight_position=highlight_position,
        module_name=module_name,
        operation=operation
    )


def create_detailed_exception(exception: Exception,
                            operation: str = None,
                            module_name: str = None,
                            message: str = None) -> DetailedError:
    """
    Create a DetailedError from an exception with structured context.
    
    Args:
        exception: The original exception
        operation: What operation was being performed
        module_name: Module being processed
        message: Custom error message
        
    Returns:
        DetailedError with structured context
    """
    context = analyze_exception(exception, operation, module_name)
    
    if message is None:
        if operation and module_name:
            message = f"Failed to {operation} module '{module_name}'"
        elif operation:
            message = f"Failed to {operation}"
        else:
            message = f"Operation failed: {exception}"
    
    return DetailedError(
        message=message,
        context=context,
        original_exception=exception
    )


def log_detailed_error(exception: Exception,
                      operation: str = None,
                      module_name: str = None,
                      message: str = None,
                      logger: logging.Logger = None) -> DetailedError:
    """
    Create and log a detailed error.
    
    Args:
        exception: The original exception
        operation: What operation was being performed
        module_name: Module being processed
        message: Custom error message
        logger: Logger to use (defaults to root logger)
        
    Returns:
        DetailedError with structured context
    """
    detailed_error = create_detailed_exception(exception, operation, module_name, message)
    
    if logger is None:
        logger = logging.getLogger()
    
    logger.error(detailed_error.format_detailed_message())
    
    return detailed_error