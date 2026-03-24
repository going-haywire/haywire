import os
import shutil
import subprocess
import platform
from typing import NamedTuple

from nicegui import ui


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

    This uses Format 2: edge::outlet_pin_id@outlet_node_id>>inlet_node_id@inlet_pin_id

    Args:
        outlet_node_id: The source node's unique identifier
        outlet_pin_id: The source pin's identifier within the node
        inlet_node_id: The destination node's unique identifier
        inlet_pin_id: The destination pin's identifier within the node

    Returns:
        Unique edge identifier

    Example:
        generate_edge_id('node_123', 'output', 'node_456', 'input')
        -> 'edge::output@node_123>>input@node_456'
    """
    outlet_uuid = generate_pin_uuid(outlet_node_id, outlet_pin_id)
    inlet_uuid = generate_pin_uuid(inlet_node_id, inlet_pin_id)
    return f"edge::{outlet_uuid}>>{inlet_uuid}"


class EdgeComponents(NamedTuple):
    """Components of a parsed edge ID."""

    outlet_node_id: str
    outlet_pin_id: str
    inlet_node_id: str
    inlet_pin_id: str


def parse_edge_id(edge_id: str) -> EdgeComponents:
    """
    Parse an edge identifier back into its components.

    Args:
        edge_id: Edge ID in format edge::outlet_node_id__outlet_pin_id>>inlet_node_id__inlet_pin_id

    Returns:
        EdgeComponents with outlet_node_id, outlet_pin_id, inlet_node_id, inlet_pin_id

    Raises:
        ValueError: If edge_id format is invalid

    Example:
        parse_edge_id('edge::output@node_123>>input@node_456')
        -> EdgeComponents(outlet_node_id='node_123', outlet_pin_id='output',
                               inlet_node_id='node_456', inlet_pin_id='input')
    """
    # Split by :: to get prefix and the rest
    if "::" not in edge_id:
        raise ValueError(
            f"Invalid connection ID format: {edge_id}. "
            f"Expected format: edge::outlet_pin_id@outlet_node_id>>inlet_node_id@inlet_pin_id"
        )

    prefix, rest = edge_id.split("::", 1)

    if prefix != "edge":
        raise ValueError(f"Edge ID must start with 'edge', got: {prefix}")

    # Split by >> to get outlet and inlet parts
    if ">>" not in rest:
        raise ValueError(
            f"Invalid edge ID format: {edge_id}. Expected '>>' separator between outlet_uuid and inlet_uuid"
        )

    outlet_part, inlet_part = rest.split(">>", 1)

    # Parse outlet part (node_id__pin_id)
    outlet_parts = outlet_part.split("@")
    if len(outlet_parts) != 2:
        raise ValueError(f"Invalid outlet format in edge ID: {outlet_part}. Expected pin_id@node_id")
    outlet_pin_id, outlet_node_id = outlet_parts

    # Parse inlet part (node_id__pin_id)
    inlet_parts = inlet_part.split("@")
    if len(inlet_parts) != 2:
        raise ValueError(f"Invalid inlet format in edge ID: {inlet_part}. Expected pin_id@node_id")
    inlet_pin_id, inlet_node_id = inlet_parts

    return EdgeComponents(
        outlet_node_id=outlet_node_id,
        outlet_pin_id=outlet_pin_id,
        inlet_node_id=inlet_node_id,
        inlet_pin_id=inlet_pin_id,
    )


def _open_file_in_editor(filepath: str, line_number: int = None):
    """Open a file in the user's preferred editor with fallback options"""
    if not os.path.exists(filepath):
        ui.notify(f"File not found: {filepath}", type="negative")
        return

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
