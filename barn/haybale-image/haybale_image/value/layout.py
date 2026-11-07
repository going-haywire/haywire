"""Layout conversion on an image's own storage; see ``convert_layout``."""

from __future__ import annotations

import numpy as np

from haybale_image.value import _numpy_ops
from haybale_image.value.enums import Layout
from haybale_image.value.image_value import ImageValue


def convert_layout(img: ImageValue, layout: Layout) -> ImageValue:
    """Return ``img`` with the channels of ``layout``, in the same storage.

    The result stays where ``img`` lives (numpy stays numpy, a tensor stays on its
    device) and keeps its dtype, channel order, ``source_depth``, metadata and fields. Gray
    becomes colour by replication; a missing alpha is fully opaque; alpha is
    dropped by slicing; colour becomes gray by Rec. 601 luma over the stored
    channels, rounded for integer dtypes. Returns ``img`` itself when the layout
    already matches.
    """
    if img.layout is layout:
        return img
    primary = img._primary  # noqa: SLF001 - same package, reads the stored buffer
    if isinstance(primary, np.ndarray):
        out = ImageValue.from_array(
            _numpy_ops.convert_layout(primary, img.layout, layout, img._order),  # noqa: SLF001
            order=img._order,  # noqa: SLF001
            source_depth=img.source_depth,
            metadata=img.metadata,
        )
    else:
        from haybale_image.value import _torch_ops

        out = ImageValue.from_tensor(
            _torch_ops.convert_layout(primary, img.layout, layout, img._order),  # noqa: SLF001
            order=img._order,  # noqa: SLF001
            source_depth=img.source_depth,
            metadata=img.metadata,
        )
    return out.with_fields(img.fields)
