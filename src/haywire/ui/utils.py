
from typing import NamedTuple, Tuple
from nicegui import ui, element

from haywire.core.node.node import BaseNode, NodeErrorInfo

def render_error_info(error_info: NodeErrorInfo) -> element:
    """
    Render error information for a node.

    Args:
        node: The HaywireNode with error information
        
    Returns:
        bool: True if error info was rendered, False if no error info
    """
    with ui.column().classes('items-left p-2 border border-red-500 bg-red-50') as error_column:
        with ui.row():
            ui.icon('error', color='red').classes('text-lg')
            ui.label(error_info.error).classes('text-lg text-red-600')
        ui.label(error_info.error_message).classes('text-sm text-red-600')
        if error_info.note:
            for value in error_info.note:
                ui.label(value).classes('text-sm text-red-600')
        ui.label(error_info.timestamp).classes('text-sm text-red-600')
    return error_column


def generate_pin_id(pin_direction: str, node_id: str, pin_id: str) -> str:
    """
    Generate a unique pin identifier for UI and connection systems.

    Args:
        pin_direction: 'inlet' or 'outlet'
        node_id: The node's unique identifier
        pin_id: The pin's identifier within the node

    Returns:
        Unique pin identifier in format: {direction}__{node_id}__{pin_id}

    Example:
        generate_pin_id('inlet', 'node_abc123', 'temperature') 
        -> 'inlet__node_abc123__temperature'
    """
    if pin_direction not in ('inlet', 'outlet'):
        raise ValueError(f"Invalid pin direction: {pin_direction}. Must be 'inlet' or 'outlet'")

    return f"{pin_direction}__{node_id}__{pin_id}"


def parse_pin_id(pin_id: str) -> Tuple[str, str, str]:
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


def generate_connection_id(outlet_node_id: str, outlet_pin_id: str, inlet_node_id: str, inlet_pin_id: str) -> str:
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
        generate_connection_id('node_123', 'output', 'node_456', 'input')
        -> 'connection__outlet__node_123__output__inlet__node_456__input'
    """
    return f"connection__outlet__{outlet_node_id}__{outlet_pin_id}__inlet__{inlet_node_id}__{inlet_pin_id}"


class ConnectionComponents(NamedTuple):
    """Components of a parsed connection ID."""
    outlet_node_id: str
    outlet_pin_id: str
    inlet_node_id: str
    inlet_pin_id: str


def parse_connection_id(connection_id: str) -> ConnectionComponents:
    """
    Parse a connection identifier back into its components.

    Args:
        connection_id: Connection ID in Format 2

    Returns:
        ConnectionComponents with outlet_node_id, outlet_pin_id, inlet_node_id, inlet_pin_id

    Raises:
        ValueError: If connection_id format is invalid

    Example:
        parse_connection_id('connection__outlet__node_123__output__inlet__node_456__input')
        -> ConnectionComponents(outlet_node_id='node_123', outlet_pin_id='output',
                               inlet_node_id='node_456', inlet_pin_id='input')
    """
    parts = connection_id.split('__')
    if len(parts) != 7:
        raise ValueError(f"Invalid connection ID format: {connection_id}. Expected 7 parts, got {len(parts)}")

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
