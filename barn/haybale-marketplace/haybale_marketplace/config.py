"""Marketplace-specific path constants and bootstrap."""

from __future__ import annotations

from pathlib import Path

import toml

from haywire.core.storage import library_storage_dir

GLOBAL_MARKETPLACE_DIR: Path = library_storage_dir(__name__)

_DEFAULT_MARKETPLACE: dict = {
    "markets": [
        {
            "url": "https://going-haywire.github.io/haywire/marketplace.toml",
            "preference": [],
            "blocked": [],
        }
    ],
}


def ensure_marketplace_config() -> None:
    """Create ~/.haywire/db/haybale_marketplace/marketplace.toml with defaults if missing."""
    marketplace_file = GLOBAL_MARKETPLACE_DIR / "marketplace.toml"
    if not marketplace_file.exists():
        marketplace_file.write_text(toml.dumps(_DEFAULT_MARKETPLACE))
