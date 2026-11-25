"""Widget fixture for a chip select as a node widget (browser test support).

A multiple ``ui.select`` with ``use-chips`` is the widget's root, with no plain element
around it: Quasar keeps only ``class`` and ``style`` on a field's root and moves every
other attribute inside, so this is the root a declared size box has to reach. Every
choice is preselected, enough chips to fill several rows at any width the tests use.

Backs ``tests/ui/harness/test_chip_select_widget.py``.
"""

from __future__ import annotations

from typing import Any

from nicegui import ui

from haywire.api import BaseWidget, widget
from haywire.api.workbench import LevelMode, stamp_requires

#: The narrowest the chip field makes its node, in px.
CHIP_FIELD_MIN_WIDTH = 160

#: Every choice, all of them chosen: one row of them is far wider than the floor.
CHIP_NAMES = [f"choice_number_{i:02d}" for i in range(12)]


@widget(description="A chip select as the widget's root, declaring a width", min_width=CHIP_FIELD_MIN_WIDTH)
class ChipSelectRootWidget(BaseWidget):
    """Twelve choices, all chosen, shown as chips; the select is the widget's root.

    A test fixture: it takes input only in edit mode and does not write to its port.
    """

    def build(self) -> Any:
        select = (
            ui.select(options=list(CHIP_NAMES), value=list(CHIP_NAMES), multiple=True)
            .props("use-chips")
            .classes("w-full text-xs")
        )
        stamp_requires(select, LevelMode.EDIT)
        return select
