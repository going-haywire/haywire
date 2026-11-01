"""Model catalog: OpenModelDB-shaped entries registered as components."""

from .entry import CatalogEntry, ModelFile, Resource
from .registry import ModelCatalogRegistry

__all__ = ["CatalogEntry", "ModelCatalogRegistry", "ModelFile", "Resource"]
