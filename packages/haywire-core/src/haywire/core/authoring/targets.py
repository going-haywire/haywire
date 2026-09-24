"""Which libraries a component may be written into."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from haywire.core.registry.component import ComponentRegistry


@dataclass(frozen=True)
class AuthoringTarget:
    """A library a component may be written into.

    ``folder`` is the folder the library registered with the kind's registry
    (its ``macros/`` or ``nodes/`` folder), which need not exist yet: a
    library that registered the folder before any file was authored still has
    nothing on disk. ``is_watched`` says whether the library runs a file
    watcher, so a new file registers without a restart.
    """

    library_id: str
    label: str
    folder: Path
    is_project_library: bool
    is_watched: bool = False


def authoring_targets(
    library_system: Any,
    registry_cls: "type[ComponentRegistry]",
    workspace_root: Path | None = None,
) -> list[AuthoringTarget]:
    """The libraries a component of ``registry_cls``'s kind may be written into, best first.

    A target is a library that is editable (``InstallType.is_editable()``: its
    files on disk are the ones the framework loads and watches) and that
    registered a folder with ``registry_cls``. A library missing either cannot
    receive the file: one is read-only, the other would never scan it.

    The project's own library, the one under ``workspace_root/barn``, sorts
    first. Watched and unwatched libraries are both returned; filter on
    ``is_watched`` where registration must follow the write.

    Args:
        library_system: The library system service, for the registries.
        registry_cls: The registry of the kind being authored, e.g.
            ``NodeRegistry`` or ``MacroRegistry``.
        workspace_root: The project root, for deciding which target is the
            project's own. Without it no target is marked as such and the
            order is alphabetical.

    Returns:
        The targets, project library first, then by label. Empty when no
        library can receive the file or the registries are unreachable.

    Example::

        from haywire.core.node.registry import NodeRegistry

        targets = [t for t in authoring_targets(library_system, NodeRegistry, root) if t.is_watched]
        default = targets[0] if targets else None
    """
    try:
        registry = library_system.injector.get(registry_cls)
        library_registry = library_system.get_library_registry()
    except Exception:
        return []

    barn = (workspace_root / "barn").resolve() if workspace_root is not None else None

    targets: list[AuthoringTarget] = []
    seen: set[str] = set()

    for folder_path, identity in registry._folder_to_library.items():
        library_id = identity.name
        if library_id in seen:
            continue

        install_type = library_registry.get_library_install_type(library_id)
        if install_type is None or not install_type.is_editable():
            continue

        folder = Path(folder_path)
        is_project = False
        if barn is not None:
            try:
                is_project = folder.resolve().is_relative_to(barn)
            except OSError:
                is_project = False

        library = library_registry.get_library(library_id)
        seen.add(library_id)
        targets.append(
            AuthoringTarget(
                library_id=library_id,
                label=identity.label or library_id,
                folder=folder,
                is_project_library=is_project,
                is_watched=bool(library is not None and library.is_watched),
            )
        )

    targets.sort(key=lambda t: (not t.is_project_library, t.label.lower()))
    return targets
