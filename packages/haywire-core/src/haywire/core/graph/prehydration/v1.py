"""v0 -> v1: drop the persisted ``graph_id`` and ``name``."""

from __future__ import annotations

from .upgrader import GraphDict, UpgradeAncient, Upgrader


class UpgradeVersionOne(Upgrader):
    """Drop ``graph_id`` and ``name``.

    ``graph_id`` became a transient per-instance uuid; a file that records
    one lies the moment it is copied or opened twice.

    ``name`` is **dropped, not renamed** to ``filestem``. An upgrader gets a
    dict, not a filename, so it cannot compute the real stem — and every
    pre-v1 file's ``name`` is a stale ``"Untitled N"`` from creation time
    (three shipped fixtures all say ``"Untitled 1"``). Renaming would
    launder a wrong value into a field that promises otherwise.
    ``BaseGraph.load_from_file`` stamps the true stem right after this runs.
    """

    to_version = 1

    def detect(self, data: GraphDict) -> bool:
        if data.get("format_version", 0) >= self.to_version:
            return True
        # v1 predates format_version, so there is no version key to read.
        # Its own signal: both legacy keys are gone.
        return "graph_id" not in data and "name" not in data

    def _change_structure(self, data: GraphDict) -> GraphDict:
        data.pop("graph_id", None)
        data.pop("name", None)
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeAncient()
