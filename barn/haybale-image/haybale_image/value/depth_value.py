"""``DepthValue``: a metric depth map."""

from __future__ import annotations

import numpy as np
from haywire.barn.builtin.carrier import CarrierValue


class DepthValue(CarrierValue):
    """A depth map: one ``uint16`` per pixel, in millimetres.

    A value is immutable and shares its buffer with whoever made it; the caller
    must not write to the buffer afterwards. It is not an image, so turning it into
    something viewable is the job of a node.

    Example::

        depth = DepthValue.from_array(camera.depth_buffer)  # no copy
        depth.array()[120, 160]                             # millimetres at one pixel
        stamped = depth.stamped("camera_timestamp", 1.5, FLOAT)
    """

    __slots__ = ("_array",)

    def __init__(self, data: np.ndarray) -> None:
        """Wrap an already validated buffer; use ``from_array`` instead."""
        super().__init__()
        self._array = data.view()
        self._array.flags.writeable = False

    @classmethod
    def from_array(cls, data: np.ndarray) -> DepthValue:
        """Wrap a depth buffer without copying it.

        Raises:
            TypeError: ``data`` is not ``uint16``.
            ValueError: ``data`` is not ``H×W``.
        """
        if data.dtype != np.uint16:
            raise TypeError(f"unsupported depth dtype {data.dtype}; use uint16")
        if data.ndim != 2:
            raise ValueError(f"unsupported depth shape {data.shape}; use H×W")
        return cls(data)

    @classmethod
    def empty(cls) -> DepthValue:
        """Return a 0×0 depth map."""
        return cls(np.zeros((0, 0), np.uint16))

    @property
    def is_empty(self) -> bool:
        """Whether the map has no pixels."""
        return self._array.size == 0

    @property
    def width(self) -> int:
        """Width in pixels."""
        return int(self._array.shape[1])

    @property
    def height(self) -> int:
        """Height in pixels."""
        return int(self._array.shape[0])

    def array(self) -> np.ndarray:
        """Return the ``H×W`` buffer in millimetres, read-only."""
        return self._array
