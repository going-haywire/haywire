# packages/haywire-core/src/haywire/ui/panel/__init__.py
"""
Panel system for the Haywire UI framework.

Panels are collapsible sections that appear inside editors. Each panel
declares a Focus subclass via the @panel decorator; action panels also
declare an `actions:` type annotation on the class body. Two query
surfaces are provided:
  - PanelRegistry.get_panels_for_focus(focus): display panels with no
    action_protocol, used by PropertiesEditor.
  - PanelRegistry.get_panels_for_action(action_protocol, focus): action
    panels for context-menu hosts.
"""

from .identity import PanelIdentity
from .layout import PanelLayout
from .focus import Focus, all_focuses, focus_by_id
from .base import BasePanel
from .registry import PanelRegistry

# Import decorator last so the `panel` name resolves to the decorator function
# rather than the `.panel` submodule (the `from .panel import BasePanel` above
# binds `panel` as a submodule attribute on the package; importing the
# decorator after that shadows it back to the function).
from .decorator import panel  # noqa: E402

__all__ = [
    "PanelIdentity",
    "PanelLayout",
    "base",
    "Focus",
    "all_focuses",
    "focus_by_id",
    "BasePanel",
    "PanelRegistry",
    "panel",
]
