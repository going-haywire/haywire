"""v4 -> v5: a node no longer carries its class's identity and library, nor its props twice."""

from __future__ import annotations

from typing import Any

from haywire.core.node.legacy import LEGACY_PORTS_KEY

from .upgrader import GraphDict, Upgrader
from .v4 import UpgradeVersionFour


def _older(a: str, b: str) -> str:
    """Return the lower of two dotted version strings; a malformed one loses to a well-formed one."""

    def parts(version: str) -> tuple[int, ...] | None:
        try:
            return tuple(int(piece) for piece in version.split("."))
        except ValueError:
            return None

    pa, pb = parts(a), parts(b)
    if pa is None:
        return b
    if pb is None:
        return a
    return a if pa <= pb else b


class UpgradeVersionFive(Upgrader):
    """Move each node's library version into a ``requires`` table and drop what the class says.

    A v4 node carried an ``identity`` and a ``library`` block copied from its class, its
    ``props`` a second time under ``settings``, and its id a second time inside ``node_data``.
    v5 keeps one fact from them: the version of each library the file was saved with, as
    ``requires: {library name: version}`` at the top of the document. Where two nodes of
    one library disagree, the lower version is kept.

    A v5 file can also carry ``declarations``, the port declaration of each node class it
    was saved against. A v4 file has none and gains it on its next save.

    A v4 port saved every field, so a value its code has since changed cannot be told from
    one the user set. Each node with ports is marked with ``LEGACY_PORTS_KEY``, which makes
    the load take a declared port's fields from the code (``NodeData._deserialize_ports``).
    The mark stays on a node whose class is not loaded and goes when the node is saved.

    Every Subgraph definition in ``subgraphs`` is a document of the same shape and is
    upgraded the same way.
    """

    to_version = 5

    def detect(self, data: GraphDict) -> bool:
        return data.get("format_version", 0) >= self.to_version

    def _upgrade_document(self, data: Any) -> None:
        """Rewrite one graph or Subgraph document in place."""
        if not isinstance(data, dict):
            return
        requires: dict[str, str] = dict(data.get("requires") or {})
        for node in (data.get("nodes") or {}).values():
            if not isinstance(node, dict):
                continue
            node_data = node.get("node_data")
            if not isinstance(node_data, dict):
                continue
            library = node_data.pop("library", None)
            if isinstance(library, dict):
                name, version = library.get("name"), library.get("version")
                if isinstance(name, str) and name and isinstance(version, str) and version:
                    requires[name] = _older(requires[name], version) if name in requires else version
            node_data.pop("identity", None)
            if node_data.get("ports"):
                node_data[LEGACY_PORTS_KEY] = True
            node_data.pop("node_id", None)
            settings = node_data.get("settings")
            if isinstance(settings, dict):
                duplicate = settings.pop("props", None)
                # A file holding only the copy under settings keeps its props.
                if duplicate is not None and "props" not in node_data:
                    node_data["props"] = duplicate
        data["requires"] = requires
        for subgraph in (data.get("subgraphs") or {}).values():
            self._upgrade_document(subgraph)

    def _change_structure(self, data: GraphDict) -> GraphDict:
        self._upgrade_document(data)
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeVersionFour()
