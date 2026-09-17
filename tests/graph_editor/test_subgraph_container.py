"""SubgraphContainer: synthetic binding_id, and everything about the file delegating."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haybale_graph_editor.protocols import GraphContainer, SubgraphContainer

pytestmark = pytest.mark.unit


class _FakeHost(GraphContainer):
    """A document container, standing in for a haystack entry."""

    def __init__(self, binding_id: str = "/tmp/graphs/main.haywire", unsaved: bool = False):
        self._binding_id = binding_id
        self.editor = MagicMock()
        self.path = Path(binding_id)
        self._unsaved = unsaved
        self.save_calls: list[Path | None] = []
        self.save_result: str | None = None

    @property
    def binding_id(self) -> str:
        return self._binding_id

    @property
    def display_name(self) -> str:
        return "main.haywire"

    @property
    def unsaved(self) -> bool:  # type: ignore[override]
        return self._unsaved

    def save(self, save_as: Path | None = None) -> str | None:
        self.save_calls.append(save_as)
        return self.save_result


def _definition(key: str = "sg_1", label: str = "Filter"):
    definition = MagicMock()
    definition.key = key
    definition.label = label
    return definition


def _container(host: GraphContainer | None = None, **kwargs) -> SubgraphContainer:
    return SubgraphContainer(host or _FakeHost(), _definition(**kwargs), MagicMock())


class TestIdentity:
    def test_the_binding_id_joins_the_host_and_the_subgraph_key(self):
        container = _container(_FakeHost("/tmp/g.haywire"), key="sg_a")

        assert container.binding_id == "/tmp/g.haywire#sg_a"

    def test_the_display_name_is_the_subgraphs_label(self):
        assert _container(label="Smoothing").display_name == "Smoothing"

    def test_nesting_stacks_the_keys(self):
        """A Group inside a Group is addressable, and says where it sits."""
        outer = _container(_FakeHost("/tmp/g.haywire"), key="sg_outer")
        inner = SubgraphContainer(outer, _definition(key="sg_inner"), MagicMock())

        assert inner.binding_id == "/tmp/g.haywire#sg_outer#sg_inner"

    def test_root_host_walks_past_every_subgraph(self):
        host = _FakeHost()
        outer = SubgraphContainer(host, _definition(key="a"), MagicMock())
        inner = SubgraphContainer(outer, _definition(key="b"), MagicMock())

        assert inner.root_host is host
        assert outer.root_host is host

    def test_the_root_host_of_a_document_is_itself(self):
        host = _FakeHost()

        assert SubgraphContainer(host, _definition(), MagicMock()).root_host is host


class TestSavingDelegates:
    """A Group belongs to the host file, so nothing about saving is its own."""

    def test_the_path_is_the_hosts(self):
        host = _FakeHost("/tmp/graphs/main.haywire")

        assert _container(host).path == host.path

    def test_the_dirty_state_is_the_hosts(self):
        clean = _FakeHost(unsaved=False)
        dirty = _FakeHost(unsaved=True)

        assert _container(clean).unsaved is False
        assert _container(dirty).unsaved is True

    def test_save_goes_to_the_host(self):
        host = _FakeHost()
        container = _container(host)

        container.save()

        assert host.save_calls == [None]

    def test_save_as_passes_the_path_through(self):
        host = _FakeHost()
        target = Path("/tmp/graphs/other.haywire")

        _container(host).save(save_as=target)

        assert host.save_calls == [target]

    def test_save_returns_the_hosts_new_binding_id(self):
        host = _FakeHost()
        host.save_result = "/tmp/graphs/renamed.haywire"

        assert _container(host).save() == "/tmp/graphs/renamed.haywire"

    def test_a_nested_save_reaches_the_document_through_the_chain(self):
        host = _FakeHost()
        outer = SubgraphContainer(host, _definition(key="a"), MagicMock())
        inner = SubgraphContainer(outer, _definition(key="b"), MagicMock())

        inner.save()

        assert host.save_calls == [None]


class TestEditor:
    def test_it_owns_an_editor_over_the_subgraph(self):
        definition = _definition()
        container = SubgraphContainer(_FakeHost(), definition, MagicMock())

        assert container.editor.graph is definition

    def test_the_editor_is_not_the_hosts(self):
        host = _FakeHost()
        container = _container(host)

        assert container.editor is not host.editor

    def test_it_records_on_the_hosts_undo_history(self):
        """An edit inside a Group is an edit to the file, and undoes with the rest of it."""
        host = _FakeHost()

        assert _container(host).editor.history_manager is host.editor.history_manager

    def test_a_nested_subgraph_reaches_the_documents_history_through_the_chain(self):
        host = _FakeHost()
        outer = SubgraphContainer(host, _definition(key="a"), MagicMock())
        inner = SubgraphContainer(outer, _definition(key="b"), MagicMock())

        assert inner.editor.history_manager is host.editor.history_manager
