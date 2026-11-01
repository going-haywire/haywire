"""``ModelRef``: which model a port points at, as a catalog entry or as a file."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ModelRef:
    """A reference to a model, in exactly one of two forms.

    - **Catalog reference**: ``catalog`` holds an entry key such as ``haybale-x:catalog:4x-Demo``;
      everything else is empty. It follows the catalog, so it carries no digest.
    - **File reference**: ``urls`` and/or ``sha256`` identify one file. A file picked from a
      volume has ``sha256``, ``size`` and ``label`` but no ``urls``; it resolves by digest.

    The empty reference (neither form) means "no model chosen".
    """

    catalog: str | None = None
    urls: tuple[str, ...] = ()
    sha256: str | None = None
    size: int | None = None
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "urls", tuple(self.urls))
        if self.catalog and (self.urls or self.sha256 or self.size is not None or self.label):
            raise ValueError("a catalog reference carries no urls, sha256, size or label")

    @classmethod
    def empty(cls) -> ModelRef:
        """The reference to no model."""
        return cls()

    @property
    def is_catalog(self) -> bool:
        return bool(self.catalog)

    @property
    def is_file(self) -> bool:
        return not self.is_catalog and bool(self.urls or self.sha256)

    @property
    def is_empty(self) -> bool:
        return not self.is_catalog and not self.is_file

    @property
    def source(self) -> str | None:
        """The first url, or ``None``."""
        return self.urls[0] if self.urls else None

    def pinned(self, sha256: str, size: int) -> ModelRef:
        """This file reference with its digest and size filled in."""
        return ModelRef(catalog=self.catalog, urls=self.urls, sha256=sha256, size=size, label=self.label)

    def to_dict(self) -> dict[str, Any]:
        """JSON form with empty fields left out."""
        data: dict[str, Any] = {}
        if self.catalog:
            data["catalog"] = self.catalog
        if self.urls:
            data["urls"] = list(self.urls)
        if self.sha256:
            data["sha256"] = self.sha256
        if self.size is not None:
            data["size"] = self.size
        if self.label:
            data["label"] = self.label
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelRef:
        """Build from :meth:`to_dict` output; ``{}`` is the empty reference."""
        size = data.get("size")
        return cls(
            catalog=data.get("catalog") or None,
            urls=tuple(data.get("urls") or ()),
            sha256=data.get("sha256") or None,
            size=int(size) if size is not None else None,
            label=data.get("label") or "",
        )
