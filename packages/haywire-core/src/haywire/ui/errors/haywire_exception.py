import os
from typing import Any
from nicegui import ui

from haywire.ui import elements as hui
from haywire.core.errors.haywire_exception import HaywireException
from haywire.ui.utils import _open_file_in_editor


def _create_detail_row(
    label: str,
    value: str,
    icon: str,
    multiline: bool = False,
    monospace: bool = False,
    file_path: str = None,
    line_number: int = None,
):
    """Helper to create a consistent detail row with optional file open button"""
    classes = "text-sm " + ("font-mono" if monospace else "")

    with ui.row().classes("items-start gap-2 w-full"):
        ui.icon(icon, color="gray").classes("text-sm mt-0.5")
        ui.label(f"{label}:").classes("font-bold text-sm hw-text-muted min-w-20")
        if multiline and "\n" in value:
            with ui.column().classes("flex-grow"):
                lines = value.split("\n")
                ui.label(lines[0]).classes(classes)
                for line in lines[1:]:
                    ui.label(line).classes(classes + " pl-4")
        else:
            with ui.row().classes("items-center gap-2 flex-grow"):
                ui.label(value).classes(classes)
                # Add "Open in Editor" button if file_path is provided
                if file_path and os.path.exists(file_path):
                    with ui.button_group():
                        ui.button(
                            icon="open_in_new", on_click=lambda: _open_file_in_editor(file_path, line_number)
                        ).props("flat dense size=sm").tooltip("Open in editor").classes("ml-2")
                        # Also add a copy path button
                        ui.button(
                            icon=hui.icon.copy,
                            on_click=lambda p=file_path: ui.run_javascript(
                                f"navigator.clipboard.writeText({p!r})"
                            ),
                        ).props("flat dense size=sm").tooltip("Copy file path")


def render_error_details(error: HaywireException, parent_container=None) -> Any:
    """
    Render detailed error information for a HaywireException.

    This is a reusable function that can be called from ErrorWidget or any other UI component.
    Can be used to render error details on-demand (lazy rendering).

    Args:
        error: The HaywireException to render
        parent_container: Optional parent container to render into. If None, creates a new column.

    Returns:
        The container with rendered error details
    """
    if parent_container is None:
        parent_container = ui.column().classes("gap-4 p-4")

    with parent_container:
        # Header
        with ui.row().classes("items-center gap-2 pb-3 border-b"):
            ui.icon(error.get_severity_icon(), color=error.get_severity_color()).classes("text-3xl")
            ui.label(f"{error.category}").classes("text-xl font-bold hw-text-body")
            ui.button(
                icon=hui.icon.copy,
                on_click=lambda text=error.format_detailed(): ui.run_javascript(
                    f"navigator.clipboard.writeText({text!r})"
                ),
            ).props("flat dense").classes("ml-2").tooltip("Copy detailed error to clipboard")

        # Show the actual error message right above the code
        if error.original_exception:
            exc_type_name = type(error.original_exception).__name__
            exc_message = str(error.original_exception)
            with ui.card().classes("w-full bg-red-100 border-l-4 border-red-500 mb-2"):
                with ui.row().classes("items-start gap-2 p-2"):
                    _create_detail_row(exc_type_name, exc_message, "error")

        if error.message:
            with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
                with ui.row().classes("items-start gap-2 p-2"):
                    _create_detail_row("Message", error.message, "build")

        # Source code section
        if error.has_source_location():
            with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
                with ui.column().classes("gap-2"):
                    # Source code with context
                    if error.source_context:
                        with ui.column().classes("mt-2"):
                            code_lines = [line_content for _, line_content in error.source_context]
                            first_line_num = error.source_context[0][0] if error.source_context else 1

                            # Detect language from filename extension
                            language = "python"
                            if error.filename:
                                ext = os.path.splitext(error.filename)[1].lower()
                                language_map = {
                                    ".py": "python",
                                    ".js": "javascript",
                                    ".ts": "typescript",
                                    ".html": "html",
                                    ".css": "css",
                                    ".json": "json",
                                    ".md": "markdown",
                                    ".yml": "yaml",
                                    ".yaml": "yaml",
                                }
                                language = language_map.get(ext, "python")

                            # Build the code string with line numbers
                            max_line_num = first_line_num + len(code_lines) - 1
                            line_num_width = len(str(max_line_num))

                            numbered_lines = []
                            for i, line in enumerate(code_lines):
                                line_num = first_line_num + i
                                # Right-align line numbers and add separator
                                if error.line_number and line_num == error.line_number:
                                    # Highlight the error line
                                    if error.original_exception:
                                        exc_type_name = type(error.original_exception).__name__
                                        exc_message = str(error.original_exception)
                                        numbered_lines.append(f"{'':>{line_num_width}} ")
                                        numbered_lines.append(
                                            f"{'':>{line_num_width}} -> {exc_type_name}: {exc_message} "
                                        )
                                    numbered_lines.append(f"{'':>{line_num_width}} ")
                                    numbered_lines.append(f"{line_num:>{line_num_width}} >> {line}  <<")
                                    numbered_lines.append(f"{'':>{line_num_width}} ")
                                else:
                                    numbered_lines.append(f"{line_num:>{line_num_width}}  : {line}")

                            code_with_numbers = "\n".join(numbered_lines)

                            # Use ui.code() for syntax highlighting
                            ui.code(code_with_numbers, language=language).classes("w-full")

                            # File path with "Open in Editor" button
                            file_display = error.filename
                            if error.library_identity and error.library_identity.folder_path:
                                try:
                                    rel_path = os.path.relpath(
                                        error.filename, error.library_identity.folder_path
                                    )
                                    if not rel_path.startswith(".."):
                                        file_display = f"./{rel_path}"
                                except ValueError:
                                    pass

                            _create_detail_row(
                                "File",
                                file_display,
                                "description",
                                monospace=True,
                                file_path=error.filename,
                                line_number=error.line_number,
                            )

                            if error.line_number:
                                _create_detail_row("Line", str(error.line_number), "tag")

        # Suggestions section
        if error.has_suggestions():
            with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
                for suggestion in error.suggestions:
                    with ui.row().classes("items-start gap-2"):
                        _create_detail_row("Suggestion", suggestion, "lightbulb")

        # Traceback section (filter interesting frames)
        if error.traceback_frames:
            interesting_frames = [f for f in error.traceback_frames if error.is_interesting_frame(f)]

            if interesting_frames:
                with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
                    with ui.column().classes("gap-2"):
                        ui.label("🔍 Traceback").classes("font-bold hw-text-muted")

                        with ui.column().classes("gap-3 pl-4"):
                            for frame in interesting_frames:
                                filename = frame["file"]
                                line_number = frame["line"]
                                function_name = frame["function"]
                                source_line = frame["code"]

                                base_filename = os.path.basename(filename)

                                with ui.column().classes("gap-1 border-l-2 border-blue-300 pl-3 py-1"):
                                    # Location with Open button
                                    with ui.row().classes("items-center gap-2"):
                                        ui.icon("arrow_right", color="blue").classes("text-sm")
                                        ui.label(f"{base_filename}").classes("font-bold text-sm")
                                        ui.label(f"in {function_name}").classes("text-sm hw-text-muted")
                                        # Add open button for each frame
                                        if os.path.exists(filename):
                                            ui.button(
                                                icon="open_in_new",
                                                on_click=lambda f=filename, ln=line_number: (
                                                    _open_file_in_editor(f, ln)
                                                ),
                                            ).props("flat dense size=xs").tooltip("Open in editor")

                                    # File path (truncated if too long)
                                    display_path = filename
                                    if len(display_path) > 60:
                                        display_path = "..." + display_path[-57:]
                                    ui.label(f'File "{display_path}"').classes(
                                        "text-xs hw-text-dim font-mono"
                                    )

                                    # Source line
                                    if source_line.strip():
                                        with (
                                            ui.row()
                                            .classes("items-start gap-2 mt-1 rounded p-2")
                                            .style("background: var(--hw-bg-surface);")
                                        ):
                                            ui.label(f"line {line_number}:").classes(
                                                "text-xs hw-text-accent font-mono"
                                            )
                                            ui.label(source_line.strip()).classes("text-xs font-mono")

        # Main error info card
        with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
            with ui.column().classes("gap-2"):
                ui.label("📦 Error Information").classes("font-bold hw-text-muted")

                if error.message:
                    _create_detail_row("Message", error.message, "build")

                if error.operation:
                    _create_detail_row("Operation", error.operation, "build")

                if error.severity:
                    _create_detail_row("Severity", error.severity.value.upper(), error.get_severity_icon())

                if error.context_type:
                    _create_detail_row("Context", error.context_type, "code")

                if error.highlighted_item:
                    _create_detail_row("Item", error.highlighted_item, "label")

        # Library and context info
        if error.library_identity or error.module_name or error.registry_key:
            with ui.card().classes("w-full border-l-4 border-black-500 mb-2"):
                with ui.column().classes("gap-2"):
                    ui.label("📦 Context Information").classes("font-bold hw-text-muted")

                    if error.library_identity:
                        _create_detail_row("Library", error.library_identity.label, "folder")
                        if error.library_identity.folder_path:
                            _create_detail_row(
                                "Path", error.library_identity.folder_path, "folder_open", monospace=True
                            )

                    if error.registry_key:
                        _create_detail_row("Registry", error.registry_key, "key")

                    if error.module_name:
                        _create_detail_row("Module", error.module_name, "article")

    return parent_container
