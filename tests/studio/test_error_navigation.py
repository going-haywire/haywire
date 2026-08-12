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


def test_open_component_reveals_component_source_editor():
    from haybale_studio.editors.component_source_editor import ComponentSourceEditor
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    open_component(err, ctx)

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert published.editor is ComponentSourceEditor


def test_open_component_noop_without_registry_key():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x")
    assert open_component(err, ctx) is False


def test_open_component_source_sets_active_component_and_reveals():
    from haybale_studio.editors.component_source_editor import ComponentSourceEditor
    from haybale_studio.editors.error_navigation import open_component_source

    ctx = MagicMock()
    open_component_source("lib:node:Foo", ctx)

    assert ctx.active_component == "lib:node:Foo"
    ctx.session.publish.assert_called_once()
    assert ctx.session.publish.call_args[0][0].editor is ComponentSourceEditor


def test_open_component_docs_sets_active_component_and_reveals():
    from haybale_studio.editors.component_docs_editor import ComponentDocsEditor
    from haybale_studio.editors.error_navigation import open_component_docs

    ctx = MagicMock()
    open_component_docs("lib:widget:Bar", ctx)

    assert ctx.active_component == "lib:widget:Bar"
    ctx.session.publish.assert_called_once()
    assert ctx.session.publish.call_args[0][0].editor is ComponentDocsEditor


def test_open_component_docs_and_source_reveal_different_editors():
    """The two shortcuts must not collapse onto the same editor — that is the
    whole point of offering both on a component row."""
    from haybale_studio.editors.error_navigation import open_component_docs, open_component_source

    docs_ctx, source_ctx = MagicMock(), MagicMock()
    open_component_docs("lib:node:Foo", docs_ctx)
    open_component_source("lib:node:Foo", source_ctx)

    docs_editor = docs_ctx.session.publish.call_args[0][0].editor
    source_editor = source_ctx.session.publish.call_args[0][0].editor
    assert docs_editor is not source_editor


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
    reveal_instance(err, ctx)
    ctx.session.publish.assert_not_called()


def test_reveal_instance_publishes_reveal_graph_instance_for_node():
    from haybale_studio.editors.error_navigation import reveal_instance

    ctx = MagicMock()
    err = HaywireException.create("x")
    err.enrich(graph_id="webcam", node_id="n1")

    reveal_instance(err, ctx)

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert published.graph_id == "webcam"
    assert published.node_id == "n1"
    assert published.edge_id is None


def test_reveal_instance_publishes_reveal_graph_instance_for_edge():
    from haybale_studio.editors.error_navigation import reveal_instance

    ctx = MagicMock()
    err = HaywireException.create("x")
    err.enrich(graph_id="webcam", edge_id="edge::o@a>>i@b")

    reveal_instance(err, ctx)

    published = ctx.session.publish.call_args[0][0]
    assert published.graph_id == "webcam"
    assert published.edge_id == "edge::o@a>>i@b"
    assert published.node_id is None
