import haywire.core.graph.editor  # noqa: F401

from haywire.barn.builtin.types import BOOL, FLOAT, INT, STRING


def test_scalar_keys_are_builtin_namespaced():
    """Hoisted scalars derive a builtin:type:* key from the library id."""
    assert INT.class_identity.registry_key == "builtin:type:INT"
    assert FLOAT.class_identity.registry_key == "builtin:type:FLOAT"
    assert STRING.class_identity.registry_key == "builtin:type:STRING"
    assert BOOL.class_identity.registry_key == "builtin:type:BOOL"


def test_scalar_element_types():
    assert FLOAT.element_type_cls is float
    assert INT.element_type_cls is int
    assert STRING.element_type_cls is str
    assert BOOL.element_type_cls is bool
