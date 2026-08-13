import pytest


@pytest.mark.integration
def test_builtin_types_resolve_through_registry(library_system):
    """After full init, the type registry resolves haywire-core:type:* keys."""
    reg = library_system.get_type_registry()
    assert reg.get_type_class("haywire-core:type:INT") is not None
    assert reg.get_type_class("haywire-core:type:FLOAT") is not None
    assert reg.get_type_class("haywire-core:type:COLOR") is not None
    assert reg.get_type_class("haywire-core:type:VEC3F") is not None
