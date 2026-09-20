"""Where a macro's source is, and whether it may be edited.

"Open the component's source" means a Python file for a node class and a
document for a macro. These answer the macro half, so the studio's editing
surfaces — the placement's context menu, the add-node menu, the library
overview, ledger navigation — resolve it the same way.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from haywire.core.library.install_type import InstallType

if TYPE_CHECKING:
    from haywire.core.node.base import BaseNode

_MACRO_KIND = "macro"


def is_macro_key(registry_key: str) -> bool:
    """Whether ``registry_key`` names a macro."""
    return registry_key.split(":")[1:2] == [_MACRO_KIND]


def is_macro_placement(node: "BaseNode") -> bool:
    """Whether ``node`` is a card standing for a macro.

    Descending into one is refused: its interior is runtime state rebuilt from
    the template, so there is nothing there a user may edit in place. The
    document is opened instead.

    Read off the CLASS identity: a placement's instance ``identity`` is its
    template's, which describes the macro rather than the card standing for it.
    """
    class_identity = getattr(type(node), "class_identity", None)
    return bool(getattr(class_identity, "_is_macro_node", False))


def macro_source_path(registry_key: str) -> Path | None:
    """The ``.hwm`` file behind a macro key, or ``None``.

    ``None`` covers both a key that is not a macro and a macro whose library
    is absent, since neither has a document to open.
    """
    if not is_macro_key(registry_key):
        return None
    try:
        from haywire.core.di.config import get_library_system

        template = get_library_system().get_macro_registry().template(registry_key)
    except Exception:
        return None
    return template.path if template is not None else None


def _install_type_of(library_id: str, library_system: Any) -> InstallType | None:
    """The install type of the library ``library_id``, or ``None`` if unknown."""
    try:
        return library_system.get_library_registry().get_library_install_type(library_id)
    except Exception:
        return None


def macro_edit_refusal(registry_key: str, library_system: Any) -> str | None:
    """Why this macro cannot be opened for editing, or ``None`` if it can.

    Editing is allowed only for a library installed with ``pip -e``, whose
    files on disk are the ones the framework loads and watches — the same
    authority the component source editor uses. A refusal names the reason so
    the studio can show it instead of opening an empty editor.

    Returns:
        The reason, or ``None`` when the macro may be edited.
    """
    library_id = registry_key.split(":", 1)[0]
    install_type = _install_type_of(library_id, library_system)

    if install_type is None or install_type is InstallType.NOT_INSTALLED:
        return (
            f"The library '{library_id}' providing this macro is not installed in this "
            f"environment, so its file cannot be opened."
        )
    if not install_type.is_editable():
        return (
            f"'{library_id}' is installed as a package, so its macros are read-only. "
            f"Install it with 'pip install -e' to edit them in place."
        )
    return None
