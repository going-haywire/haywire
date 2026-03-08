# haywire/core/node/ui_state.py
"""
Node UI state - runtime visual state (position, dimensions).
"""

from dataclasses import dataclass, asdict


@dataclass
class NodeUIState:
    """
    Runtime UI state for a node instance.
    
    This contains positional and dimensional data that is:
    - Serialized with the graph (not the node class)
    - Changed frequently during editing
    - Not user-configurable via settings panel
    
    For user-configurable UI options (colors, visibility toggles),
    use self.settings instead.
    """
    
    # Position
    posX: float = 0.0
    posY: float = 0.0
    
    # Dimensions (0 = auto-calculated)
    width: float = 0.0
    height: float = 0.0
    
    # Minimum dimensions (-1 = use default)
    width_min: float = -1.0
    height_min: float = -1.0
    
    def set_position(self, pos: tuple[float, float]) -> None:
        """Set node position."""
        self.posX = pos[0]
        self.posY = pos[1]
    
    def get_position(self) -> tuple[float, float]:
        """Get node position."""
        return (self.posX, self.posY)
    
    def set_size(self, width: float, height: float) -> None:
        """Set node dimensions."""
        self.width = width
        self.height = height
    
    def get_size(self) -> tuple[float, float]:
        """Get node dimensions."""
        return (self.width, self.height)
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NodeUIState':
        """Deserialize from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class NodeUI:
    """
    Container for node UI concerns.
    
    Provides a clean namespace for UI operations:
    - self.ui.state - Position, dimensions (serialized)
    - self.ui.collapse() / expand() - Convenience methods
    
    Note: Visual settings like colors and visibility toggles
    are accessed via self.settings (e.g., self.settings.collapsed)
    """

    def __init__(self, node: 'BaseNode'):
        self._node = node
        self.state = NodeUIState()

    # =========================================================================
    # Position & Dimensions
    # =========================================================================

    def set_position(self, pos: tuple[float, float]) -> None:
        """Set node position."""
        self.state.set_position(pos)

    def get_position(self) -> tuple[float, float]:
        """Get node position."""
        return self.state.get_position()

    @property
    def position(self) -> tuple[float, float]:
        """Node position as (x, y) tuple."""
        return self.state.get_position()

    @position.setter
    def position(self, value: tuple[float, float]) -> None:
        self.state.set_position(value)

    # =========================================================================
    # Collapse / Expand (delegates to settings)
    # =========================================================================

    def collapse(self) -> None:
        """Collapse the node in the editor."""
        self._node.settings.collapsed = True

    def expand(self) -> None:
        """Expand the node in the editor."""
        self._node.settings.collapsed = False

    @property
    def is_collapsed(self) -> bool:
        """Whether the node is collapsed."""
        return self._node.settings.get('collapsed', False)

    # =========================================================================
    # Mute (delegates to settings)
    # =========================================================================

    def mute(self) -> None:
        """Mute the node (skip during execution)."""
        self._node.settings.muted = True

    def unmute(self) -> None:
        """Unmute the node."""
        self._node.settings.muted = False

    @property
    def is_muted(self) -> bool:
        """Whether the node is muted."""
        return self._node.settings.get('muted', False)

    # =========================================================================
    # Pin (delegates to settings)
    # =========================================================================

    def pin(self) -> None:
        """Pin the node (prevent auto-layout movement)."""
        self._node.settings.pinned = True

    def unpin(self) -> None:
        """Unpin the node."""
        self._node.settings.pinned = False

    @property
    def is_pinned(self) -> bool:
        """Whether the node is pinned."""
        return self._node.settings.get('pinned', False)
    
    # =========================================================================
    # Serialization
    # =========================================================================
    
    def to_dict(self) -> dict:
        """Serialize UI state."""
        return {
            'state': self.state.to_dict()
        }
    
    def from_dict(self, data: dict) -> None:
        """Restore UI state."""
        if 'state' in data:
            self.state = NodeUIState.from_dict(data['state'])