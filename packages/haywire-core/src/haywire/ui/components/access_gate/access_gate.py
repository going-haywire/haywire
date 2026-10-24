"""Browser-side level-mode enforcer: one per page, for canvas cards and panels, pointer and keyboard."""

from __future__ import annotations

from nicegui import ui

from haywire.core.access import LevelMode


class AccessGate(ui.element, component="access_gate.vue"):
    """Stop content the level mode in force does not satisfy from taking pointer input or keyboard focus.

    The gate reads ``data-hw-requires`` (see ``stamp_requires``) in two scopes:

    - Canvas cards: an element inside a card (``.ui-node-slot``) takes input
      while the canvas root's ``data-hw-level-mode`` satisfies the element's
      nearest ``data-hw-requires``; an unstamped element counts as ``edit``.
    - Panels: inside ``[data-hw-mode-scope="session"]`` only stamped elements
      are gated, against the session mode written here to ``<html
      data-hw-session-mode>``; a gated one is greyed (``opacity: 0.5``).

    A gated element takes no pointer input and loses keyboard focus as it gains
    it, or when a mode change gates the focused element. Mount one per page;
    the browser exposes the decision as ``window.hwAccess.isGated(el)``. The
    gate is the browser half of the level mode: the server still refuses the
    write.

    Args:
        session_mode: The session's level mode at mount.

    Example::

        gate = AccessGate(session_mode=context.level_mode)
        gate.set_session_mode(LevelMode.EDIT)  # panel writers stamped up to edit take input
    """

    def __init__(self, *, session_mode: LevelMode = LevelMode.VIEW) -> None:
        super().__init__()
        self._props["sessionMode"] = session_mode.value

    def set_session_mode(self, mode: LevelMode) -> None:
        """Gate panel content against level mode ``mode``."""
        self._props["sessionMode"] = mode.value
        self.update()
