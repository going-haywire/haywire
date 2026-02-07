"""
Webcam Frame Event Node - Receives frame callbacks and provides frame data
"""

from typing import Optional
from haybale_visiongraph.types.frame_type import FRAME
import numpy as np

from haywire.core.execution.event_source import CallbackEvent
from haywire.core.execution.execution_context import ExecutionContext
from haywire.core.node.decorator import node
from haywire.core.node.base import BaseNode
from haywire.core.node.behavior import NodeType


@node(
    label='Webcam Frame Info Display',
    description='Displays information about webcam frames',
    menu='vision/info',
    search_tags=['webcam', 'frame', 'camera', 'event', 'video'],
    node_type=NodeType.CONTROL,
)
class WebcamFrameInfoDisplayNode(BaseNode):
    """
    Event node that receives webcam frame callbacks.
    Provides the frame data and metadata for processing.
    
    Config:
        callback_name: Name of the callback to listen for
    
    Outputs:
        frame_ready: Control flow when frame arrives
        frame: Frame data with metadata (FRAME type)
        raw_data: Raw numpy array (for convenience)
        frame_number: Sequential frame number
        timestamp: Time since stream start
        width: Frame width in pixels
        height: Frame height in pixels
    """
    
    def init(self):
        from haybale_core.types.specs import EXEC, STRING, INT, FLOAT
        from haybale_core.widgets.basic_widgets import TextWidget
        from ..types.frame_type import FRAME
                
        # Control output
        self.add(EXEC.as_inlet('execute', label='Analyse Frame'))

        # Control output
        self.add(EXEC.as_outlet('frame_ready', label='Frame Ready'))
        
        # Frame data output
        self.add(FRAME.as_inlet('frame', label='Frame'))
        
        # Convenience outputs for common data
        # Note: For raw_data, we'll use a generic outlet since we don't have
        # a specific numpy array type defined yet
        self.add(FLOAT.as_outlet('timestamp', label='Timestamp (s)'))
        self.add(INT.as_outlet('frame_number', label='Frame Number'))
        self.add(INT.as_outlet('width', label='Width'))
        self.add(INT.as_outlet('height', label='Height'))
    
    
    def worker(self, context: ExecutionContext, frame: FRAME) -> Optional[str]:
        
        # Extract frame data from payload
        frame_data = frame.data
        
        if frame_data is None:
            return None
                
        # Output all data
        self.out('timestamp', frame.timestamp)
        self.out('frame_number', frame.frame_number)
        self.out('width', frame.width)
        self.out('height', frame.height)
        
        # Trigger downstream execution
        return 'frame_ready'