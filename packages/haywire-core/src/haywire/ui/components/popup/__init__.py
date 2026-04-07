# packages/haywire-core/src/haywire/ui/panel/__init__.py
"""
Panel system for the Haywire UI framework.

Panels are collapsible sections that appear inside editors, filtered by scope.
Use the @panel decorator to mark panel classes, PanelRegistry to manage them,
and ScopeDescriptor to define named scope tabs in panel-consuming editors.
"""

from .popup import Popup

__all__ = [
    "Popup",
]