"""Model catalog: OpenModelDB-shaped entries registered as components."""

from .entry import CatalogEntry, ModelFile, Resource
from .registry import CatalogRegistry

__all__ = ["CatalogEntry", "CatalogRegistry", "ModelFile", "Resource"]
