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
    FLYOUT_OPEN_DELAY_S,
    FLYOUT_PROPS,
    FLYOUT_Z,
    FlyoutIcon,
    FlyoutSiblings,
    SubmenuRow,
    close_flyout,
    flyout_category,
    menu_item_tooltip,
    open_flyout_group,
    open_on_hover,
)
from haywire.ui.elements.icons import AppIcon  # noqa: F401

# Module-level alias: hui.icon.add, hui.icon.canvas, etc.
icon = AppIcon

# hui.flyout(icon, tooltip=...) / hui.submenu_row(label, icon=None, enabled=True)
# — classes, not @contextmanager generators (see flyout.py for why).
flyout = FlyoutIcon
submenu_row = SubmenuRow
