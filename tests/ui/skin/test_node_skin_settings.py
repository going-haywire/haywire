"""Every NodeSkinSettings field must be read by a skin.

The bag renders straight into a settings panel, so a declared-but-unread field
is worse than an absent one: the user toggles it and nothing happens, which
reads as a broken feature rather than a missing one. `show_node_ids` and
`show_port_ids` sat unread from introduction until they were deleted — under a
class docstring asserting "All fields are wired to actual rendering logic".

Enforced by source inspection rather than by rendering, because "is this value
ever consumed" is not observable from a rendered card: a field read and then
ignored looks identical to one never read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from haybale_studio.settings.node_skin_settings import NodeSkinSettings

pytestmark = pytest.mark.unit

# Skins are the declared consumer ("consumed directly by NodeSkin and its
# subclasses"). Accessors on NodeSkin (CARD_H_PADDING and friends) live here
# too, so this directory is the whole read surface.
_SKIN_DIR = Path(__file__).resolve().parents[3] / "barn/haybale-studio/haybale_studio/skins"


def _declared_fields() -> set[str]:
    return set(NodeSkinSettings._property_settings())


def _fields_read_by_skins() -> set[str]:
    """Field names appearing as `self._ui_settings.<name>` anywhere in the skins."""
    pattern = re.compile(r"_ui_settings\.([a-z_][a-z0-9_]*)")
    found: set[str] = set()
    for path in _SKIN_DIR.rglob("*.py"):
        found.update(pattern.findall(path.read_text()))
    return found


def test_skin_directory_is_where_this_test_thinks_it_is():
    """Guard the premise — a bad path would make every assertion below vacuous."""
    assert _SKIN_DIR.is_dir(), f"skin directory not found: {_SKIN_DIR}"
    assert (_SKIN_DIR / "node_skin.py").is_file()


def test_every_declared_field_is_read_by_a_skin():
    unread = _declared_fields() - _fields_read_by_skins()
    assert not unread, (
        f"NodeSkinSettings declares {sorted(unread)}, which no skin reads. "
        f"These render in the settings panel and do nothing — wire them or "
        f"delete them."
    )


def test_no_skin_reads_a_field_that_was_deleted():
    """The reverse direction: a stale read would be an AttributeError at render."""
    unknown = _fields_read_by_skins() - _declared_fields()
    assert not unknown, f"skins read {sorted(unknown)}, which NodeSkinSettings does not declare"


@pytest.mark.parametrize("gone", ["show_node_ids", "show_port_ids"])
def test_deleted_debug_fields_stay_deleted(gone):
    """Deleted 2026-08-22: declared but never read since introduction."""
    assert gone not in _declared_fields()
