from haywire.core.node.inspector import PortInfo, SettingInfo
from haywire_studio.packaging.docs.model import ComponentRecord, LibraryDoc
from haywire_studio.packaging.docs.render import (
    coverage_report,
    doc_filename,
    render_component,
    render_overview,
    render_quickref,
    render_readme,
)


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


def test_render_component_node_lists_ports():
    rec = ComponentRecord(
        registry_key="lib:node:resize",
        kind="node",
        library_id="lib",
        label="Resize",
        description="Resize an image",
        deprecation="",
        hidden=False,
        search_tags=[],
        menu="",
        docstring="Does the resize.",
        ports=[PortInfo("img", "inlet", "Image", "the image", "data", "lib:type:image", False, "")],
        settings=[],
        extra={},
    )
    out = render_component(rec)
    assert "lib:node:resize" in out
    assert "img" in out
    assert "inlet" in out
    assert "Does the resize." in out  # verbatim docstring


def test_render_component_orders_ports_inlet_config_outlet():
    """Ports render grouped by direction: inlets, then configs, then outlets."""
    rec = ComponentRecord(
        registry_key="lib:node:n",
        kind="node",
        library_id="lib",
        label="N",
        description="",
        deprecation="",
        hidden=False,
        search_tags=[],
        menu="",
        docstring="",
        ports=[
            PortInfo("out1", "outlet", "", "", "data", None, False, ""),
            PortInfo("cfg1", "config", "", "", "data", None, False, ""),
            PortInfo("in1", "inlet", "", "", "data", None, False, ""),
        ],
        settings=[],
        extra={},
    )
    out = render_component(rec)
    assert out.index("in1") < out.index("cfg1") < out.index("out1")


def test_render_component_excludes_props_bag_settings():
    """The framework's `props` bag (NodeProperties: posX, posY, width, ...)
    must never appear in a node's rendered Settings table — it's framework
    chrome, not something the node author wrote, and documenting it would
    drown out (and misrepresent as node-specific) the author's own settings.
    """
    rec = ComponentRecord(
        registry_key="lib:node:resize",
        kind="node",
        library_id="lib",
        label="Resize",
        description="Resize an image",
        deprecation="",
        hidden=False,
        search_tags=[],
        menu="",
        docstring="",
        ports=[],
        settings=[
            SettingInfo(
                name="posX",
                bag="props",
                label="Position X",
                description="framework position",
                category="",
                default=0,
                type_name="int",
                validator_name=None,
                validator_doc=None,
            ),
            SettingInfo(
                name="quality",
                bag="example",
                label="Quality",
                description="resize quality",
                category="",
                default="high",
                type_name="str",
                validator_name=None,
                validator_doc=None,
            ),
        ],
        extra={},
    )
    out = render_component(rec)
    assert "quality" in out  # author's own setting is documented
    assert "posX" not in out  # framework props bag is excluded entirely


def test_coverage_flags_missing_description():
    rec = ComponentRecord(
        registry_key="lib:type:x",
        kind="type",
        library_id="lib",
        label="X",
        description="",
        deprecation="",
        hidden=False,
        search_tags=[],
        menu="",
        docstring="",
        ports=[],
        settings=[],
        extra={},
    )
    doc = LibraryDoc("lib", "Lib", "1.0.0", "", [rec])
    report = coverage_report(doc)
    assert any("lib:type:x" in line for line in report)


MARKER = (
    "<!-- marketstall:share-url:start -->\n"
    "`https://example.com/subscribe`\n"
    "<!-- marketstall:share-url:end -->"
)


def test_readme_prepends_notes_and_preserves_marker_block():
    doc = LibraryDoc("lib", "Lib", "1.0.0", "A lib", [])
    existing = f"# old\n\n{MARKER}\n\nold catalog"
    out = render_readme(doc, notes="## Why this lib\nBecause.", existing_readme=existing)
    assert "## Why this lib" in out  # NOTES prepended
    assert "https://example.com/subscribe" in out  # marker content survived
    assert out.count("marketstall:share-url:start") == 1  # exactly one block


def test_readme_inserts_placeholder_marker_when_none_exists():
    doc = LibraryDoc("lib", "Lib", "1.0.0", "A lib", [])
    out = render_readme(doc, notes="", existing_readme=None)
    assert "marketstall:share-url:start" in out


def test_readme_inserts_placeholder_marker_when_existing_readme_lacks_it():
    doc = LibraryDoc("lib", "Lib", "1.0.0", "A lib", [])
    existing = "# Some README\n\nno marker here"
    out = render_readme(doc, notes="", existing_readme=existing)
    assert "marketstall:share-url:start" in out
    assert "Subscribe URL not yet published" in out
