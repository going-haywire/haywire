"""
Core utility functions for Haywire framework.

This module provides commonly used utilities across different parts of the system.
"""

from typing import Tuple


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
