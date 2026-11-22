"""v5 -> v6: the components renamed in 0.6 get their new registry keys."""

from __future__ import annotations

from haywire.core.renames import bundled_renames, rewrite_graph_keys

from .upgrader import GraphDict, Upgrader
from .v5 import UpgradeVersionFive

#: The release whose bundled key maps this version applies.
_RELEASE = "0.6"


class UpgradeVersionSix(Upgrader):
    """Rewrite every registry key the bundled 0.6 key maps rename.

    Every file at format v5 or older was saved before 0.6, and every library whose
    components 0.6 renamed releases with core, so every key those maps list is an old
    one. Only whole keys match, and the maps hold no chains, so a v5 file already
    holding the new keys passes through unchanged.

    The rewrite is ``haywire rename --map``'s, over the whole document: ``registry_key``,
    ``widget_key`` and ``chain_adapter_keys`` at any depth (port type recipes and
    ``subgraphs`` included), the keys of the ``declarations`` table, and a renamed
    key's ``class_name``, ``registry_id`` and ``module`` copies.
    """

    to_version = 6

    def detect(self, data: GraphDict) -> bool:
        return data.get("format_version", 0) >= self.to_version

    def _change_structure(self, data: GraphDict) -> GraphDict:
        rewrite_graph_keys(data, list(bundled_renames(_RELEASE)))
        return data

    def _predecessor(self) -> Upgrader:
        return UpgradeVersionFive()
