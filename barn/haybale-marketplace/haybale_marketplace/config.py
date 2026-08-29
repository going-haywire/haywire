"""Marketplace-specific path constants and bootstrap."""

from __future__ import annotations

from pathlib import Path

from haywire.core.storage import library_storage_dir

GLOBAL_MARKETPLACE_DIR: Path = library_storage_dir(__name__)

#: The framework's own feed. Carries the lockstep `barn/*` libraries that ship
#: with haywire itself, published by the monorepo on every release tag.
OFFICIAL_FEED_URL = "https://going-haywire.github.io/haywire/marketplace.toml"

#: The curated catalogue: going-haywire libraries in their own repos, plus
#: selected third-party ones. `stable` is the default because its assertion is
#: the one a default should make — every version in it was proven to resolve
#: and load *together*, which is the failure no runtime check can see (each
#: install is a separate resolve into one shared venv, so installing B can
#: silently upgrade a dependency A pinned older).
CURATED_FEED_BASE = "https://going-haywire.github.io/marketplace"
CURATED_STABLE_URL = f"{CURATED_FEED_BASE}/stable/marketplace.toml"

#: Written verbatim on first run. A text template rather than `toml.dumps` of a
#: dict, because comments are the point: switching channel means hand-editing
#: this file — there is no unsubscribe in the UI — so this is the one place a
#: user is guaranteed to open, and the alternatives belong in front of them
#: there rather than in a doc they would have to know to look for.
_DEFAULT_MARKETPLACE_TOML = f"""\
# Your marketplace subscriptions. Hand-edited — this is the recovery path when
# a source misbehaves, and the only way to change which channel you follow.
#
# A refresh never writes this file. It holds your intent; only you change it.

# ── the framework's own libraries ───────────────────────────────────────────
[[markets]]
url = "{OFFICIAL_FEED_URL}"
preference = []
blocked = []

# ── the curated catalogue ───────────────────────────────────────────────────
# Three channels carry the same libraries at different versions. They differ in
# what has been PROVEN about the version each one names — swap the url below to
# follow a different one, and subscribe to exactly one of the three: two at
# once offer the same names at different versions, which every refresh then
# reports as a conflict.
#
#   stable  versions proven to install and load TOGETHER as one set.
#           Advances when haywire cuts a release.
#   latest  the newest version of each library as of the last catalogue
#           release, each proven to install and load on its own.
#   edge    whatever is newest on PyPI right now. Regenerated nightly.
#           Asserts only that the library is in the catalogue.
[[markets]]
url = "{CURATED_STABLE_URL}"
preference = []
blocked = []

# url = "{CURATED_FEED_BASE}/latest/marketplace.toml"
# url = "{CURATED_FEED_BASE}/edge/marketplace.toml"
#
# Past catalogue releases stay published permanently, so an installation that
# must not move can pin to one. They are listed at:
#   {CURATED_FEED_BASE}/archives.html
"""


def ensure_marketplace_config() -> None:
    """Create ~/.haywire/db/haybale_marketplace/marketplace.toml if missing.

    Only ever writes when the file is absent, so an existing user's
    subscriptions — and any hand-edit they made — are never touched.
    """
    marketplace_file = GLOBAL_MARKETPLACE_DIR / "marketplace.toml"
    if not marketplace_file.exists():
        marketplace_file.write_text(_DEFAULT_MARKETPLACE_TOML, encoding="utf-8")
