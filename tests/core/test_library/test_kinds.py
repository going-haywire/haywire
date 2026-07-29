from haywire.core.library.kinds import kind_registry_map, KIND_FOLDERS, canon_area, doc_filename

EXPECTED = {
    "node",
    "type",
    "adapter",
    "widget",
    "skin",
    "setting",
    "theme",
    "panel",
    "editor",
    "state",
    "farmhand",
}


def test_kind_map_covers_all_eleven_kinds():
    assert set(kind_registry_map()) == EXPECTED
    assert set(KIND_FOLDERS) == EXPECTED


def test_canon_area_handles_irregular_kinds():
    assert canon_area("type") == "datatypes"  # not "types"
    assert canon_area("state") == "states"
    assert canon_area("node") == "nodes"


def test_doc_filename_replaces_all_colons():
    assert doc_filename("lib:node:resize_image") == "lib.node.resize_image.md"
    assert doc_filename("lib:widget:x") == "lib.widget.x.md"
