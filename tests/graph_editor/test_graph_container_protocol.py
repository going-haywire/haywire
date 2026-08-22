"""Tests for the GraphContainer base class shape.

GraphContainer is an ABC — a source library subclasses it to host a graph
in GraphEditor. These tests pin the contract so accidental drift gets
caught: which members are abstract, and that a dataclass subclass (the
shape GraphEntry uses) can actually be instantiated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pytest

from haybale_graph_editor.protocols import GraphContainer


@dataclass
class _DummyContainer(GraphContainer):
    """Minimal dataclass subclass — mirrors how GraphEntry inherits."""

    editor: Any = field(default_factory=object)
    path: Optional[Path] = None
    unsaved: bool = False

    @property
    def binding_id(self) -> str:
        return str(self.path) if self.path is not None else "unsaved"

    @property
    def display_name(self) -> str:
        return self.path.stem if self.path is not None else "Untitled"

    def save(self, save_as: Optional[Path] = None) -> Optional[str]:
        return None


def test_dataclass_subclass_is_instantiable():
    """A dataclass subclass supplying the abstract members constructs.

    Guards the ABC/dataclass trap: ``editor``/``path``/``unsaved`` must stay
    plain annotations on the base. Were they ``@abstractmethod`` properties,
    a dataclass field would NOT clear ``__abstractmethods__`` and every
    container would raise TypeError at construction.
    """
    c = _DummyContainer()
    assert isinstance(c, GraphContainer)


def test_subclass_missing_abstract_member_cannot_instantiate():
    """Omitting an abstract member is caught at construction."""

    class _NoSave(GraphContainer):
        editor: Any = object()
        path = None
        unsaved = False

        @property
        def binding_id(self) -> str:
            return "x"

        @property
        def display_name(self) -> str:
            return "x"

    with pytest.raises(TypeError, match="abstract"):
        _NoSave()  # type: ignore[abstract]


def test_container_attributes_are_accessible():
    """Every documented attribute can be read off a conforming container."""
    c = _DummyContainer(path=Path("/tmp/x.haywire"), unsaved=True)
    assert c.binding_id == "/tmp/x.haywire"
    assert c.path == Path("/tmp/x.haywire")
    assert c.unsaved is True
    assert c.display_name == "x"
    assert c.editor is not None
    assert c.save() is None
    assert c.save(save_as=Path("/tmp/y.haywire")) is None


def test_graph_entry_is_a_graph_container():
    """The real implementation inherits nominally, not just structurally."""
    from haybale_haystack.graph_entry import GraphEntry

    assert issubclass(GraphEntry, GraphContainer)
