"""Farmhand contribution seam (SDK-free): tools, registry, context."""

from haywire.core.farmhand.base import Farmhand
from haywire.core.farmhand.decorator import farmhand
from haywire.core.farmhand.identity import FarmhandIdentity, ToolAnnotations
from haywire.core.farmhand.registry import FarmhandRegistry
from haywire.core.farmhand.schema import derive_input_schema

__all__ = [
    "Farmhand",
    "FarmhandIdentity",
    "FarmhandRegistry",
    "ToolAnnotations",
    "derive_input_schema",
    "farmhand",
]
