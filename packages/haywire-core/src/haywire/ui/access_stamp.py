"""The browser marker that says which level mode an element needs before it takes input.

An element stamped ``data-hw-requires="view|operate|edit"`` takes pointer input
only while the level mode in force where it is drawn satisfies that mode. On a
canvas card an unstamped element counts as ``edit``.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.access import LevelMode


def stamp_requires(element: ui.element, mode: LevelMode = LevelMode.EDIT) -> None:
    """Mark *element* as taking input from level mode *mode* on.

    The attribute is always written, also for the ``EDIT`` default: in a panel
    only stamped elements are gated.

    Example::

        stamp_requires(handle)  # takes input only in edit
        stamp_requires(badge, LevelMode.VIEW)  # takes input in every mode
        stamp_requires(toggle, LevelMode.OPERATE)  # takes input in operate and edit
    """
    element.props(f'data-hw-requires="{mode.value}"')
