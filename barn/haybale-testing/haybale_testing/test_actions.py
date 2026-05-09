"""Test-specific action Protocols.

Mirror the structure of production ContextMenuActions but with
test-specific names so test fixtures appear only when test-specific
hosts (which structurally satisfy these Protocols) query them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TestCanvasContextActions(Protocol):
    __test__: bool = False  # not a pytest test class

    def test_create_node_at_click(self, registry_key: str) -> None: ...


@runtime_checkable
class TestNodeContextActions(Protocol):
    __test__: bool = False

    def test_delete_node(self, node_id: str) -> None: ...
    def test_copy_node(self, node_id: str) -> None: ...
    def test_redraw_node(self, node_id: str) -> None: ...
    def test_revalidate_node(self, node_id: str) -> None: ...
    def test_reset_node(self, node_id: str) -> None: ...


@runtime_checkable
class TestEdgeContextActions(Protocol):
    __test__: bool = False

    def test_delete_edge(self, edge_id: str) -> None: ...
    def test_inspect_edge(self, edge_id: str) -> None: ...


@runtime_checkable
class TestSelectionContextActions(Protocol):
    __test__: bool = False

    def test_copy_selection(self) -> None: ...
    def test_paste_at_click(self) -> None: ...
