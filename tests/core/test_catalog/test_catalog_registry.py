"""``CatalogRegistry``: an OpenModelDB-shaped JSON file becomes a catalog entry."""

import json
import copy

import pytest

HASH_A = "a" * 64
HASH_B = "b" * 64

OMDB_DEMO = {
    "name": "4x Demo",
    "author": "someone",
    "license": "CC-BY-4.0",
    "tags": ["photo"],
    "description": "A demo upscaler",
    "date": "2024-01-01",
    "architecture": "esrgan",
    "size": ["64nf", "23nb"],
    "scale": 4,
    "inputChannels": 3,
    "outputChannels": 3,
    "resources": [
        {
            "platform": "pytorch",
            "type": "pth",
            "size": 67025055,
            "sha256": HASH_A,
            "urls": ["https://a.example/4x.pth", "https://b.example/4x.pth"],
        }
    ],
}


def write(path, document):
    path.write_text(json.dumps(document))
    return path


def lib_identity(folder):
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(label="X", name="haybale-x", folder_path=str(folder), module_name="haybale_x")


@pytest.fixture
def catalog_registry():
    from haywire.core.catalog import CatalogRegistry

    return CatalogRegistry()


@pytest.fixture
def identity(tmp_path):
    return lib_identity(tmp_path)


@pytest.mark.unit
def test_openmodeldb_file_parses_unchanged(tmp_path, catalog_registry, identity):
    doc = copy.deepcopy(OMDB_DEMO)
    doc["size"] = None
    write(tmp_path / "4x-Demo.json", doc)
    catalog_registry.add_folder(str(tmp_path), identity)

    entry = catalog_registry.entry("haybale-x:catalog:4x-Demo")
    assert entry is not None
    assert entry.architecture == "esrgan"
    assert entry.scale == 4
    assert entry.input_channels == 3
    assert entry.output_channels == 3
    assert entry.tags == ["photo"]
    (res,) = entry.resources
    assert res.tags() == {"platform": "pytorch", "type": "pth"}
    assert res.files[0].urls == ("https://a.example/4x.pth", "https://b.example/4x.pth")
    assert res.files[0].path == ""
    assert res.files[0].sha256 == HASH_A
    assert res.variant_name() == "pytorch-pth"
    assert not res.is_bundle
    assert res.total_size == 67025055
    assert entry.class_identity.registry_key == "haybale-x:catalog:4x-Demo"
    assert entry.class_library is identity
    assert entry.path == tmp_path / "4x-Demo.json"
    assert entry.fields()["architecture"] == "esrgan"
    assert set(entry.fields()) == {
        "architecture",
        "scale",
        "purpose",
        "tags",
        "license",
        "input_channels",
        "output_channels",
    }
    assert catalog_registry.entries() == [entry]


@pytest.mark.unit
def test_variant_tags_and_bundle(tmp_path, catalog_registry, identity):
    doc = copy.deepcopy(OMDB_DEMO)
    doc["purpose"] = ["upscale"]
    doc["resources"] = [
        {
            "platform": "pytorch",
            "type": "pth",
            "backend": "torch",
            "precision": "fp16",
            "sha256": HASH_A,
            "urls": ["u"],
        },
        {
            "platform": "onnx",
            "type": "onnx",
            "files": [
                {"path": "a.onnx", "sha256": HASH_A, "size": 10, "urls": ["u1"]},
                {"path": "b.bin", "sha256": HASH_B, "size": 32, "urls": ["u2"]},
            ],
        },
        {"urls": ["x"]},
    ]
    write(tmp_path / "multi.json", doc)
    catalog_registry.add_folder(str(tmp_path), identity)

    entry = catalog_registry.entry("haybale-x:catalog:multi")
    assert entry is not None
    flat, bundle, bare = entry.resources
    assert flat.variant_name() == "pytorch-pth-torch-fp16"
    assert flat.tags() == {"platform": "pytorch", "type": "pth", "backend": "torch", "precision": "fp16"}
    assert bundle.is_bundle
    assert bundle.total_size == 42
    assert bundle.sha256 is None
    assert bundle.files[1].path == "b.bin"
    assert bare.tags() == {}
    assert bare.variant_name() == "default"
    assert entry.fields()["purpose"] == ["upscale"]


def _failed(registry, key):
    from haywire.core.registry.lifecycle_event import LifeCycleEventType

    event = registry.get_lastevent(key)
    return event is not None and event.event_type is LifeCycleEventType.CLASS_RELOAD_FAILED


@pytest.mark.unit
def test_bad_sha256_is_refused_and_keeps_previous(tmp_path, catalog_registry, identity):
    path = write(tmp_path / "Demo.json", OMDB_DEMO)
    catalog_registry.add_folder(str(tmp_path), identity)
    before = catalog_registry.entry("haybale-x:catalog:Demo")
    assert before is not None

    bad: dict = copy.deepcopy(OMDB_DEMO)
    bad["name"] = "changed"
    bad["resources"][0]["sha256"] = "xyz"
    write(path, bad)
    catalog_registry.register_file(str(path), identity)

    assert catalog_registry.entry("haybale-x:catalog:Demo") is before
    assert _failed(catalog_registry, "haybale-x:catalog:Demo")
    assert before.name == "4x Demo"


@pytest.mark.unit
@pytest.mark.parametrize(
    "doc",
    [
        [1, 2],
        {"name": "n"},
        {"name": "n", "resources": []},
        {"name": "n", "resources": [{"platform": "pytorch", "type": "pth"}]},
        {"name": "n", "resources": [{"sha256": "abc", "urls": ["u"]}]},
    ],
)
def test_malformed_documents_are_refused(tmp_path, catalog_registry, identity, doc):
    write(tmp_path / "Bad.json", doc)
    catalog_registry.add_folder(str(tmp_path), identity)

    assert catalog_registry.entry("haybale-x:catalog:Bad") is None
    assert _failed(catalog_registry, "haybale-x:catalog:Bad")
    assert catalog_registry.entries() == []


@pytest.mark.unit
def test_empty_resources_refused_queues_failure(tmp_path, catalog_registry, identity):
    write(tmp_path / "Empty.json", {"name": "n", "resources": []})
    catalog_registry.add_folder(str(tmp_path), identity)

    assert catalog_registry.entry("haybale-x:catalog:Empty") is None
    assert _failed(catalog_registry, "haybale-x:catalog:Empty")


@pytest.mark.unit
def test_bad_stem_is_skipped(tmp_path, catalog_registry, identity):
    write(tmp_path / "bad stem.json", OMDB_DEMO)
    catalog_registry.add_folder(str(tmp_path), identity)

    assert catalog_registry.entries() == []


@pytest.mark.unit
def test_kind_maps_know_catalog():
    from haywire.core.library.kinds import KIND_FOLDERS, canon_area, kind_registry_map
    from haywire.core.catalog import CatalogRegistry

    assert kind_registry_map()["catalog"] is CatalogRegistry
    assert KIND_FOLDERS["catalog"] == "catalog"
    assert canon_area("catalog") == "catalogs"


@pytest.mark.unit
def test_models_scan_after_macros():
    from haywire.core.library.base import BaseLibrary

    assert BaseLibrary._REGISTRY_SCAN_PRIORITY["CatalogRegistry"] == 76


@pytest.mark.unit
def test_injector_provides_the_ambient_singleton(test_injector):
    from haywire.core.di.context import get_catalog_registry
    from haywire.core.catalog import CatalogRegistry

    registry = test_injector.get(CatalogRegistry)

    assert get_catalog_registry() is registry
    assert test_injector.get(CatalogRegistry) is registry


@pytest.mark.integration
def test_library_gets_the_registry(library_system):
    from haywire.core.catalog import CatalogRegistry

    singleton = library_system.get_catalog_registry()
    registry = library_system.get_library_registry()
    assert registry._class_registries[CatalogRegistry] is singleton
    libs = [registry._libraries[name] for name in registry.list_names()]
    assert libs
    assert all(lib.get_registry(CatalogRegistry) is singleton for lib in libs if lib is not None)


def test_a_catalog_key_resolves_like_any_component(library_system):
    """The component docs and source editors find a catalog entry by its key."""
    key = "haybale-example:catalog:4x-Compact-Pretrain"

    assert library_system.get_registry_for_key(key) is library_system.get_catalog_registry()
    entry = library_system.lookup_component_class(key)
    assert entry is not None
    assert entry.class_identity.registry_key == key
    assert entry.path.name == "4x-Compact-Pretrain.json"
