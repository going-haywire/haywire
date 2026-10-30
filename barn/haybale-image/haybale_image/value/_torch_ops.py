"""Torch conversions between image storages; see ``ImageValue.tensor``.

Importing this module imports torch.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import torch

from haybale_image.value.enums import ChannelOrder

TENSOR_DTYPES: frozenset[torch.dtype] = frozenset(
    {torch.uint8, torch.float16, torch.bfloat16, torch.float32}
)

_NP_TO_TORCH = {
    np.dtype(np.uint8): torch.uint8,
    np.dtype(np.float16): torch.float16,
    np.dtype(np.float32): torch.float32,
}

Axes = Literal["chw", "hwc"]


def _channel_count(t: torch.Tensor, axes: Axes) -> int:
    if axes == "chw":
        return int(t.shape[0])
    return 1 if t.ndim == 2 else int(t.shape[2])


def _channel_map(channels: int, swap: bool) -> list[int]:
    """Return, for each output channel, the input channel it copies; a swap reverses colour, keeps alpha."""
    if not swap or channels == 1:
        return list(range(channels))
    return [2, 1, 0, 3][:channels]


def _remap(t: torch.Tensor, src_axes: Axes, dst_axes: Axes, swap: bool, dtype: torch.dtype) -> torch.Tensor:
    """Return a new ``dtype`` tensor holding ``t`` in ``dst_axes`` with channels reordered, in one copy."""
    channels = _channel_count(t, src_axes)
    height, width = (t.shape[1], t.shape[2]) if src_axes == "chw" else (t.shape[0], t.shape[1])
    shape = (channels, height, width) if dst_axes == "chw" else (height, width, channels)
    out = torch.empty(shape, dtype=dtype, device=t.device)
    if channels == 1:
        out.view(height, width).copy_(t.reshape(height, width))
        return out
    # Per-channel copies fold the reorder into the layout copy: an index or a permute
    # would cost a pass of its own.
    for dst, src in enumerate(_channel_map(channels, swap)):
        source = t[src] if src_axes == "chw" else t[..., src]
        (out[dst] if dst_axes == "chw" else out[..., dst]).copy_(source)
    return out


def _convert(
    t: torch.Tensor,
    src_axes: Axes,
    dst_axes: Axes,
    swap: bool,
    src_max: int | None,
    dtype: torch.dtype,
    dst_max: int | None,
) -> torch.Tensor:
    """Return ``t`` in ``dst_axes`` as a new ``dtype`` tensor on ``t``'s device.

    ``src_max`` / ``dst_max`` are the integer range of each side, ``None`` for [0, 1] floats.
    Integer targets clip to [0, 1] and round half to even.
    """
    if dst_max is not None:
        if src_max == dst_max:
            return _remap(t, src_axes, dst_axes, swap, dtype)
        unit = _remap(t, src_axes, dst_axes, swap, torch.float32)
        if src_max is not None:
            unit.div_(src_max)
        return unit.clamp_(0.0, 1.0).mul_(dst_max).round_().to(dtype)
    if src_max is None:
        return _remap(t, src_axes, dst_axes, swap, dtype)
    if src_max == 255 and dtype == torch.float16:
        # 0..255 is exact in float16, so the camera path scales without a float32 pass.
        return _remap(t, src_axes, dst_axes, swap, dtype).mul_(1.0 / 255)
    # Other integers scale in float32: 65535 overflows float16, bfloat16 would round twice.
    return _remap(t, src_axes, dst_axes, swap, torch.float32).div_(src_max).to(dtype)


def upload(
    src: np.ndarray,
    src_order: ChannelOrder,
    device: str | torch.device,
    dtype: torch.dtype,
    order: ChannelOrder,
) -> torch.Tensor:
    """Return ``src`` as a new ``1×C×H×W`` tensor of ``dtype`` on ``device``.

    Transfers the buffer in its stored dtype (uint16 as int32) and converts on ``device``.
    """
    if src.dtype == np.uint16:
        # torch has no uint16 arithmetic; int32 holds every value.
        host = torch.from_numpy(src.astype(np.int32))
        src_max: int | None = 65535
    else:
        contiguous = src if src.flags.c_contiguous else np.ascontiguousarray(src)
        host = torch.from_numpy(contiguous)
        src_max = 255 if src.dtype == np.uint8 else None
    t = host.to(device, non_blocking=True)
    dst_max = 255 if dtype == torch.uint8 else None
    return _convert(t, "hwc", "chw", src_order != order, src_max, dtype, dst_max).unsqueeze(0)


def convert_tensor(
    src: torch.Tensor, src_order: ChannelOrder, device: torch.device, dtype: torch.dtype, order: ChannelOrder
) -> torch.Tensor:
    """Return CHW ``src`` as a new ``1×C×H×W`` tensor of ``dtype`` on ``device``.

    Converts on the GPU side of the move: after it when uploading, before it when downloading.
    """
    src_max = 255 if src.dtype == torch.uint8 else None
    dst_max = 255 if dtype == torch.uint8 else None
    swap = src_order != order
    if device.type == "cpu" and src.device.type != "cpu":
        # A non-blocking device-to-host copy returns before the data arrives, so downloads block.
        return _convert(src, "chw", "chw", swap, src_max, dtype, dst_max).to(device).unsqueeze(0)
    t = src.to(device, non_blocking=True)
    return _convert(t, "chw", "chw", swap, src_max, dtype, dst_max).unsqueeze(0)


def download(src: torch.Tensor, src_order: ChannelOrder, dtype: np.dtype, order: ChannelOrder) -> np.ndarray:
    """Return CHW ``src`` as a read-only ``H×W`` / ``H×W×C`` numpy array of ``dtype``.

    Converts on ``src``'s device before the transfer, so the smaller dtype crosses.
    """
    src_max = 255 if src.dtype == torch.uint8 else None
    dst_max: int | None
    if dtype == np.uint16:
        target, dst_max = torch.int32, 65535
    else:
        target = _NP_TO_TORCH[np.dtype(dtype)]
        dst_max = 255 if target == torch.uint8 else None
    t = _convert(src, "chw", "hwc", src_order != order, src_max, target, dst_max)
    out = t.cpu().numpy()
    if out.shape[2] == 1:
        out = out[:, :, 0]
    if dtype == np.uint16:
        out = out.astype(np.uint16)
    out.setflags(write=False)
    return out


def tensor_layout(data: torch.Tensor) -> torch.Tensor:
    """Return ``data`` as ``C×H×W``, accepting ``C×H×W`` or ``1×C×H×W``; raise ``ValueError`` otherwise."""
    if data.ndim == 4 and data.shape[0] == 1:
        data = data[0]
    if data.ndim != 3 or data.shape[0] not in (1, 3, 4):
        raise ValueError(f"unsupported image tensor shape {tuple(data.shape)}; use C×H×W or 1×C×H×W")
    return data


def check_tensor_dtype(dtype: torch.dtype) -> torch.dtype:
    """Return ``dtype``; raise ``TypeError`` unless it is uint8, float16, bfloat16 or float32."""
    if dtype not in TENSOR_DTYPES:
        raise TypeError(f"unsupported image tensor dtype {dtype}; use uint8, float16, bfloat16 or float32")
    return dtype


def default_source_depth(dtype: torch.dtype) -> int:
    """Return the bit depth a tensor of ``dtype`` came from: 8 for uint8, else 32."""
    return 8 if dtype == torch.uint8 else 32
