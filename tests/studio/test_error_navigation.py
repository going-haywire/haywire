"""Error → component/file navigation helpers (studio)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from haywire.core.errors.haywire_exception import HaywireException

pytestmark = pytest.mark.unit


def test_open_component_publishes_reveal_component_source():
    from haybale_studio.editors.error_navigation import open_component
    from haywire.core.signals import RevealComponentSource

    ctx = MagicMock()
    err = HaywireException.create("x", registry_key="lib:node:Foo")
    assert open_component(err, ctx) is True

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert isinstance(published, RevealComponentSource)
    assert published.registry_key == "lib:node:Foo"


def test_open_component_noop_without_registry_key():
    from haybale_studio.editors.error_navigation import open_component

    ctx = MagicMock()
    err = HaywireException.create("x")
    assert open_component(err, ctx) is False
    ctx.session.publish.assert_not_called()


def test_open_component_source_publishes_reveal_component_source():
    from haybale_studio.editors.error_navigation import open_component_source
    from haywire.core.signals import RevealComponentSource

    ctx = MagicMock()
    open_component_source("lib:node:Foo", ctx)

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert isinstance(published, RevealComponentSource)
    assert published.registry_key == "lib:node:Foo"


def test_open_component_docs_publishes_reveal_component_docs():
    from haybale_studio.editors.error_navigation import open_component_docs
    from haywire.core.signals import RevealComponentDocs

    ctx = MagicMock()
    open_component_docs("lib:widget:Bar", ctx)

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert isinstance(published, RevealComponentDocs)
    assert published.registry_key == "lib:widget:Bar"


def test_navigation_helpers_write_no_session_state():
    """The claim rule lives in the answering editor's @reveal_on hook, which
    runs before the reveal. A helper that ALSO wrote context would be a second
    copy of that rule, free to disagree — which is exactly how open_file_in_studio
    used to bypass CodeEditor's extension veto."""
    from haybale_studio.editors.error_navigation import (
        open_component_docs,
        open_component_source,
        open_file_in_studio,
    )

    for call in (
        lambda c: open_component_source("lib:node:Foo", c),
        lambda c: open_component_docs("lib:node:Foo", c),
        lambda c: open_file_in_studio("/tmp/thing.py", 12, c),
    ):
        ctx = MagicMock()
        ctx.active_component = None
        ctx.active_file = None
        call(ctx)
        assert ctx.active_component is None
        assert ctx.active_file is None


def test_open_component_docs_and_source_are_distinct_signals():
    """The two shortcuts must not collapse onto one signal — @reveal_on
    dispatches on the type, and that is what routes docs and source to two
    different editors."""
    from haybale_studio.editors.error_navigation import open_component_docs, open_component_source

    docs_ctx, source_ctx = MagicMock(), MagicMock()
    open_component_docs("lib:node:Foo", docs_ctx)
    open_component_source("lib:node:Foo", source_ctx)

    docs_signal = docs_ctx.session.publish.call_args[0][0]
    source_signal = source_ctx.session.publish.call_args[0][0]
    assert type(docs_signal) is not type(source_signal)


def test_open_file_in_studio_publishes_reveal_source():
    """Names no editor, so CodeEditor's hook — not this helper — decides whether
    the path is editable."""
    from haybale_studio.editors.error_navigation import open_file_in_studio
    from haywire.core.signals import RevealSource

    ctx = MagicMock()
    open_file_in_studio("/tmp/thing.py", 12, ctx)

    ctx.session.publish.assert_called_once()
    published = ctx.session.publish.call_args[0][0]
    assert isinstance(published, RevealSource)
    assert published.binding_id == "/tmp/thing.py"
    assert published.label == "thing.py"


def test_open_file_in_studio_routes_a_vetoed_extension_to_the_hook():
    """The bug this conversion fixed: a non-editable path used to be revealed
    into the CodeEditor directly, bypassing the veto. Now it travels as a
    RevealSource that CodeEditor declines."""
    from haybale_studio.editors.code_editor import CodeEditor
    from haybale_studio.editors.error_navigation import open_file_in_studio

    ctx = MagicMock()
    open_file_in_studio("/tmp/thing.bin", None, ctx)
    published = ctx.session.publish.call_args[0][0]

    hook_ctx = MagicMock()
    hook_ctx.active_file = None
    assert CodeEditor._on_reveal_source(hook_ctx, published) is False
    assert hook_ctx.active_file is None


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
    err.enrich(graph_id="webcam", edge_id="a[o]->b[i]")

    reveal_instance(err, ctx)

    published = ctx.session.publish.call_args[0][0]
    assert published.graph_id == "webcam"
    assert published.edge_id == "a[o]->b[i]"
    assert published.node_id is None


# ---------------------------------------------------------------------------
# @reveal_on — the seam that keeps core off the barn libraries
#
# Core UI can know a registry key or a path, but not an editor class: naming
# one would mean haywire-core importing a barn library, the dependency arrow
# backwards (.insights/project_app_library_dependency_direction.md). So core
# publishes a bare RevealSignal and the editor CLASS that declared @reveal_on
# claims it. Class-level, so it works with no instance alive — which is the
# whole reason CodeEditor (opens=ON_PAYLOAD) can answer at all.
# ---------------------------------------------------------------------------


def test_component_source_editor_declares_reveal_on():
    from haybale_studio.editors.component_source_editor import ComponentSourceEditor
    from haywire.core.session.handlers import discover_reveal_handlers
    from haywire.core.signals import RevealComponentSource

    assert discover_reveal_handlers(ComponentSourceEditor) == {
        RevealComponentSource: "_on_reveal_component_source"
    }


def test_component_docs_editor_declares_reveal_on():
    from haybale_studio.editors.component_docs_editor import ComponentDocsEditor
    from haywire.core.session.handlers import discover_reveal_handlers
    from haywire.core.signals import RevealComponentDocs

    assert discover_reveal_handlers(ComponentDocsEditor) == {
        RevealComponentDocs: "_on_reveal_component_docs"
    }


def test_component_docs_hook_points_the_viewer_and_proceeds():
    from haybale_studio.editors.component_docs_editor import ComponentDocsEditor
    from haywire.core.signals import RevealComponentDocs

    ctx = MagicMock()
    proceed = ComponentDocsEditor._on_reveal_component_docs(
        ctx, RevealComponentDocs(registry_key="lib:widget:Bar")
    )

    assert proceed is True
    assert ctx.active_component == "lib:widget:Bar"
    ctx.session.publish.assert_not_called()


def test_code_editor_declares_reveal_on():
    from haybale_studio.editors.code_editor import CodeEditor
    from haywire.core.session.handlers import discover_reveal_handlers
    from haywire.core.signals import RevealSource

    assert discover_reveal_handlers(CodeEditor) == {RevealSource: "_on_reveal_source"}


def test_component_source_hook_points_the_viewer_and_proceeds():
    """The hook writes session state BEFORE the framework reveals, so the
    revealed editor draws the component asked for rather than the previous one."""
    from haybale_studio.editors.component_source_editor import ComponentSourceEditor
    from haywire.core.signals import RevealComponentSource

    ctx = MagicMock()
    proceed = ComponentSourceEditor._on_reveal_component_source(
        ctx, RevealComponentSource(registry_key="lib:setting:Foo")
    )

    assert proceed is True
    assert ctx.active_component == "lib:setting:Foo"
    # The hook does NOT publish — the shell performs the reveal. This is the
    # roundtrip that @reveal_on removed.
    ctx.session.publish.assert_not_called()


def test_code_editor_hook_claims_an_editable_file():
    from haybale_studio.editors.code_editor import CodeEditor
    from haywire.core.signals import RevealSource

    ctx = MagicMock()
    proceed = CodeEditor._on_reveal_source(ctx, RevealSource(binding_id="/tmp/thing.py"))

    assert proceed is True
    assert ctx.active_file == Path("/tmp/thing.py")
    ctx.session.publish.assert_not_called()


def test_code_editor_hook_vetoes_an_extension_it_cannot_edit():
    """A veto means "not mine" — and it must leave no half-applied navigation
    behind, so active_file stays untouched."""
    from haybale_studio.editors.code_editor import CodeEditor
    from haywire.core.signals import RevealSource

    ctx = MagicMock()
    ctx.active_file = None
    proceed = CodeEditor._on_reveal_source(ctx, RevealSource(binding_id="/tmp/thing.bin"))

    assert proceed is False
    assert ctx.active_file is None


def test_reveal_source_binding_id_is_the_path_and_is_required():
    """RevealSource adds no path field: a file editor binds tabs BY path, so
    binding_id already is the path. Carrying both would let them disagree."""
    import dataclasses

    from haywire.core.signals import RevealSource

    assert {f.name for f in dataclasses.fields(RevealSource)} == {"binding_id", "label"}
    with pytest.raises(TypeError):
        RevealSource()  # type: ignore[call-arg]


def test_reveal_on_rejects_a_signal_that_is_not_a_reveal():
    """Decoration-time guard: a signal with no binding_id/label cannot
    describe a reveal, and saying so at import beats a silent no-op later."""
    from haywire.core.session.handlers import reveal_on
    from haywire.core.signals import SelectionMoved

    with pytest.raises(TypeError, match="RevealSignal"):

        @reveal_on(SelectionMoved)  # type: ignore[misc]
        @classmethod
        def _hook(cls, ctx, event):  # pragma: no cover
            return True
