"""Tests for the GraphContainer protocol shape.

The protocol is a structural contract — anything with the right
attributes and methods satisfies it. These tests pin the shape so
accidental drift gets caught.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from haybale_graph_editor.protocols import GraphContainer


@dataclass
class _DummyContainer:
    """Minimal struct that satisfies GraphContainer structurally."""

    binding_id: str = "id-1"
    editor: object = field(default_factory=object)
    path: Optional[Path] = None
    unsaved: bool = False
    display_name: str = "Dummy"

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        return None


def test_dummy_container_satisfies_protocol():
    """A struct with the right shape is a GraphContainer at runtime."""
    c = _DummyContainer()
    assert isinstance(c, GraphContainer)


def test_missing_save_method_does_not_satisfy_protocol():
    """A struct without save() is not a GraphContainer."""

    @dataclass
    class _NoSave:
        binding_id: str = "x"
        editor: object = field(default_factory=object)
        path: Optional[Path] = None
        unsaved: bool = False
        display_name: str = "x"

    assert not isinstance(_NoSave(), GraphContainer)


def test_protocol_attributes_are_accessible():
    """Every documented attribute can be read off a conforming container."""
    c = _DummyContainer(binding_id="abc", path=Path("/tmp/x.haywire"), unsaved=True)
    assert c.binding_id == "abc"
    assert c.path == Path("/tmp/x.haywire")
    assert c.unsaved is True
    assert c.display_name == "Dummy"
    assert c.editor is not None
    assert c.save() is None
    assert c.save(save_as=Path("/tmp/y.haywire")) is None
