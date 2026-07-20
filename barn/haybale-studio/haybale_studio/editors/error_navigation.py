"""Navigation helpers: error → component definition / involved file.

These translate a HaywireException's string locators into studio navigation
(active_component for the CONTEXT-slot source viewer; Reveal(CodeEditor) for
a file in the MAIN slot). Instance navigation (graph reveal + select) lives in
the same package but is a separate helper (see reveal_instance)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from haywire.core.errors.haywire_exception import HaywireException
    from haywire.core.session.context import SessionContext


def open_component(error: "HaywireException", context: "SessionContext") -> bool:
    """Point the CONTEXT-slot component source viewer at this error's component.

    Sets ``active_component = registry_key`` (the ComponentSourceEditor follows
    it). Returns False if the error has no registry_key."""
    if not error.can_open_component():
        return False
    context.active_component = error.registry_key
    return True


def open_file_in_studio(filepath: str, line_number: "int | None", context: "SessionContext") -> None:
    """Open a file in the studio's MAIN-slot CodeEditor.

    Mirrors ComponentSourceEditor._open_in_code_editor: set active_file, then
    Reveal the CodeEditor bound to the path. line_number is accepted for a
    future goto; the CodeEditor binds by path today."""
    from haybale_studio.editors.code_editor import CodeEditor
    from haywire.core.session.signals import Reveal

    path = Path(filepath)
    context.active_file = path
    context.session.publish(Reveal(editor=CodeEditor, binding_id=str(path), label=path.name))
