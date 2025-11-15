from haywire.core.errors.haywire_exception import HaywireException


import inspect
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PrimitiveTypeDefinitionError(HaywireException, TypeError):
    """
    Raised when a primitive type is defined incorrectly.

    This exception knows it should point to the CLASS DEFINITION in user code,
    not the validation code in base.py or decorators.py.

    Attributes:
        cls: The class object (required - used to extract all error information)
        extra_fields: List of extra field names (if validation failed due to extra fields)
        missing_value: True if validation failed due to missing 'value' annotation
    """
    cls: Optional[type] = None
    extra_fields: Optional[List[str]] = None
    missing_value: bool = False

    def __post_init__(self):
        import inspect

        # Extract all information from the class object
        cls_name = ""
        cls_module = ""
        cls_filename = None
        cls_line_number = None

        if self.cls is not None:
            cls_name = self.cls.__name__
            cls_module = self.cls.__module__

            try:
                cls_filename = inspect.getfile(self.cls)
                source_lines, start_line_number = inspect.getsourcelines(self.cls)

                # Find the actual 'class' keyword line (not decorator lines)
                cls_line_number = start_line_number
                for i, line in enumerate(source_lines):
                    stripped = line.strip()
                    if stripped.startswith('class '):
                        cls_line_number = start_line_number + i
                        break
            except:
                pass  # Keep as None if extraction fails

        # Build message and set rendering hints
        if self.extra_fields:
            self.message = (
                f"\n\n"
                f"{'='*70}\n"
                f"❌ Primitive Type Definition Error\n"
                f"{'='*70}\n"
                f"Class:    {cls_name}\n"
                f"Module:   {cls_module}\n"
            )
            if cls_filename and cls_line_number:
                self.message += f"Location: {cls_filename}:{cls_line_number}\n"

            self.message += (
                f"{'='*70}\n\n"
                f"Primitive types can only define a 'value' field.\n\n"
                f"Found extra fields: {', '.join(sorted(self.extra_fields))}\n"
            )

            self.suggestions = [
                f"Remove these fields: {', '.join(sorted(self.extra_fields))}",
                "Use @compound_type if you need multiple fields"
            ]
            self.highlight_text = self.extra_fields[0] if self.extra_fields else None

        elif self.missing_value:
            self.message = (
                f"\n\n"
                f"{'='*70}\n"
                f"❌ Primitive Type Definition Error\n"
                f"{'='*70}\n"
                f"Class:    {cls_name}\n"
                f"Module:   {cls_module}\n"
            )
            if cls_filename and cls_line_number:
                self.message += f"Location: {cls_filename}:{cls_line_number}\n"

            self.message += (
                f"{'='*70}\n\n"
                f"Primitive types must have a 'value' annotation.\n"
            )

            self.suggestions = [
                "Add: value: YourType",
                f"Example: value: float for {cls_name}(PrimitiveType[float])"
            ]
            self.highlight_text = "value"

        else:
            self.message = f"Invalid primitive type definition: {cls_name}"
            self.suggestions = []

        # Set rendering hints to hide internal implementation
        self.error_filename = cls_filename
        self.error_line_number = cls_line_number
        self.error_category = "Type Definition Error"
        self.show_full_traceback = False  # Hide __init_subclass__ and decorator internals
        self.skip_frame_functions = ['__init_subclass__', 'decorator', '_raise_primitive_type_error']
        self.skip_frame_files = ['base.py', 'decorators.py']
        self.skip_stacktrace_steps = 1  # Skip the first traceback frame (error location already shown in source box)

        # Call parent's __post_init__
        super().__post_init__()