"""Where a macro's source is, and whether it may be edited.

"Open the component's source" means a Python file for a node class and a
document for a macro. These answer the macro half, so the studio's editing
surfaces — the placement's context menu, the add-node menu, the library
overview, ledger navigation — resolve it the same way.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from haywire.core.library.install_type import InstallType
from haywire.core.macro.origin import MacroOrigin

if TYPE_CHECKING:
    from haywire.core.graph.base import BaseGraph
    from haywire.core.macro.template import MacroTemplate
    from haywire.core.node.base import BaseNode

_MACRO_KIND = "macro"


def is_macro_key(registry_key: str) -> bool:
    """Whether ``registry_key`` names a macro."""
    return registry_key.split(":")[1:2] == [_MACRO_KIND]


def is_macro_placement(node: "BaseNode") -> bool:
    """Whether ``node`` is a card standing for a macro.

    Its interior is runtime state rebuilt from the template, so it can be
    entered and viewed but not edited in place; the document is the editing
    surface.

    Read off the CLASS identity: a placement's instance ``identity`` is its
    template's, which describes the macro rather than the card standing for it.
    """
    class_identity = getattr(type(node), "class_identity", None)
    return bool(getattr(class_identity, "_is_macro_node", False))


def modified_instance_origin(node: "BaseNode") -> MacroOrigin | None:
    """Return the origin of the Group ``node`` stands for, or ``None``.

    ``None`` for a node that is not a Graph-node, an unbound card, and a Group
    that was not detached from a macro.
    """
    resolve = getattr(node, "resolve_definition", None)
    if resolve is None:
        return None
    definition = resolve()
    return getattr(definition, "origin", None)


def macro_template(registry_key: str) -> "MacroTemplate | None":
    """Return the template registered under ``registry_key``, or ``None`` when absent."""
    from haywire.core.di.config import get_library_system

    try:
        library_system = get_library_system()
    except Exception:
        return None
    return library_system.get_macro_registry().template(registry_key)


def origin_label(definition: Any) -> str:
    """Return the label of the macro ``definition`` stands for or was detached from.

    The template's label, or the definition's own when the template is not
    registered, or the macro's registry key when it has neither.
    """
    origin = getattr(definition, "origin", None)
    key = getattr(definition, "template_key", None) or (origin.key if origin is not None else "")
    template = macro_template(key) if key else None
    if template is not None:
        return str(template.class_identity.label)
    return str(getattr(definition, "label", "") or key)


def macro_source_path(registry_key: str) -> Path | None:
    """The ``.hwm`` file behind a macro key, or ``None``.

    ``None`` covers both a key that is not a macro and a macro whose library
    is absent, since neither has a document to open.
    """
    if not is_macro_key(registry_key):
        return None
    try:
        template = macro_template(registry_key)
    except Exception:
        return None
    return template.path if template is not None else None


def count_placements(graphs: Iterable["BaseGraph"], registry_key: str) -> tuple[int, int]:
    """Count the placements of the macro ``registry_key`` across ``graphs``.

    Every Subgraph is searched at any depth, a placement's interior included.

    Returns:
        ``(placements, graphs)``: how many placements there are, and how many of
        ``graphs`` hold at least one.
    """
    placements = 0
    holding = 0
    for graph in graphs:
        found = _placements_in(graph, registry_key)
        placements += found
        if found:
            holding += 1
    return placements, holding


def _placements_in(graph: "BaseGraph", registry_key: str) -> int:
    """Placements of ``registry_key`` in ``graph`` and every Subgraph beneath it."""
    found = sum(1 for wrapper in graph.node_wrappers.values() if wrapper.registry_key == registry_key)
    for definition in graph.subgraphs.values():
        found += _placements_in(definition, registry_key)
    return found


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
