import haywire.core.graph.editor  # noqa: F401

import pytest


def test_choices_is_a_string_subtype():
    from haywire.barn.builtin.types import CHOICES, STRING

    assert issubclass(CHOICES, STRING)
    assert CHOICES("fast").to_dict() == {"value": "fast"}
    assert CHOICES.from_dict({"value": "fast"}) == "fast"


def test_choices_default_widget_is_select():
    from haywire.barn.builtin.types import CHOICES
    from haywire.barn.builtin import widget_keys

    assert CHOICES.class_identity.widget_key == widget_keys.SELECT_WIDGET


@pytest.mark.integration
def test_string_to_choices_needs_an_explicit_adapter(library_system):
    """A promoted CHOICES inlet fed by a STRING outlet needs StringToChoicesAdapter:
    CHOICES is the descendant, and per adapter-canon.md an ancestor->descendant
    conversion is never a free passthrough (not every string is a valid choice)."""
    reg = library_system.get_adapter_registry()

    fwd = reg.get_adapter("builtin:type:STRING", "builtin:type:CHOICES")
    assert fwd is not None


@pytest.mark.integration
def test_choices_to_string_needs_no_adapter(library_system):
    """CHOICES(STRING) -> STRING is a free child->parent passthrough (AdapterFactory's
    issubclass check) — no adapter should be registered for this direction, since one
    was already found to be dead code (registry lookup for this pair is never reached)."""
    from haywire.barn.builtin.types import CHOICES, STRING
    from haywire.core.adapter.factory import AdapterFactory

    reg = library_system.get_adapter_registry()
    factory = AdapterFactory(reg)

    adapter, error = factory.create_chain(CHOICES, STRING, edge_id="test-edge")

    assert error is None
    assert adapter is not None
    assert adapter._get_registry_keys() == []  # ReturnAdapter: no adapter chain used
    assert reg.get_adapter("builtin:type:CHOICES", "builtin:type:STRING") is None
