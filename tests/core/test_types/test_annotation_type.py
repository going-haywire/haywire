"""The annotation wire: drawn and saved, never executed, styled per edge."""

import pytest

from haywire.core.edge.style import STYLE_FIELDS
from haywire.core.settings import settings_fields
from haywire.core.types.wire import WireRole, wire_type_of

pytestmark = pytest.mark.unit


def test_the_annotation_wire_is_visual_and_styled():
    from haywire.barn.builtin.types.annotation import AnnotationStyle, AnnotationWire

    assert AnnotationWire.role is WireRole.VISUAL
    assert AnnotationWire.propagation == ()
    assert AnnotationWire.pin_kind == "annotation"
    assert AnnotationWire.style is AnnotationStyle
    assert AnnotationWire.id == "haywire-core:wire:AnnotationWire"


def test_the_style_declares_every_recognised_field():
    from haywire.barn.builtin.types.annotation import AnnotationStyle

    assert tuple(settings_fields(AnnotationStyle)) == STYLE_FIELDS


def test_annotation_travels_on_the_annotation_wire_and_has_no_widget():
    from haywire.barn.builtin.types import ADD, ANNOTATION
    from haywire.barn.builtin.types.annotation import AnnotationWire

    for type_cls in (ANNOTATION, ADD[ANNOTATION]):
        wire = wire_type_of(type_cls)
        assert wire is not None
        assert wire.id == AnnotationWire.id
    assert ANNOTATION.class_identity.widget_key is None
