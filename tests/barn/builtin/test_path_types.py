import pytest

from haywire.core.volumes import VolumePath

pytestmark = pytest.mark.integration


def _types(library_system):
    reg = library_system.get_type_registry()
    return (
        reg.get_type_class("haywire-core:type:PATH"),
        reg.get_type_class("haywire-core:type:FILE_PATH"),
        reg.get_type_class("haywire-core:type:FOLDER_PATH"),
    )


def test_types_register(library_system):
    for cls in _types(library_system):
        assert cls is not None


def test_round_trip_keeps_relative_verbatim(library_system):
    path_cls, file_cls, folder_cls = _types(library_system)
    vp = VolumePath("models", "a\\b/../c.png")
    for cls in (path_cls, file_cls, folder_cls):
        data = cls(vp).to_dict()
        assert data == {"value": {"volume": "models", "relative": "a\\b/../c.png"}}
        assert cls.from_dict(data) == vp


def test_default_is_project_root(library_system):
    path_cls, _, _ = _types(library_system)
    assert path_cls.class_identity.default == {"value": {"volume": "project", "relative": ""}}
    assert path_cls.from_dict({"value": {}}) == VolumePath("project", "")


def test_hierarchy(library_system):
    path_cls, file_cls, folder_cls = _types(library_system)
    assert issubclass(file_cls, path_cls)
    assert issubclass(folder_cls, path_cls)
    assert not issubclass(path_cls, file_cls)
    assert not issubclass(file_cls, folder_cls)


def test_widget_modes(library_system):
    from haywire.barn.builtin import widget_keys

    path_cls, file_cls, folder_cls = _types(library_system)
    for cls in (path_cls, file_cls, folder_cls):
        assert cls.class_identity.widget_key == widget_keys.PATH_WIDGET
    assert file_cls.class_identity.widget_config["properties"]["mode"] == "file"
    assert folder_cls.class_identity.widget_config["properties"]["mode"] == "folder"
