"""The Upgrader contract and the chain terminator.

One Upgrader per structural change to the ``.haywire`` format. Each converts
a graph dict from the shape the PREVIOUS version produced into its own.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

GraphDict = dict[str, Any]


class UnknownGraphFormat(Exception):
    """The dict is not recognisably a Haywire graph.

    Internal to this package — ``prehydrate`` catches it at the boundary and
    re-raises as a HaywireException.
    """


#: Structural floor. Every Haywire graph ever written carries these keys.
_REQUIRED = ("nodes", "edges")


def validate(data: GraphDict) -> None:
    """Raise :class:`UnknownGraphFormat` unless *data* is recognisably a graph.

    Checks **presence, not truthiness**: an edge-less graph still carries
    ``"edges": {}``, and three of the shipped fixtures are in exactly that
    state. Do not "simplify" this to ``if not data.get("edges")``.
    """
    missing = [key for key in _REQUIRED if key not in data]
    if missing:
        raise UnknownGraphFormat(f"missing required key(s): {', '.join(missing)}")


class Upgrader(ABC):
    """One step in the format migration chain."""

    #: The format version this upgrader PRODUCES.
    to_version: int

    @abstractmethod
    def detect(self, data: GraphDict) -> bool:
        """True when *data* is already at :attr:`to_version` **or newer**.

        Own-signal detection: each version decides for itself what proves a
        file is already its shape. The signal may be the ``format_version``
        key, or — for versions predating it — a structural marker. A rule
        that later proves wrong is fixed here, without touching the chain.

        "or newer" is what makes the short-circuit in :meth:`upgrade`
        correct: a current file matches at the head and returns untouched.
        """

    @abstractmethod
    def _change_structure(self, data: GraphDict) -> GraphDict:
        """Apply this version's structural change.

        The predecessor has already run, so *data* is in the previous
        version's shape.
        """

    @abstractmethod
    def _predecessor(self) -> "Upgrader":
        """The upgrader producing the version immediately below this one."""

    def upgrade(self, data: GraphDict) -> GraphDict:
        """Bring *data* up to :attr:`to_version`, recursing first.

        Template method: subclasses supply the three abstract members only,
        so the recurse / short-circuit / stamp sequence is written once and
        cannot drift between versions.

        ``validate`` runs on the short-circuit path too, and that is
        load-bearing. Detection rules are often *absence*-based (v1's signal
        is "graph_id and name are both gone"), and absence matches unrelated
        dicts — ``{"totally": "unrelated"}`` would otherwise be claimed at
        the head and never reach the terminator. A ``detect`` that says
        "already current" must still be answering about a graph.
        """
        if self.detect(data):
            validate(data)
            return data

        data = self._predecessor().upgrade(data)
        data = self._change_structure(data)
        data["format_version"] = self.to_version
        return data


class UpgradeAncient(Upgrader):
    """Chain terminator — the oldest shape we accept.

    Nothing precedes it: by the time recursion reaches here, no later
    version claimed the dict, so it is either genuinely ancient or not a
    graph at all.
    """

    to_version = 0

    def detect(self, data: GraphDict) -> bool:
        validate(data)
        return True

    def _change_structure(self, data: GraphDict) -> GraphDict:
        return data

    def _predecessor(self) -> Upgrader:
        raise AssertionError("UpgradeAncient.upgrade never recurses (detect is always True)")
