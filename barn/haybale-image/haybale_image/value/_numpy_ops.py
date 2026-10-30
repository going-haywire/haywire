"""Numpy conversions between image storages; see ``ImageValue.array``."""

from __future__ import annotations

import numpy as np

from haybale_image.value.enums import ChannelOrder

# Largest value of each integer dtype; float dtypes span [0, 1].
_INT_MAX = {np.dtype(np.uint8): 255, np.dtype(np.uint16): 65535}


def read_only(a: np.ndarray) -> np.ndarray:
    """Return a read-only view of ``a``, leaving ``a`` itself writable."""
    view = a.view()
    view.setflags(write=False)
    return view


def swap_colour_order(a: np.ndarray) -> np.ndarray:
    """Return ``a`` with its first three channels reversed (RGB ↔ BGR), alpha kept last."""
    if a.ndim == 2:
        return a
    index = [2, 1, 0, 3] if a.shape[2] == 4 else [2, 1, 0]
    return a[..., index]


def convert_dtype(a: np.ndarray, dtype: np.dtype) -> np.ndarray:
    """Return ``a`` as ``dtype``, rescaling between integer ranges and [0, 1]; returns ``a`` if unchanged."""
    src = a.dtype
    if src == dtype:
        return a
    if src in _INT_MAX and dtype in _INT_MAX:
        if dtype == np.uint16:
            return a.astype(np.uint16) * np.uint16(257)
        return np.rint(a / np.float32(257)).astype(np.uint8)
    if src in _INT_MAX:
        return (a.astype(np.float32) * np.float32(1 / _INT_MAX[src])).astype(dtype)
    if dtype in _INT_MAX:
        scaled = np.clip(a.astype(np.float32, copy=False), 0.0, 1.0) * np.float32(_INT_MAX[dtype])
        return np.rint(scaled).astype(dtype)
    return a.astype(dtype)


def convert(src: np.ndarray, src_order: ChannelOrder, dtype: np.dtype, order: ChannelOrder) -> np.ndarray:
    """Return ``src`` stored as ``dtype`` in ``order``, read-only; a view of ``src`` when nothing changes."""
    out = src if src_order == order else swap_colour_order(src)
    return read_only(convert_dtype(out, dtype))
