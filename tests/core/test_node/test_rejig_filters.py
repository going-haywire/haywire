"""``rejig``'s filters: several criteria per side, OR'd within, AND'd across.

A port is flagged for removal when it matches ``include`` and does not match
``exclude``. Each filter is a regex string, or a list mixing exact ids,
``PortOrigin`` values and compiled patterns.

The origin criterion is what lets a node rebuild an interface stamped from
outside while sparing the growing slot it declared itself — a bare ``rejig()``
takes both.
"""

from __future__ import annotations

import re

import pytest

from haywire.core.graph.base import BaseGraph
from haywire.core.types.enums import PortOrigin

from tests.conftest import make_node

pytestmark = [pytest.mark.integration]

_ADD = "haybale-testing:node:TestAddFloatNode"


def _stamp(node, specs) -> None:
    """Give ``node`` exactly ``specs``, ignoring what it declared."""
    with node.rejig():
        for spec in specs:
            node.add(spec)


@pytest.fixture
def node_with_mixed_ports(graph_with_library_system: BaseGraph):
    """A node carrying two DECLARED ports and two RESOLVED ones."""
    from haywire.barn.builtin.types import FLOAT

    graph = graph_with_library_system
    wrapper = make_node(graph, _ADD)
    node = wrapper.node
    _stamp(
        node,
        [
            FLOAT.as_inlet("kept_a", origin=PortOrigin.DECLARED),
            FLOAT.as_inlet("kept_b", origin=PortOrigin.DECLARED),
            FLOAT.as_inlet("grown_a", origin=PortOrigin.RESOLVED),
            FLOAT.as_inlet("grown_b", origin=PortOrigin.RESOLVED),
        ],
    )
    return node


def _ids(node) -> set[str]:
    return set(node.ports)


class TestOriginCriterion:
    def test_excluding_an_origin_spares_those_ports(self, node_with_mixed_ports):
        """The trap's fix: rebuild the interface, keep what the node declared."""
        node = node_with_mixed_ports

        with node.rejig(exclude=[PortOrigin.DECLARED]):
            pass  # re-add nothing

        assert _ids(node) == {"kept_a", "kept_b"}

    def test_including_an_origin_flags_only_those(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(include=[PortOrigin.RESOLVED]):
            pass

        assert _ids(node) == {"kept_a", "kept_b"}

    def test_a_bare_rejig_still_flags_everything(self, node_with_mixed_ports):
        """Unchanged, and the reason the trap needs documenting."""
        node = node_with_mixed_ports

        with node.rejig():
            pass

        assert _ids(node) == set()


class TestSeveralCriteriaAreOred:
    def test_an_id_and_an_origin_together(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=["grown_a", PortOrigin.DECLARED]):
            pass

        assert _ids(node) == {"kept_a", "kept_b", "grown_a"}

    def test_a_pattern_and_an_origin_together(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=[re.compile(r"^grown_"), PortOrigin.DECLARED]):
            pass

        assert _ids(node) == {"kept_a", "kept_b", "grown_a", "grown_b"}

    def test_two_ids(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=["kept_a", "grown_a"]):
            pass

        assert _ids(node) == {"kept_a", "grown_a"}


class TestIncludeAndExcludeAreAnded:
    def test_exclude_wins_over_include(self, node_with_mixed_ports):
        """A port named by both is spared."""
        node = node_with_mixed_ports

        with node.rejig(include=[PortOrigin.RESOLVED], exclude=["grown_a"]):
            pass

        assert _ids(node) == {"kept_a", "kept_b", "grown_a"}

    def test_an_exclude_outside_the_include_set_changes_nothing(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(include=[PortOrigin.RESOLVED], exclude=["kept_a"]):
            pass

        assert _ids(node) == {"kept_a", "kept_b"}


class TestEmptyAndNone:
    def test_an_empty_include_flags_nothing(self, node_with_mixed_ports):
        """``include=[]`` is none; ``include=None`` is all."""
        node = node_with_mixed_ports

        with node.rejig(include=[]):
            pass

        assert _ids(node) == {"kept_a", "kept_b", "grown_a", "grown_b"}

    def test_an_empty_exclude_spares_nothing(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=[]):
            pass

        assert _ids(node) == set()

    def test_an_unknown_id_is_ignored(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=["nobody", PortOrigin.DECLARED]):
            pass

        assert _ids(node) == {"kept_a", "kept_b"}


class TestTheBareStringStaysARegex:
    """The single-pattern spelling predates lists and keeps its meaning."""

    def test_a_bare_string_include_is_a_regex(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(include=r"^grown_"):
            pass

        assert _ids(node) == {"kept_a", "kept_b"}

    def test_a_bare_string_exclude_is_a_regex(self, node_with_mixed_ports):
        node = node_with_mixed_ports

        with node.rejig(exclude=r"^kept_"):
            pass

        assert _ids(node) == {"kept_a", "kept_b"}

    def test_a_string_inside_a_list_is_an_exact_id(self, node_with_mixed_ports):
        """``"kept_a"`` in a list matches that port only, not a pattern."""
        node = node_with_mixed_ports

        with node.rejig(exclude=["kept_"]):
            pass

        assert _ids(node) == set()


class TestReAddedPortsSurvive:
    def test_a_flagged_port_re_added_keeps_its_place(self, node_with_mixed_ports):
        from haywire.barn.builtin.types import FLOAT

        node = node_with_mixed_ports

        with node.rejig(exclude=[PortOrigin.DECLARED]):
            node.add(FLOAT.as_inlet("grown_a", origin=PortOrigin.RESOLVED))

        assert _ids(node) == {"kept_a", "kept_b", "grown_a"}
