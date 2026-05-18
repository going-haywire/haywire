"""
Marketplace data model.

MarketplaceEntry is the canonical representation of a package available
for installation from a marketplace manifest (local or remote TOML).
"""

from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class MarketplaceEntry:
    """A package available for installation from a marketplace manifest."""

    name: str  # pip distribution name, e.g. "haybale-visiongraph"
    min_version: str  # minimum required version floor, e.g. "0.0.1"; not "latest available"
    label: str = ""  # human-readable display name, e.g. "Visiongraph"
    description: str = ""
    author: str = ""
    source: str = "pypi"
    install_spec: str = ""
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)  # pip package names, e.g. ["haybale-core"]
    source_url: str = ""  # URL to the library's source (repo/subdirectory)
    docs_url: str = ""  # Raw URL to OVERVIEW.md (or directory containing it)
    source_label: str = ""  # "project", "official", "my-team" — which feed this came from
    source_file: str = ""  # local file path the user can edit (always a local file)
    source_origin: str = ""  # remote URL if this entry was fetched via a [[sources]] URL

    # Fields that are persisted to / read from marketplace TOML files.
    # Order here controls output order in serialized snippets.
    _TOML_FIELDS: ClassVar[tuple[str, ...]] = (
        "name",
        "label",
        "min_version",
        "description",
        "author",
        "source",
        "install_spec",
        "tags",
        "dependencies",
        "source_url",
        "docs_url",
    )

    def to_dict(self) -> dict:
        """Return a TOML-serializable dict, omitting empty/default values."""
        result = {}
        for f in self._TOML_FIELDS:
            val = getattr(self, f)
            if val or val == 0:  # keep falsy-but-meaningful values like 0; skip "" and []
                result[f] = val
        return result
