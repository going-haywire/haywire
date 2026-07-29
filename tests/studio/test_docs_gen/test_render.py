from haywire_studio.docs_gen.model import ComponentRecord, LibraryDoc
from haywire_studio.docs_gen.render import doc_filename, render_quickref, render_overview


def _doc():
    visible = ComponentRecord(
        registry_key="lib:node:resize",
        kind="node",
        library_id="lib",
        label="Resize",
        description="Resize an image",
        deprecation="",
        hidden=False,
        search_tags=["image"],
        menu="image/ops",
        docstring="",
        ports=[],
        settings=[],
        extra={},
    )
    hidden = ComponentRecord(
        registry_key="lib:node:reroute",
        kind="node",
        library_id="lib",
        label="Reroute",
        description="internal",
        deprecation="",
        hidden=True,
        search_tags=[],
        menu="",
        docstring="",
        ports=[],
        settings=[],
        extra={},
    )
    return LibraryDoc("lib", "Lib", "1.0.0", "A lib", [visible, hidden])


def test_doc_filename_replaces_colons():
    assert doc_filename("lib:node:resize") == "lib.node.resize.md"


def test_quickref_lists_registry_keys_and_excludes_hidden():
    out = render_quickref(_doc())
    assert "lib:node:resize" in out  # agents key on registry_key
    assert "lib:node:reroute" not in out  # hidden excluded


def test_overview_uses_labels_not_keys_and_excludes_hidden():
    out = render_overview(_doc())
    assert "Resize" in out  # humans see labels
    assert "lib:node:resize" not in out  # keys are agent-only
    assert "Reroute" not in out  # hidden excluded
