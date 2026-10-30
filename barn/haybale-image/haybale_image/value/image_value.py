"""``ImageValue``: one image with fixed semantics and free storage."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt

from haybale_image.value import _numpy_ops
from haybale_image.value.enums import ChannelOrder, Layout

if TYPE_CHECKING:
    import torch

ARRAY_DTYPES: frozenset[np.dtype] = frozenset(
    np.dtype(d) for d in (np.uint8, np.uint16, np.float16, np.float32)
)
SOURCE_DEPTHS = (8, 16, 32)
_LAYOUT_BY_CHANNELS = {1: Layout.GRAY, 3: Layout.RGB, 4: Layout.RGBA}


def default_source_depth(dtype: np.dtype) -> int:
    """Return the bit depth a buffer of ``dtype`` came from: 8, 16, or 32 for any float."""
    if dtype == np.uint8:
        return 8
    if dtype == np.uint16:
        return 16
    return 32


def check_source_depth(source_depth: int) -> int:
    """Return ``source_depth``; raise ``ValueError`` unless it is 8, 16 or 32."""
    if source_depth not in SOURCE_DEPTHS:
        raise ValueError(f"source_depth must be one of {SOURCE_DEPTHS}, got {source_depth}")
    return source_depth


class ImageValue:
    """An image whose meaning is fixed and whose storage is free.

    The meaning never changes: colours are RGB, float values span [0, 1], the
    ``layout`` is gray, RGB or RGBA, and ``source_depth`` records the bit depth
    the pixels came from. The storage is whatever the producer had: a numpy array
    or a torch tensor on any device, in any supported dtype, with RGB or BGR
    channel order. Read pixels only through ``array()`` and ``tensor()``, which
    convert on first use and cache the result on the value. A value is immutable;
    build a new one for new pixels.

    Example::

        frame = camera.read()                        # H×W×3 uint8, BGR
        img = ImageValue.from_array(frame, order=ChannelOrder.BGR)  # no copy
        img.layout                                   # Layout.RGB
        rgb = img.array()                            # float32 RGB in [0, 1]
        bgr = img.array(np.uint8, ChannelOrder.BGR)  # the camera buffer itself
    """

    __slots__ = ("_primary", "_order", "_layout", "_source_depth", "_height", "_width", "_cache")

    def __init__(
        self,
        primary: Any,
        order: ChannelOrder,
        layout: Layout,
        source_depth: int,
        height: int,
        width: int,
    ) -> None:
        """Wrap an already validated buffer; use ``from_array`` or ``from_tensor`` instead."""
        self._primary = primary
        self._order = order
        self._layout = layout
        self._source_depth = source_depth
        self._height = height
        self._width = width
        self._cache: dict[tuple[Any, ...], Any] = {}

    @classmethod
    def from_array(
        cls,
        data: np.ndarray,
        *,
        order: ChannelOrder = ChannelOrder.RGB,
        source_depth: int | None = None,
    ) -> ImageValue:
        """Wrap a numpy image without copying it.

        The value takes ownership of ``data``: the caller must not write to it
        afterwards. An ``H×W×1`` array is treated as gray.

        Args:
            data: ``H×W`` or ``H×W×1`` (gray), ``H×W×3`` (RGB) or ``H×W×4`` (RGBA),
                with dtype ``uint8``, ``uint16``, ``float16`` or ``float32``.
                Float values span [0, 1]; strided views are accepted.
            order: Channel order of ``data``'s colour channels.
            source_depth: Bit depth the pixels came from (8, 16 or 32); defaults
                to the depth of ``data``'s dtype.

        Raises:
            TypeError: ``data`` has an unsupported dtype.
            ValueError: ``data`` has an unsupported shape, or ``source_depth`` is
                not 8, 16 or 32.
        """
        if data.dtype not in ARRAY_DTYPES:
            raise TypeError(f"unsupported image dtype {data.dtype}; use uint8, uint16, float16 or float32")
        if data.ndim == 3 and data.shape[2] == 1:
            data = data[:, :, 0]
        if data.ndim == 2:
            layout = Layout.GRAY
        elif data.ndim == 3 and data.shape[2] in _LAYOUT_BY_CHANNELS:
            layout = _LAYOUT_BY_CHANNELS[data.shape[2]]
        else:
            raise ValueError(f"unsupported image shape {data.shape}; use H×W, H×W×1, H×W×3 or H×W×4")
        depth = (
            default_source_depth(data.dtype) if source_depth is None else check_source_depth(source_depth)
        )
        return cls(data, order, layout, depth, int(data.shape[0]), int(data.shape[1]))

    @classmethod
    def from_tensor(
        cls,
        data: torch.Tensor,
        *,
        order: ChannelOrder = ChannelOrder.RGB,
        source_depth: int | None = None,
    ) -> ImageValue:
        """Wrap a torch image without copying it or moving it off its device.

        The value takes ownership of ``data``: the caller must not write to it
        afterwards. Requires torch.

        Args:
            data: ``C×H×W`` or ``1×C×H×W`` with C = 1 (gray), 3 (RGB) or 4 (RGBA),
                dtype ``uint8``, ``float16``, ``bfloat16`` or ``float32``. Float
                values span [0, 1].
            order: Channel order of ``data``'s colour channels.
            source_depth: Bit depth the pixels came from (8, 16 or 32); defaults
                to 8 for ``uint8`` and 32 for float dtypes.

        Raises:
            TypeError: ``data`` has an unsupported dtype.
            ValueError: ``data`` has an unsupported shape, or ``source_depth`` is
                not 8, 16 or 32.
        """
        from haybale_image.value import _torch_ops

        _torch_ops.check_tensor_dtype(data.dtype)
        chw = _torch_ops.tensor_layout(data)
        layout = _LAYOUT_BY_CHANNELS[int(chw.shape[0])]
        depth = (
            _torch_ops.default_source_depth(chw.dtype)
            if source_depth is None
            else check_source_depth(source_depth)
        )
        return cls(chw, order, layout, depth, int(chw.shape[1]), int(chw.shape[2]))

    @property
    def layout(self) -> Layout:
        """Which channels the image has."""
        return self._layout

    @property
    def width(self) -> int:
        """Width in pixels."""
        return self._width

    @property
    def height(self) -> int:
        """Height in pixels."""
        return self._height

    @property
    def channels(self) -> int:
        """Number of channels: 1, 3 or 4."""
        return {Layout.GRAY: 1, Layout.RGB: 3, Layout.RGBA: 4}[self._layout]

    @property
    def source_depth(self) -> int:
        """Bit depth the pixels came from: 8, 16 or 32."""
        return self._source_depth

    def array(self, dtype: npt.DTypeLike = np.float32, order: ChannelOrder = ChannelOrder.RGB) -> np.ndarray:
        """Return the pixels as a read-only numpy array, converted on first use and cached.

        Returns the stored buffer itself (as a read-only view) when it already has
        ``dtype`` and ``order``. Float results span [0, 1]; converting to an
        integer dtype clips to [0, 1] first, then rounds half to even.

        Args:
            dtype: ``uint8``, ``uint16``, ``float16`` or ``float32``.
            order: Channel order of the result; ignored for gray images.

        Returns:
            ``H×W`` for gray images, ``H×W×C`` otherwise.

        Raises:
            TypeError: ``dtype`` is not one of the supported dtypes.
        """
        target = np.dtype(dtype)
        if target not in ARRAY_DTYPES:
            raise TypeError(f"unsupported image dtype {target}; use uint8, uint16, float16 or float32")
        key = ("array", target, order)
        cached = self._cache.get(key)
        if cached is None:
            if isinstance(self._primary, np.ndarray):
                cached = _numpy_ops.convert(self._primary, self._order, target, order)
            else:
                from haybale_image.value import _torch_ops

                cached = _torch_ops.download(self._primary, self._order, target, order)
            self._cache[key] = cached
        return cached

    def tensor(
        self,
        device: str | torch.device,
        dtype: torch.dtype | None = None,
        order: ChannelOrder = ChannelOrder.RGB,
    ) -> torch.Tensor:
        """Return the pixels as a ``1×C×H×W`` torch tensor on ``device``, converted on first use and cached.

        A numpy-backed image transfers in its stored dtype and converts on
        ``device``, so a uint8 camera frame crosses at a quarter of the float32
        size. Float results span [0, 1]. Treat the result as read-only: it is
        shared by every caller asking for the same ``device``, ``dtype`` and
        ``order``. Requires torch.

        Args:
            device: Target device, e.g. ``"cuda"``, ``"mps"`` or ``"cpu"``.
            dtype: ``torch.uint8``, ``float16``, ``bfloat16`` or ``float32``;
                ``None`` means ``torch.float32``.
            order: Channel order of the result; ignored for gray images.

        Raises:
            TypeError: ``dtype`` is not one of the supported dtypes.
        """
        import torch

        from haybale_image.value import _torch_ops

        target = _torch_ops.check_tensor_dtype(torch.float32 if dtype is None else dtype)
        dev = torch.device(device)
        key = ("tensor", str(dev), target, order)
        cached = self._cache.get(key)
        if cached is None:
            if isinstance(self._primary, np.ndarray):
                cached = _torch_ops.upload(self._primary, self._order, dev, target, order)
            else:
                cached = _torch_ops.convert_tensor(self._primary, self._order, dev, target, order)
            self._cache[key] = cached
        return cached

    @property
    def residency(self) -> str:
        """Where the stored pixels live: ``"array"`` for numpy, else the tensor's device (``"cuda:0"``)."""
        if isinstance(self._primary, np.ndarray):
            return "array"
        return str(self._primary.device)
