
import os
import shutil
import subprocess
import platform
from typing import NamedTuple, Tuple

from nicegui import ui

def generate_pin_uuid(pin_direction: str, node_id: str, pin_id: str) -> str:
    """
    Generate a unique pin identifier for UI and connection systems.

    Args:
        pin_direction: 'inlet' or 'outlet'
        node_id: The node's unique identifier
        pin_id: The inlet/outlet identifier within the node

    Returns:
        Unique pin identifier in format: {direction}__{node_id}__{pin_id}

    Example:
        generate_pin_id('inlet', 'node_abc123', 'temperature') 
        -> 'inlet__node_abc123__temperature'
    """
    if pin_direction not in ('inlet', 'outlet'):
        raise ValueError(f"Invalid pin direction: {pin_direction}."
                         f" Must be 'inlet' or 'outlet'")

    return f"{pin_direction}__{node_id}__{pin_id}"


def parse_pin_uuid(pin_id: str) -> Tuple[str, str, str]:
    """
    Parse a pin identifier back into its components.

    Args:
        pin_id: Pin identifier in format {direction}__{node_id}__{pin_id}

    Returns:
        Tuple of (direction, node_id, pin_id)

    Raises:
        ValueError: If pin_id format is invalid
    """
    parts = pin_id.split('__')
    if len(parts) != 3:
        raise ValueError(f"Invalid pin ID format: {pin_id}")

    direction, node_id, pin_id_part = parts[0], parts[1], parts[2]

    if direction not in ('inlet', 'outlet'):
        raise ValueError(f"Invalid pin direction in ID: {direction}")

    return direction, node_id, pin_id_part


def generate_connection_uuid(
        outlet_node_id: str, 
        outlet_pin_id: str, 
        inlet_node_id: str, 
        inlet_pin_id: str) -> str:
    """
    Generate a unique connection identifier for UI and graph systems.

    This uses Format 2: connection__outlet__node_id__pin_id__inlet__node_id__pin_id

    Args:
        outlet_node_id: The source node's unique identifier
        outlet_pin_id: The source pin's identifier within the node
        inlet_node_id: The destination node's unique identifier  
        inlet_pin_id: The destination pin's identifier within the node

    Returns:
        Unique connection identifier

    Example:
        generate_connection_uuid('node_123', 'output', 'node_456', 'input')
        -> 'connection__outlet__node_123__output__inlet__node_456__input'
    """
    outlet_uuid = generate_pin_uuid('outlet', outlet_node_id, outlet_pin_id)
    inlet_uuid = generate_pin_uuid('inlet', inlet_node_id, inlet_pin_id)
    return f"connection__{outlet_uuid}__{inlet_uuid}"

class ConnectionComponents(NamedTuple):
    """Components of a parsed connection ID."""
    outlet_node_id: str
    outlet_pin_id: str
    inlet_node_id: str
    inlet_pin_id: str


def parse_connection_uuid(connection_uuid: str) -> ConnectionComponents:
    """
    Parse a connection identifier back into its components.

    Args:
        connection_uuid: Connection ID in Format 2

    Returns:
        ConnectionComponents with outlet_node_id, outlet_pin_id, inlet_node_id, inlet_pin_id

    Raises:
        ValueError: If connection_uuid format is invalid

    Example:
        parse_connection_uuid('connection__outlet__node_123__output__inlet__node_456__input')
        -> ConnectionComponents(outlet_node_id='node_123', outlet_pin_id='output',
                               inlet_node_id='node_456', inlet_pin_id='input')
    """
    parts = connection_uuid.split('__')
    if len(parts) != 7:
        raise ValueError(f"Invalid connection ID format: {connection_uuid}. "
                         f"Expected 7 parts, got {len(parts)}")

    if parts[0] != 'connection':
        raise ValueError(f"Connection ID must start with 'connection', got: {parts[0]}")
    if parts[1] != 'outlet':
        raise ValueError(f"Expected 'outlet' at position 1, got: {parts[1]}")
    if parts[4] != 'inlet':
        raise ValueError(f"Expected 'inlet' at position 4, got: {parts[4]}")

    return ConnectionComponents(
        outlet_node_id=parts[2],
        outlet_pin_id=parts[3],
        inlet_node_id=parts[5],
        inlet_pin_id=parts[6]
    )


def _open_file_in_editor(filepath: str, line_number: int = None):
    """Open a file in the user's preferred editor with fallback options"""
    if not os.path.exists(filepath):
        ui.notify(f'File not found: {filepath}', type='negative')
        return

    system = platform.system()
    success = False

    # List of editors to try in order
    editors_to_try = []

    if system == 'Darwin':  # macOS
        editors_to_try = [
            (['code', '--goto', f'{filepath}:{line_number or 1}'], 'VS Code'),
            (['open', '-a', 'Visual Studio Code', filepath], 'VS Code'),
            (['open', '-a', 'PyCharm', filepath], 'PyCharm'),
            (['open', '-a', 'Sublime Text', filepath], 'Sublime Text'),
            (['open', '-t', filepath], 'TextEdit'),
            (['open', filepath], 'Default app'),
        ]
    elif system == 'Windows':
        editors_to_try = [
            (['code', '--goto', f'{filepath}:{line_number or 1}'], 'VS Code'),
            (['notepad++', f'-n{line_number or 1}', filepath], 'Notepad++'),
            (['notepad', filepath], 'Notepad'),
            (['start', '', filepath], 'Default app'),
        ]
    else:  # Linux
        editors_to_try = [
            (['code', '--goto', f'{filepath}:{line_number or 1}'], 'VS Code'),
            (['gedit', f'+{line_number or 1}', filepath], 'gedit'),
            (['kate', '-l', str(line_number or 1), filepath], 'Kate'),
            (['xdg-open', filepath], 'Default app'),
        ]

    # Try each editor until one works
    for cmd, editor_name in editors_to_try:
        try:
            # Check if the command exists (except for 'open' and 'start' which are built-in)
            if cmd[0] not in ['open', 'start', 'xdg-open']:
                if not shutil.which(cmd[0]):
                    continue

            # Try to run the command
            if system == 'Windows' and cmd[0] == 'start':
                subprocess.Popen(cmd, shell=True)
            else:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            ui.notify(f'Opening in {editor_name}...', type='positive')
            success = True
            break
        except (subprocess.CalledProcessError, FileNotFoundError, OSError):
            continue

    if not success:
        # Last resort: show the file path and let user open manually
        ui.notify(
            f'Could not open file automatically. Path copied to clipboard: {filepath}',
            type='warning',
            position='top'
        )
        ui.run_javascript(f'navigator.clipboard.writeText({filepath!r})')
