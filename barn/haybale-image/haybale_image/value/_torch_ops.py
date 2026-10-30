"""Torch conversions between image storages; see ``ImageValue.tensor``.

Importing this module imports torch, so ``ImageValue`` imports it only inside its
tensor code paths.
"""

from __future__ import annotations

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


def _swap_colour_order(t: torch.Tensor) -> torch.Tensor:
    """Return CHW ``t`` with its first three channels reversed, alpha kept last."""
    if t.shape[0] == 1:
        return t
    index = [2, 1, 0, 3] if t.shape[0] == 4 else [2, 1, 0]
    return t[index]


def _rescale(t: torch.Tensor, src_max: int | None, dtype: torch.dtype, dst_max: int | None) -> torch.Tensor:
    """Return ``t`` as ``dtype``; ``*_max`` is the integer range of each side, ``None`` for [0, 1] floats."""
    if src_max == dst_max and t.dtype == dtype:
        return t
    if dst_max is None:
        work = t.to(dtype)
        return work if src_max is None else work * (1.0 / src_max)
    # Integer targets: clamp in [0, 1], then round half to even, in float32 for exact 16-bit values.
    unit = t.to(torch.float32) if src_max is None else t.to(torch.float32) / src_max
    return torch.round(unit.clamp(0.0, 1.0) * dst_max).to(dtype)


def upload(
    src: np.ndarray,
    src_order: ChannelOrder,
    device: str | torch.device,
    dtype: torch.dtype,
    order: ChannelOrder,
) -> torch.Tensor:
    """Return ``src`` as a ``1×C×H×W`` tensor of ``dtype`` on ``device``.

    Transfers the buffer in its stored dtype and converts on ``device``.
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
    t = t.unsqueeze(0) if t.ndim == 2 else t.permute(2, 0, 1)
    if src_order != order:
        t = _swap_colour_order(t)
    dst_max = 255 if dtype == torch.uint8 else None
    return _rescale(t, src_max, dtype, dst_max).unsqueeze(0)


def convert_tensor(
    src: torch.Tensor, src_order: ChannelOrder, device: torch.device, dtype: torch.dtype, order: ChannelOrder
) -> torch.Tensor:
    """Return CHW ``src`` as a ``1×C×H×W`` tensor of ``dtype`` on ``device``, converting after the move."""
    t = src.to(device, non_blocking=True)
    if src_order != order:
        t = _swap_colour_order(t)
    src_max = 255 if src.dtype == torch.uint8 else None
    return _rescale(t, src_max, dtype, 255 if dtype == torch.uint8 else None).unsqueeze(0)


def download(src: torch.Tensor, src_order: ChannelOrder, dtype: np.dtype, order: ChannelOrder) -> np.ndarray:
    """Return CHW ``src`` as a read-only ``H×W`` / ``H×W×C`` numpy array of ``dtype``.

    Converts on ``src``'s device before the transfer, so the smaller dtype crosses.
    """
    t = src if src_order == order else _swap_colour_order(src)
    src_max = 255 if src.dtype == torch.uint8 else None
    if dtype == np.uint16:
        t = _rescale(t, src_max, torch.int32, 65535)
    else:
        target = _NP_TO_TORCH[np.dtype(dtype)]
        t = _rescale(t, src_max, target, 255 if target == torch.uint8 else None)
    t = t[0] if t.shape[0] == 1 else t.permute(1, 2, 0)
    out = t.contiguous().cpu().numpy()
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
