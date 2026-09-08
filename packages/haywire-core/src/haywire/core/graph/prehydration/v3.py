"""v2 -> v3: promotion records become dicts, so they can carry ``show_widget``."""

from __future__ import annotations

from typing import Any

from .upgrader import GraphDict, Upgrader
from .v2 import UpgradeVersionTwo


class UpgradeVersionThree(Upgrader):
    """Rewrite every ``promoted`` entry from a bare direction string to a dict.

    v2 recorded a promotion as ``storage_key -> "outlet"``. A promoted port's
    widget visibility became user-settable (pin menu), and that choice has
    nowhere else to live: a promoted port is regenerated from this record on
    load rather than serialized in the ports block. So the value widens to
    ``{"direction": "outlet"}``, with an optional ``"show_widget"`` added only
    when the user picked something other than the direction default.

    Migrated files carry no ``show_widget`` — nobody could have set one before
    this version existed, so every migrated promotion resolves to its direction
    default, exactly as it rendered in v2.

    Promotion records live in two places, and both are walked:

    - ``nodes[*].settings[*].promoted`` — the real ones.
    - ``meta.promoted`` — the graph's own ``GraphSettings`` bag. Always empty
      in practice (``GraphSettings._node`` is always None, so a graph-level
      field can never be promoted), but normalized anyway so the shape is
      uniform wherever a bag was written.
    """

    to_version = 3

    def detect(self, data: GraphDict) -> bool:
        return data.get("format_version", 0) >= self.to_version

    @staticmethod
    def _migrate_bag(bag: Any) -> None:
        """Rewrite one settings bag's ``promoted`` block in place."""
        if not isinstance(bag, dict):
            return
        promoted = bag.get("promoted")
        if not isinstance(promoted, dict):
            return
        for key, record in list(promoted.items()):
            # Already a dict: a v3-shaped record reached here through a mixed
            # or hand-edited file. Leave it alone rather than re-wrapping it.
            if isinstance(record, str):
                promoted[key] = {"direction": record}

    def _change_structure(self, data: GraphDict) -> GraphDict:
        for node in (data.get("nodes") or {}).values():
            if not isinstance(node, dict):
                continue
            for bag in (node.get("settings") or {}).values():
                self._migrate_bag(bag)
        self._migrate_bag(data.get("meta"))
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeVersionTwo()
