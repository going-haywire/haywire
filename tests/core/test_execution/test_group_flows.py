"""Partitioning flows into execution groups (ADR 0064)."""

from dataclasses import dataclass, field
from typing import List

from haywire.core.execution.execution_group import group_flows, shared_data_node_ids


@dataclass
class _Node:
    node_id: str


@dataclass
class _Flow:
    """Stub exposing the three accessors grouping reads."""

    name: str
    entry: str
    control: List[str] = field(default_factory=list)
    data: List[str] = field(default_factory=list)

    def get_entry_node_id(self) -> str:
        return self.entry

    def get_control_node_ids(self) -> List[str]:
        return list(self.control)

    def get_all_nodes(self) -> List[_Node]:
        return [_Node(n) for n in [self.entry, *self.control, *self.data]]


def _names(groups) -> List[List[str]]:
    return [[f.name for f in g] for g in groups]


def test_disjoint_flows_get_one_group_each():
    flows = [_Flow("A", "ea", ["a1"]), _Flow("B", "eb", ["b1"]), _Flow("C", "ec", ["c1"])]
    groups = group_flows(flows)
    assert len(groups) == 3
    assert _names(groups) == [["A"], ["B"], ["C"]]


def test_shared_control_node_merges():
    flows = [_Flow("A", "ea", ["x"]), _Flow("B", "eb", ["x"])]
    assert _names(group_flows(flows)) == [["A", "B"]]


def test_shared_data_node_does_not_merge():
    flows = [_Flow("A", "ea", ["a1"], ["s"]), _Flow("B", "eb", ["b1"], ["s"])]
    groups = group_flows(flows)
    assert _names(groups) == [["A"], ["B"]]
    assert shared_data_node_ids(groups) == {"s"}


def test_data_node_shared_inside_one_group_is_not_shared():
    flows = [_Flow("A", "ea", ["x"], ["s"]), _Flow("B", "eb", ["x"], ["s"])]
    groups = group_flows(flows)
    assert _names(groups) == [["A", "B"]]
    assert shared_data_node_ids(groups) == frozenset()


def test_transitive_chain_merges():
    flows = [_Flow("A", "ea", ["x"]), _Flow("B", "eb", ["x", "y"]), _Flow("C", "ec", ["y"])]
    assert _names(group_flows(flows)) == [["A", "B", "C"]]


def test_chain_merge_keeps_input_order_and_first_appearance():
    flows = [
        _Flow("A", "ea", ["x"]),
        _Flow("B", "eb", ["b"]),
        _Flow("C", "ec", ["y"]),
        _Flow("D", "ed", ["x", "y"]),
    ]
    assert _names(group_flows(flows)) == [["A", "C", "D"], ["B"]]


def test_shared_entry_node_merges():
    flows = [_Flow("A", "e", ["a1"]), _Flow("B", "e", ["b1"])]
    assert _names(group_flows(flows)) == [["A", "B"]]
