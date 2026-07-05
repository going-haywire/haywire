"""
haywire.ui.elements — Haywire Design System component wrappers.

Import as:

    from haywire.ui import elements as hui

    hui.panel_header(...)
    hui.icon.add
    hui.icon.canvas

The ``icon`` attribute is the ``AppIcon`` class (all attributes are class-level
strings), so ``hui.icon.add`` and ``AppIcon.add`` are identical.
"""

from haywire.ui.elements.elements import *  # noqa: F401, F403
from haywire.ui.elements.flyout import (  # noqa: F401
    FLYOUT_PROPS,
    FLYOUT_Z,
    FlyoutSiblings,
    close_flyout,
    flyout_category,
    menu_item_tooltip,
    open_on_hover,
)
from haywire.ui.elements.icons import AppIcon  # noqa: F401

# Module-level alias: hui.icon.add, hui.icon.canvas, etc.
icon = AppIcon
