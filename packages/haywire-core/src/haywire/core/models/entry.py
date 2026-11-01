"""One model catalog file, parsed and under the component contract."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from haywire.core.library.identity import LibraryIdentity
from haywire.core.registry.identity import BaseIdentity

#: Resource tags, in the order a variant name joins them.
_TAG_ORDER = ("platform", "type", "backend", "precision")


@dataclass(frozen=True)
class ModelFile:
    """One file of a resource.

    ``path`` is the file's name inside a bundle; ``""`` for a single-file resource.
    """

    path: str
    sha256: str | None
    size: int | None
    urls: tuple[str, ...]


@dataclass(frozen=True)
class Resource:
    """One downloadable variant of a catalog entry: a file or a bundle of files.

    A tag the resource lacks (``None``) means it runs anywhere.
    """

    platform: str
    type: str
    size: int | None
    sha256: str | None
    urls: tuple[str, ...]
    files: tuple[ModelFile, ...]
    backend: str | None = None
    precision: str | None = None

    def tags(self) -> dict[str, str]:
        """The tags this resource carries, omitting those it lacks."""
        values = {
            "platform": self.platform,
            "type": self.type,
            "backend": self.backend,
            "precision": self.precision,
        }
        return {name: value for name in _TAG_ORDER if (value := values[name])}

    def variant_name(self) -> str:
        """Tag values joined in tag order (``pytorch-pth-fp16``), or ``default``."""
        return "-".join(self.tags().values()) or "default"

    @property
    def is_bundle(self) -> bool:
        """Whether the resource is several files rather than one."""
        return len(self.files) > 1 or any(f.path for f in self.files)

    @property
    def total_size(self) -> int | None:
        """Sum of the file sizes, or the resource's own size when files carry none."""
        sizes = [f.size for f in self.files]
        if sizes and all(s is not None for s in sizes):
            return sum(s for s in sizes if s is not None)
        return self.size


@dataclass
class CatalogEntry:
    """A model catalog JSON file registered as a component.

    Field names follow OpenModelDB. Behind the same ``class_identity`` /
    ``class_library`` pair a class exposes, so the docs generator and
    farmhand helpers read it without knowing it is a file.
    """

    name: str
    author: str
    license: str
    architecture: str
    scale: int | None
    purpose: list[str]
    tags: list[str]
    description: str
    size: int | None
    input_channels: int | None
    output_channels: int | None
    requires: dict[str, Any]
    resources: tuple[Resource, ...]
    document: dict[str, Any]
    path: Path
    content_hash: str
    identity: BaseIdentity
    library: LibraryIdentity

    @property
    def class_identity(self) -> BaseIdentity:
        return self.identity

    @property
    def class_library(self) -> LibraryIdentity:
        return self.library

    def fields(self) -> dict[str, Any]:
        """The entry-level fields a port ``filter`` matches against."""
        return {
            "architecture": self.architecture,
            "scale": self.scale,
            "purpose": self.purpose,
            "tags": self.tags,
            "license": self.license,
            "input_channels": self.input_channels,
            "output_channels": self.output_channels,
        }
