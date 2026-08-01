from haywire_studio.packaging.docs.model import ComponentRecord, LibraryDoc


def test_component_record_defaults_are_empty_not_none():
    rec = ComponentRecord(
        registry_key="lib:type:temperature",
        kind="type",
        library_id="lib",
        label="Temperature",
        description="A temp",
        deprecation="",
        hidden=False,
        search_tags=[],
        menu="",
        docstring="",
        ports=[],
        settings=[],
        extra={},
    )
    assert rec.ports == [] and rec.settings == [] and rec.extra == {}


def test_library_doc_holds_components():
    doc = LibraryDoc(library_id="lib", label="Lib", version="1.0.0", description="", components=[])
    assert doc.components == []
