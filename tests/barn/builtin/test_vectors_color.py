from haywire.barn.builtin.types import VEC2I, VEC3F
from haywire.core.settings.types import Vec2i, Vec3f


def test_vec3f_key_and_element_type():
    assert VEC3F.class_identity.registry_key == "haywire-core:type:VEC3F"
    assert VEC3F.element_type_cls is Vec3f


def test_vec2i_key_and_element_type():
    assert VEC2I.class_identity.registry_key == "haywire-core:type:VEC2I"
    assert VEC2I.element_type_cls is Vec2i


def test_color_is_its_own_type():
    from haywire.barn.builtin.types import COLOR, ColorStr

    assert COLOR.class_identity.registry_key == "haywire-core:type:COLOR"
    # COLOR wraps a real str subclass, NOT plain str, so it is distinct from STRING.
    assert issubclass(ColorStr, str)
    assert COLOR.element_type_cls is ColorStr
    assert COLOR.element_type_cls is not str
