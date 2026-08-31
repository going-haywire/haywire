import os
import shlex
import shutil
import logging
import subprocess
import platform
from typing import Callable

from nicegui import ui

logger = logging.getLogger(__name__)


def anchor_cleanup_to_element(element: "ui.element", callback: Callable[[], None]) -> None:
    """Run *callback* when *element* is removed from the DOM.

    Wraps NiceGUI's private ``Element._handle_delete``, which fires for every
    element removed by ``content.clear()`` (client.remove_elements) or page
    close. Exceptions from *callback* are swallowed so a failing teardown can't
    block the delete; pass an idempotent callback.
    """
    original_handle_delete = element._handle_delete

    def _handle_delete() -> None:
        try:
            callback()
        except Exception:
            logger.debug("anchor_cleanup_to_element callback failed", exc_info=True)
        original_handle_delete()

    element._handle_delete = _handle_delete  # type: ignore[method-assign]


def generate_pin_uuid(node_id: str, pin_id: str) -> str:
    """
    Generate a unique pin identifier for UI and edge systems.

    Args:
        node_id: The node's unique identifier
        pin_id: The inlet/outlet identifier within the node

    Returns:
        Unique pin identifier in format: {pin_id}@{node_id}

    Example:
        generate_pin_id('node_abc123', 'temperature')
        -> 'temperature@node_abc123'
    """

    return f"{pin_id}@{node_id}"


def generate_edge_uuid(
    outlet_node_id: str, outlet_pin_id: str, inlet_node_id: str, inlet_pin_id: str
) -> str:
    """
    Generate a unique edge identifier for UI and graph systems.

    Format: ``{outlet_node_id}[{outlet_pin_id}]->{inlet_node_id}[{inlet_pin_id}]`` —
    written source-to-sink, matching the direction the data flows.

    Note this deliberately does NOT compose from :func:`generate_pin_uuid`. Pin
    UUIDs are their own DOM-id scheme (``{pin_id}@{node_id}``); edge ids are
    opaque tokens whose only contract is that Python and ``canvas.vue``'s
    ``_buildEdgeID`` produce byte-identical strings. The separator is ``->``
    rather than ``>>`` because ``>>`` is already the port-hierarchy separator
    used by the pin fallback strings (see ``EdgeWrapper.outletPinFallback``).

    The id is used verbatim as an SVG element id, so it must stay free of
    whitespace.

    Args:
        outlet_node_id: The source node's unique identifier
        outlet_pin_id: The source pin's identifier within the node
        inlet_node_id: The destination node's unique identifier
        inlet_pin_id: The destination pin's identifier within the node

    Returns:
        Unique edge identifier

    Example:
        generate_edge_uuid('node_123', 'output', 'node_456', 'input')
        -> 'node_123[output]->node_456[input]'
    """
    return f"{outlet_node_id}[{outlet_pin_id}]->{inlet_node_id}[{inlet_pin_id}]"


def _build_editor_command(template: str, filepath: str, line_number: int | None) -> list[str] | None:
    """Turn an editor-command template into an argv list.

    ``{file}`` and ``{line}`` are substituted (line defaults to 1). A template
    with no ``{file}`` gets the path appended as the final arg. An empty/blank
    template returns None so the caller falls back to its per-OS editor list.
    """
    template = template.strip()
    if not template:
        return None
    line = str(line_number or 1)
    if "{file}" in template:
        rendered = template.replace("{file}", filepath).replace("{line}", line)
        return shlex.split(rendered)
    # No placeholder — append the path.
    return shlex.split(template) + [filepath]


def _open_file_in_editor(filepath: str, line_number: int | None = None):
    """Open a file in the user's preferred editor with fallback options"""
    if not os.path.exists(filepath):
        ui.notify(f"File not found: {filepath}", type="negative")
        return

    # Prefer the user-configured external editor command (framework setting).
    from haywire.core.tooling.settings import ExternalToolsSettings

    configured = _build_editor_command(ExternalToolsSettings().editor_command, filepath, line_number)
    if configured is not None:
        try:
            if configured[0] == "start":  # Windows built-in
                subprocess.Popen(configured, shell=True)
                ui.notify("Opening in external editor…", type="positive")
                return
            elif configured[0] in ("open", "xdg-open") or shutil.which(configured[0]):
                subprocess.Popen(configured, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ui.notify("Opening in external editor…", type="positive")
                return
            # command not found → fall through to the per-OS list
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            pass  # fall through to the per-OS fallback list

    system = platform.system()
    success = False

    # List of editors to try in order
    editors_to_try = []

    if system == "Darwin":  # macOS
        editors_to_try = [
            (["code", "--goto", f"{filepath}:{line_number or 1}"], "VS Code"),
            (["open", "-a", "Visual Studio Code", filepath], "VS Code"),
            (["open", "-a", "PyCharm", filepath], "PyCharm"),
            (["open", "-a", "Sublime Text", filepath], "Sublime Text"),
            (["open", "-t", filepath], "TextEdit"),
            (["open", filepath], "Default app"),
        ]
    elif system == "Windows":
        editors_to_try = [
            (["code", "--goto", f"{filepath}:{line_number or 1}"], "VS Code"),
            (["notepad++", f"-n{line_number or 1}", filepath], "Notepad++"),
            (["notepad", filepath], "Notepad"),
            (["start", "", filepath], "Default app"),
        ]
    else:  # Linux
        editors_to_try = [
            (["code", "--goto", f"{filepath}:{line_number or 1}"], "VS Code"),
            (["gedit", f"+{line_number or 1}", filepath], "gedit"),
            (["kate", "-l", str(line_number or 1), filepath], "Kate"),
            (["xdg-open", filepath], "Default app"),
        ]

    # Try each editor until one works
    for cmd, editor_name in editors_to_try:
        try:
            # Check if the command exists (except for 'open' and 'start' which are built-in)
            if cmd[0] not in ["open", "start", "xdg-open"]:
                if not shutil.which(cmd[0]):
                    continue

            # Try to run the command
            if system == "Windows" and cmd[0] == "start":
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            ui.notify(f"Opening in {editor_name}...", type="positive")
            success = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            continue

    if not success:
        # Last resort: show the file path and let user open manually
        ui.notify(
            f"Could not open file automatically. Path copied to clipboard: {filepath}",
            type="warning",
            position="top",
        )
        ui.run_javascript(f"navigator.clipboard.writeText({filepath!r})")
