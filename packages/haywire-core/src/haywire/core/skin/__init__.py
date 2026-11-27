# haywire/core/skin/__init__.py
"""Skin settings schema — the data half of "skins" (core), as opposed to the
rendering half (haywire.ui.skin: nicegui-backed skin classes, node card
layout). Kept separate so core never imports from ui.
"""

from __future__ import annotations

from .settings import NodeDefaultSkinSettings

__all__ = [
    "NodeDefaultSkinSettings",
]
