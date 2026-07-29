from haywire.core.library.kinds import kind_registry_map, KIND_FOLDERS, canon_area

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
