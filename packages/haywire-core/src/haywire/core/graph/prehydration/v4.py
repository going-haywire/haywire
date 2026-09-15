"""v3 -> v4: ``DataPort``'s fold keys get their name."""

from __future__ import annotations

from typing import Any

from .upgrader import GraphDict, Upgrader
from .v3 import UpgradeVersionThree

#: Old port key -> new port key. Both mean fold membership, which is what the
#: port layer now calls its own hierarchy (ADR 0035).
_PORT_KEY_RENAMES = {"parent_group": "parent_fold", "is_group": "is_fold"}


class UpgradeVersionFour(Upgrader):
    """Rename every port's ``parent_group``/``is_group`` key to ``parent_fold``/``is_fold``.

    Completes ADR 0035, which replaced author-facing ``group()`` with ``fold()``
    but left these two internals — both meaning fold membership — behind. They
    are serialized, so a rename needs a migration rather than just a grep.

    Port keys live under ``nodes[*].node_data.ports[*].kwargs``, which is where
    ``DataPort.to_dict`` writes each non-default dataclass field.
    """

    to_version = 4

    def detect(self, data: GraphDict) -> bool:
        return data.get("format_version", 0) >= self.to_version

    @staticmethod
    def _migrate_port(port: Any) -> None:
        """Rename one port's fold keys in place."""
        if not isinstance(port, dict):
            return
        kwargs = port.get("kwargs")
        if not isinstance(kwargs, dict):
            return
        for old_key, new_key in _PORT_KEY_RENAMES.items():
            if old_key in kwargs:
                # A file carrying both keys was hand-edited; the new one wins.
                kwargs.setdefault(new_key, kwargs[old_key])
                del kwargs[old_key]

    def _change_structure(self, data: GraphDict) -> GraphDict:
        for node in (data.get("nodes") or {}).values():
            if not isinstance(node, dict):
                continue
            node_data = node.get("node_data")
            if not isinstance(node_data, dict):
                continue
            for port in (node_data.get("ports") or {}).values():
                self._migrate_port(port)
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeVersionThree()
