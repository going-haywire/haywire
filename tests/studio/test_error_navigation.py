"""Error → component/file navigation helpers (studio)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.unit


def test_open_component_sets_active_component():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    assert open_component(err, ctx) is True
    assert ctx.active_component == "lib:node:Foo"


def test_open_component_noop_without_registry_key():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x")
    assert open_component(err, ctx) is False


def test_open_file_in_studio_reveals_code_editor():
    from haybale_studio.editors.error_navigation import open_file_in_studio

    ctx = MagicMock()
    open_file_in_studio("/tmp/thing.py", 12, ctx)
    assert ctx.active_file == Path("/tmp/thing.py")
    # A Reveal was published on the session.
    assert ctx.session.publish.call_count == 1
    published = ctx.session.publish.call_args[0][0]
    assert published.binding_id == "/tmp/thing.py"


def test_reveal_instance_noop_when_cannot_reveal():
    from haybale_studio.editors.error_navigation import reveal_instance

    ctx = MagicMock()
    err = HaywireException.create("x")  # no graph_id/node_id
    assert reveal_instance(err, ctx) is False
    ctx.session.publish.assert_not_called()


def test_reveal_instance_noop_when_graph_gone(monkeypatch):
    from haybale_studio.editors.error_navigation import reveal_instance

    ctx = MagicMock()
    # HaystackState.get_by_id returns None → instance gone.
    ctx.app_data.__getitem__.return_value.get_by_id.return_value = None
    err = HaywireException.create("x")
    err.enrich(graph_id="/tmp/g.haywire", node_id="n1")
    assert reveal_instance(err, ctx) is False


def test_reveal_instance_selects_node(monkeypatch):
    from haybale_studio.editors.error_navigation import reveal_instance

    ctx = MagicMock()
    entry = MagicMock()
    node_wrapper = MagicMock()
    entry.graph.get_node_wrapper.return_value = node_wrapper
    ctx.app_data.__getitem__.return_value.get_by_id.return_value = entry

    err = HaywireException.create("x")
    err.enrich(graph_id="/tmp/g.haywire", node_id="n1")

    assert reveal_instance(err, ctx) is True
    entry.graph.get_node_wrapper.assert_called_once_with("n1")
    # active_node was assigned the resolved wrapper.
    assert ctx.data.__getitem__.return_value.active_node is node_wrapper
    # Reveal + SelectionMoved published (2 publishes).
    assert ctx.session.publish.call_count == 2
