"""@farmhand stamps identity; naming and annotations follow the spec."""

import pytest

from haywire.core.farmhand import Farmhand, ToolAnnotations, farmhand

pytestmark = pytest.mark.unit


def _studio_identity():
    from haywire.core.library.identity import LibraryIdentity

    return LibraryIdentity(
        label="Studio",
        version="0.1",
        description="",
        author_url="",
        folder_path="/tmp/studio",
        module_name="studio",
        id="studio",
    )


@pytest.fixture(autouse=True)
def _stub_library_identity(monkeypatch):
    """These unit tests run outside any library module, so stub the derivation
    (patch the name the decorator module imported, not the utils original)."""
    from haywire.core.farmhand import decorator as decorator_module

    monkeypatch.setattr(
        decorator_module,
        "derive_library_identity",
        lambda cls: _studio_identity(),
    )


def _make_tool():
    @farmhand(
        label="Status",
        description="Report studio status.",
        registry_id="status",
        annotations=ToolAnnotations(read_only_hint=True),
    )
    class StatusTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    return StatusTool


def test_identity_and_mcp_name():
    tool = _make_tool()
    assert tool.class_identity.registry_key == "studio:farmhand:status"
    assert tool.class_library.id == "studio"
    assert tool.mcp_name() == "studio_status"
    assert tool.class_identity.annotations.read_only_hint is True


def test_registry_id_defaults_to_class_name():
    # Established pattern (@node/@state): verbatim class name, no transformation.
    @farmhand()
    class ListOpenGraphs(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert ListOpenGraphs.class_identity.registry_key == "studio:farmhand:ListOpenGraphs"


def test_sync_run_rejected():
    with pytest.raises(TypeError, match="async"):

        @farmhand()
        class BadTool(Farmhand):
            def run(self, ctx) -> dict:  # type: ignore[override]
                return {}


def test_non_subclass_rejected():
    with pytest.raises(TypeError):

        @farmhand()
        class NotATool:
            async def run(self, ctx) -> dict:
                return {}


def test_input_schema_uses_override_when_present():
    @farmhand()
    class Overridden(Farmhand):
        input_schema_override = {"type": "object", "properties": {"q": {"type": "string"}}}

        async def run(self, ctx, q: str) -> dict:
            return {}

    assert Overridden.input_schema() == Overridden.input_schema_override


def test_annotations_to_dict_camelcase():
    d = ToolAnnotations(read_only_hint=True, destructive_hint=True).to_dict()
    assert d == {
        "readOnlyHint": True,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def test_inherited_baseidentity_field_passes_through():
    # @node's **kwargs shape means BaseIdentity fields flow through for free.
    @farmhand(hidden=True)
    class HiddenTool(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert HiddenTool.class_identity.hidden is True


def test_unknown_kwarg_raises():
    with pytest.raises(TypeError):

        @farmhand(not_a_field="oops")
        class BadFieldTool(Farmhand):
            async def run(self, ctx) -> dict:
                return {}
