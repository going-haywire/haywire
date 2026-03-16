# packages/haywire-core/src/haywire/ui/panel/__init__.py
"""
Panel system for the Haywire UI framework.

Panels are collapsible sections that appear inside editors, filtered by scope.
Use the @panel decorator to mark panel classes, PanelRegistry to manage them,
and ScopeDescriptor to define named scope tabs in panel-consuming editors.
"""

from .identity import PanelIdentity
from .base import BasePanel, PanelLayout
from .decorator import panel
from .registry import PanelRegistry
from .scope import ScopeDescriptor

__all__ = [
    'PanelIdentity',
    'BasePanel',
    'PanelLayout',
    'panel',
    'PanelRegistry',
    'ScopeDescriptor',
]
