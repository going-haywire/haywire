"""
Frame data type for video streams
"""

from dataclasses import dataclass
from typing import Any, Optional
import numpy as np

from haywire.core.data.enums import FlowType
from haywire.core.types.base import BaseType
from haywire.core.types.decorator import type


@type(
    registry_id='frame',
    label='Frame',
    description='Video frame data with metadata',
    flow_type=FlowType.DATA,
    default={
        'data': None,
        'timestamp': 0.0,
        'frame_number': 0,
        'width': 0,
        'height': 0,
        'channels': 0
    },
    color='#9c27b0',
)
@dataclass
class FRAME(BaseType):
    """
    Video frame data type with metadata.
    
    Attributes:
        data: Numpy array containing the frame data (H, W, C)
        timestamp: Time when frame was captured (seconds)
        frame_number: Sequential frame number since stream start
        width: Frame width in pixels
        height: Frame height in pixels
        channels: Number of color channels (typically 3 for BGR/RGB)
    """
    data: Optional[np.ndarray] = None
    timestamp: float = 0.0
    frame_number: int = 0
    width: int = 0
    height: int = 0
    channels: int = 0
    
    def __post_init__(self):
        """Automatically extract dimensions from numpy array if provided"""
        if self.data is not None and isinstance(self.data, np.ndarray):
            if len(self.data.shape) >= 2:
                self.height, self.width = self.data.shape[:2]
                self.channels = self.data.shape[2] if len(self.data.shape) > 2 else 1
    
    def is_valid(self) -> bool:
        """Check if frame contains valid data"""
        return self.data is not None and isinstance(self.data, np.ndarray) and self.data.size > 0
    
    def copy(self) -> 'FRAME':
        """Create a deep copy of the frame"""
        return FRAME(
            data=self.data.copy() if self.data is not None else None,
            timestamp=self.timestamp,
            frame_number=self.frame_number,
            width=self.width,
            height=self.height,
            channels=self.channels
        )