"""
Eager-then-lazy folder tree.

``FolderTreeModel`` walks a folder three levels deep up front and plants a
"Click to load children" sentinel under every folder that still has unloaded
contents; expanding the sentinel loads three more levels. ``folder_tree``
renders a model as a ``ui.tree``.

Symlinked directories are leaves (never followed). Excluded directory names
and dot-entries (except ``.haywire``) are skipped.
"""

import copy
from collections.abc import Callable
from pathlib import Path

from nicegui import ui

# Suffix of the id of a folder's "load more" sentinel child.
_LOAD_MORE_ID = "__load_more__"
_SENTINEL_SEP = "::"


class FolderTreeModel:
    """Q-tree node dicts for a folder, loaded three levels at a time.

    ``nodes`` holds q-tree node dicts (``id`` is the absolute path string,
    ``label`` the entry name). Folders past the batch depth carry a single
    sentinel child until ``expand_sentinel`` loads them.

    Example::

        model = FolderTreeModel(Path("/project"), show_files=False)
        model.expand_sentinel("/project/a/b/c")  # load the next batch
    """

    def __init__(
        self,
        root: Path,
        *,
        show_files: bool = True,
        exclude_dirs: frozenset[str] = frozenset(),
        batch_depth: int = 3,
    ) -> None:
        self.root = root
        self.show_files = show_files
        self.exclude_dirs = exclude_dirs
        self.batch_depth = batch_depth
        self.nodes: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self.rebuild()

    def rebuild(self) -> None:
        """Re-walk from the root and reset every sentinel."""
        self._by_id.clear()
        self.nodes = self._build_subtree(self.root, depth=0)
        self._index_nodes(self.nodes)

    def is_sentinel(self, node_id: str) -> bool:
        """Return whether ``node_id`` is a "load more" sentinel."""
        return node_id.endswith(_LOAD_MORE_ID)

    def node(self, node_id: str) -> dict | None:
        """Return the node dict for ``node_id``, or ``None`` when unknown (sentinels are not indexed)."""
        return self._by_id.get(node_id)

    def has_sentinel_child(self, node_id: str) -> bool:
        """Return whether the node's children are still an unloaded sentinel."""
        node = self._by_id.get(node_id)
        if node is None:
            return False
        return any(self.is_sentinel(child["id"]) for child in node.get("children") or [])

    def expand_sentinel(self, node_id: str) -> bool:
        """Load three more levels under folder ``node_id``; return whether children were loaded."""
        node = self._by_id.get(node_id)
        if node is None:
            return False
        path = Path(node_id)
        if not path.is_dir():
            return False
        children = self._build_subtree(path, depth=0)
        node["children"] = children
        self._index_nodes(children)
        return True

    @staticmethod
    def sentinel_parent_id(sentinel_id: str) -> str:
        """Return the folder id a sentinel id belongs to."""
        return sentinel_id[: -(len(_SENTINEL_SEP) + len(_LOAD_MORE_ID))]

    def _skipped(self, entry: Path) -> bool:
        if entry.name.startswith(".") and entry.name != ".haywire":
            return True
        is_dir = entry.is_dir()
        if is_dir and entry.name in self.exclude_dirs:
            return True
        return not is_dir and not self.show_files

    def _build_subtree(self, path: Path, depth: int) -> list[dict]:
        items: list[dict] = []
        try:
            entries = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except (PermissionError, OSError):
            return items
        for entry in entries:
            if self._skipped(entry):
                continue
            node: dict = {"id": str(entry), "label": entry.name}
            if entry.is_dir() and not entry.is_symlink():
                if depth + 1 < self.batch_depth:
                    node["children"] = self._build_subtree(entry, depth + 1)
                else:
                    node["children"] = self._sentinel_for(entry)
            items.append(node)
        return items

    def _sentinel_for(self, path: Path) -> list[dict]:
        """Return a single "load more" child for ``path``, or [] when nothing visible is inside."""
        try:
            for entry in path.iterdir():
                if self._skipped(entry):
                    continue
                return [
                    {
                        "id": f"{path}{_SENTINEL_SEP}{_LOAD_MORE_ID}",
                        "label": "Click to load children",
                    }
                ]
        except (PermissionError, OSError):
            pass
        return []

    def _index_nodes(self, nodes: list[dict]) -> None:
        for node in nodes:
            if self.is_sentinel(node["id"]):
                continue
            self._by_id[node["id"]] = node
            self._index_nodes(node.get("children") or [])


def folder_tree(model: FolderTreeModel, *, on_select: Callable[[Path], None]) -> ui.tree:
    """Render ``model`` as a ``ui.tree`` and return it.

    Clicking a sentinel, or expanding a folder whose only child is a sentinel,
    loads the next batch. Clicking a folder toggles its expansion. ``on_select``
    receives the path of every clicked file or folder (never a sentinel).
    """
    tree: ui.tree

    def push_nodes(parent_id: str) -> None:
        # Vue/Quasar prop diff is reference-based, so push a fresh deep copy. Quasar resets
        # its expansion on a full nodes replacement; re-apply the expanded ids plus the parent.
        previously_expanded = list(tree._props.get("expanded", []) or [])
        tree._props["nodes"] = copy.deepcopy(model.nodes)
        keep = [eid for eid in previously_expanded if not model.is_sentinel(eid)]
        if parent_id not in keep:
            keep.append(parent_id)
        tree._props["expanded"] = keep
        tree.update()

    def expand(parent_id: str) -> None:
        if model.expand_sentinel(parent_id):
            push_nodes(parent_id)

    def handle_expand(expanded_ids: list[str]) -> None:
        for node_id in expanded_ids or []:
            if not model.is_sentinel(node_id) and model.has_sentinel_child(node_id):
                expand(node_id)

    def handle_select(node_id: str | None) -> None:
        if not node_id:
            return
        if model.is_sentinel(node_id):
            tree.deselect()
            expand(model.sentinel_parent_id(node_id))
            return
        path = Path(node_id)
        if not path.is_file():
            expanded = tree._props.get("expanded", [])
            if node_id in expanded:
                tree.collapse([node_id])
            else:
                tree.expand([node_id])
            tree.deselect()
        on_select(path)

    tree = (
        ui.tree(
            copy.deepcopy(model.nodes),
            label_key="label",
            node_key="id",
            on_select=lambda e: handle_select(e.value),
            # on_expand makes `expanded` a controlled prop, so the server tracks
            # arrow-driven expansion; without it the first sentinel click re-applies a
            # stale (empty) set and collapses the whole tree.
            on_expand=lambda e: handle_expand(e.value),
        )
        .props("dense no-transition")
        .classes("w-full text-sm hw-tree")
    )
    return tree
