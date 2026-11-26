"""The browser marker that says which level mode an element needs before it takes input.

An element stamped ``view``, ``operate`` or ``edit`` takes pointer input only while
the level mode in force where it is drawn satisfies that mode. On a canvas card an
unstamped element counts as ``edit``. Where stamps nest, the strictest one around
an element decides: an inner stamp can only tighten.

The stamp is two classes, ``hw-requires`` and ``hw-requires-<mode>``, never an
attribute: a Quasar field (``ui.select``, ``ui.input``, ``ui.number``, ...) keeps
only ``class`` and ``style`` on its root and moves every other attribute to its
inner native element, where a press on its label or icons would miss it.
"""

from __future__ import annotations

from nicegui import ui

from haywire.core.access import LevelMode

REQUIRES_CLASS = "hw-requires"
"""Every stamped element carries this class; the mode is in ``requires_class(mode)``."""


def requires_class(mode: LevelMode) -> str:
    """The class that names *mode* on a stamped element, ``hw-requires-<mode>``."""
    return f"{REQUIRES_CLASS}-{mode.value}"


_MODE_CLASSES = " ".join(requires_class(mode) for mode in LevelMode)


def stamp_requires(element: ui.element, mode: LevelMode = LevelMode.EDIT) -> None:
    """Mark *element* as taking input from level mode *mode* on.

    The stamp is always written, also for the ``EDIT`` default: in a panel only
    stamped elements are gated. A second stamp replaces the first.

    Example::

        stamp_requires(handle)  # takes input only in edit
        stamp_requires(badge, LevelMode.VIEW)  # takes input in every mode
        stamp_requires(toggle, LevelMode.OPERATE)  # takes input in operate and edit
    """
    element.classes(remove=_MODE_CLASSES, add=f"{REQUIRES_CLASS} {requires_class(mode)}")


def stamped_mode(element: ui.element) -> LevelMode | None:
    """The level mode *element* is stamped with, or ``None`` when it carries no stamp."""
    for mode in LevelMode:
        if requires_class(mode) in element.classes:
            return mode
    return None
