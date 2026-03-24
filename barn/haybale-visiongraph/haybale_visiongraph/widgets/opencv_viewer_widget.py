"""
OpenCV Viewer Widget - Displays numpy arrays as streaming video in nodes
"""

from typing import Any, Optional, TYPE_CHECKING
from haybale_visiongraph.types.frame_type import FRAME
import numpy as np
from nicegui import ui

from haywire.ui.widget.interface import IWidget
from haywire.ui.widget.decorator import widget

from haybale_visiongraph.widgets.components.streaming_viewer import StreamingViewer

if TYPE_CHECKING:
    from haywire.core.types import DataPort


@widget(
    description="Streaming video viewer for numpy arrays using custom StreamingViewer",
    compatible_types=[FRAME],  # Will be FRAME type
)
class OpencvViewerWidget(IWidget):
    """
    Widget for displaying numpy arrays as streaming video.

    Uses a custom StreamingViewer component for efficient MJPEG streaming.
    Automatically streams frame updates when the port value changes.

    Config options (via ``OpencvViewerWidget.config(properties={...})``):

    - ``quality`` (int): JPEG compression quality (0–100, default: ``80``).
    - ``width`` (str): CSS width of the viewer (default: ``'100%'``).
    - ``height`` (str): CSS height of the viewer (default: ``'auto'``).
    - ``frame_queue_size`` (int): Internal frame buffer size (default: ``1``).
    - ``block_on_full`` (bool): Block the producer when the queue is full (default: ``False``).

    Usage:
        from haybale_visiongraph.widgets.opencv_viewer_widget import OpencvViewerWidget

        self.add(FRAME.as_inlet(
            'preview',
            label='Preview',
            widget=OpencvViewerWidget.config(properties={
                'quality': 80,
                'width': '100%',
                'height': '300px'
            })
        ))
    """

    def __init__(self, port: "DataPort"):
        """
        Initialize the OpenCV viewer widget.

        Args:
            port: DataPort containing FRAME data
        """
        self.port = port
        self.port_id: str = port.id
        self.config: dict = (
            port.widget_config if hasattr(port, "widget_config") and port.widget_config else {}
        )

        # UI elements
        self.ui_element: Optional[Any] = None
        self.streaming_viewer: Optional[StreamingViewer] = None

        # Callback for model changes
        self._model_changed_callback: Optional[Any] = None

    def render(self) -> Any:
        """
        Render the streaming viewer widget.

        Returns:
            Container with the streaming viewer
        """
        if self.ui_element is None:
            # Extract configuration
            props = self.config.get("properties", {})
            quality = props.get("quality", 80)
            width = props.get("width", "100%")
            height = props.get("height", "auto")
            frame_queue_size = props.get("frame_queue_size", 1)
            block_on_full = props.get("block_on_full", False)

            # Create container with viewer
            with ui.card().classes("w-full") as container:
                self.streaming_viewer = StreamingViewer(
                    quality=quality, frame_queue_size=frame_queue_size, block_on_full=block_on_full
                ).style(f"width: {width}; height: {height};")

            self.ui_element = container

            # Setup binding to port changes
            self._setup_binding()

            # Initial sync: try to display current frame if available
            self._sync_frame_to_viewer()

            # Cleanup on disconnect
            if hasattr(self.ui_element, "client"):
                self.ui_element.client.on_disconnect(lambda: self.cleanup())

        return self.ui_element

    def _setup_binding(self) -> None:
        """Setup binding to listen for frame updates from the port"""
        # Subscribe to port value changes
        self._model_changed_callback = lambda _: self._sync_frame_to_viewer()
        self.port._data.on_changed += self._model_changed_callback

    def _sync_frame_to_viewer(self) -> None:
        """
        Synchronize the port's FRAME value to the streaming viewer.

        Extracts the numpy array from the FRAME object and streams it
        to the viewer component.
        """
        if self.streaming_viewer is None:
            return

        # Don't try to stream if viewer is shutting down
        if not self.streaming_viewer._is_running:
            return

        try:
            # Get the frame from the port
            frame = self.port.get_value()

            if frame is None:
                return

            # Extract numpy array from FRAME object
            # Handle both FRAME objects and raw numpy arrays
            if hasattr(frame, "data"):
                # It's a FRAME object
                frame_data = frame.data
            elif isinstance(frame, np.ndarray):
                # It's already a numpy array
                frame_data = frame
            else:
                # Unknown type
                return

            # Validate the frame data
            if frame_data is None or not isinstance(frame_data, np.ndarray):
                return

            if frame_data.size == 0:
                return

            # Stream the frame to the viewer
            self.streaming_viewer.stream(frame_data)

        except Exception as e:
            # Silently fail - don't crash the UI on streaming errors
            # Only log if viewer is still supposed to be running
            if self.streaming_viewer and self.streaming_viewer._is_running:
                print(f"[OpencvViewerWidget] Error streaming frame: {e}")

    def cleanup(self) -> None:
        """Clean up resources and subscriptions"""
        # Clean up the streaming viewer
        if self.streaming_viewer:
            try:
                self.streaming_viewer.cleanup()
            except Exception as e:
                print(f"[OpencvViewerWidget] Viewer cleanup warning: {e}")

        # Unsubscribe from port changes
        if self._model_changed_callback and self.port:
            try:
                self.port._data.on_changed -= self._model_changed_callback
            except Exception as e:
                print(f"[OpencvViewerWidget] Port cleanup warning: {e}")

        # Clear references
        self._model_changed_callback = None
        self.streaming_viewer = None
        self.ui_element = None
        self.port = None
