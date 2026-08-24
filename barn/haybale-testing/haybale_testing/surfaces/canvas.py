"""Test-only canvas menu surface."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from haywire.ui.surface import Surface


@runtime_checkable
class TestCanvasActions(Protocol):
    __test__: bool = False  # not a pytest test class

    def test_create_node_at_click(self, registry_key: str) -> None: ...


class TestCanvasMenu(Surface):
    __test__: bool = False

    id = "test_canvas"
    order = 100
    provides = TestCanvasActions
