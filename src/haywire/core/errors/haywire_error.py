
from dataclasses import dataclass
from typing import List, Optional

from haywire.core.library.library_identity import LibraryIdentity

@dataclass
class HaywireError:
    """Structured error information"""
    error_type: str
    error_message: str
    filename: str
    line_number: int
    source_line: str
    context_lines: List[str]
    message: str  # High-level error message for the user
    error_category: str = "Error"  # Error category 
    operation: Optional[str] = None  # 'import', 'instantiation', 'syntax_check'
    suggestions: Optional[List[str]] = None  # Actionable suggestions
    library_identity: Optional[LibraryIdentity] = None # Library identity
    module_name: Optional[str] = None 
    registry_key: Optional[str] = None
    highlight_position: Optional[int] = None
    highlight_length: Optional[int] = None
    class_name: Optional[str] = None
    context_info: Optional[List[tuple]] = None  # List of (line_number, line_content) tuples
    traceback_info: Optional[List[tuple]] = None  # List of (filename, line_number, function_name, source_line) tuples
    original_exception: Optional[Exception] = None  # Original exception (if any)

    def format_detailed(self) -> str:
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

