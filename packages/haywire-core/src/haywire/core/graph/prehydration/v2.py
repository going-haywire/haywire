"""v1 -> v2: nest the editable metadata fields into a ``meta`` bag."""

from __future__ import annotations

from .upgrader import GraphDict, Upgrader
from .v1 import UpgradeVersionOne


class UpgradeVersionTwo(Upgrader):
    """Move ``label`` / ``description`` / ``author`` / ``version`` into ``meta``.

    They became a ``GraphSettings`` bag (``graph.meta``), serialized under a
    single ``"meta"`` key beside ``"props"``.

    A settings bag serializes as ``{"values": {...}, "promoted": {...}}`` —
    NOT a flat mapping. ``Settings.from_dict`` raises ``PromotedFormatError``
    on the flat shape (it is the pre-promotion-refactor format), so emitting
    a bare dict here would make every migrated file fail to load its
    metadata.
    """

    to_version = 2

    _META_FIELDS = ("label", "description", "author", "version")

    def detect(self, data: GraphDict) -> bool:
        return data.get("format_version", 0) >= self.to_version

    def _change_structure(self, data: GraphDict) -> GraphDict:
        meta = data.get("meta") or {}
        values = dict(meta.get("values", {}))
        for field in self._META_FIELDS:
            if field in data:
                values.setdefault(field, data.pop(field))
        data["meta"] = {"values": values, "promoted": dict(meta.get("promoted", {}))}
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeVersionOne()
