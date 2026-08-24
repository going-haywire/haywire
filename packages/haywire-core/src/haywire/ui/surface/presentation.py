# packages/haywire-core/src/haywire/ui/surface/presentation.py
"""Presentation: chrome metadata for surfaces that draw a tab/label/icon."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Presentation:
    """Chrome a host draws around a surface: a label and an icon.

    Declared only by surfaces whose host draws chrome around them (e.g. the
    properties editor draws a tab per root surface that declares one). A
    menu or toolbar surface with no chrome of its own leaves
    ``Surface.presentation`` as ``None``.
    """

    label: str
    icon: str
