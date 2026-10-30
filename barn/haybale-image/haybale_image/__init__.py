"""Haybale-Image: image values shared by vision and ML libraries.

Provides:
  - ImageValue (``haybale_image.value``): an image with fixed semantics (RGB order,
    values in [0, 1], layout, source depth) and free storage (dtype, channel order,
    numpy array or torch tensor on any device), reached only through accessors.

The IMAGE types, adapters, IO nodes and viewer arrive in a later slice.
"""

from haywire.core.library.base import BaseLibrary
from haywire.core.library.decorator import library


@library(
    file_watcher=True,
)
class Library(BaseLibrary):
    """Image library — image values, types and IO."""

    def register_components(self):
        """Register nothing yet: types, adapters and nodes arrive with the IMAGE types."""

    def validate(self) -> bool:
        return True
