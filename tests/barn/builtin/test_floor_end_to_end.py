import pytest

import haywire.core.graph.editor  # noqa: F401


@pytest.mark.integration
def test_builtin_types_resolve_through_registry(library_system):
    """After full init, the type registry resolves builtin:type:* keys."""
    reg = library_system.get_type_registry()
    assert reg.get_type_class("builtin:type:INT") is not None
    assert reg.get_type_class("builtin:type:FLOAT") is not None
    assert reg.get_type_class("builtin:type:COLOR") is not None
    assert reg.get_type_class("builtin:type:VEC3F") is not None
