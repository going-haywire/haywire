# packages/haywire-framework/src/haywire/ui/panel/__init__.py
"""
Panel system for the Haywire UI framework.

Panels are collapsible sections that appear inside editors, filtered by context.
Use the @panel decorator to mark panel classes, and PanelRegistry to manage them.
"""

from .identity import PanelIdentity
from .base import BasePanel, PanelLayout
from .decorator import panel
from .registry import PanelRegistry

__all__ = [
    'PanelIdentity',
    'BasePanel',
    'PanelLayout',
    'panel',
    'PanelRegistry',
]
