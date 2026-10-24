"""requires= on panel, editor and farmhand identities — and NOT on BaseIdentity."""

import dataclasses

import pytest

from haywire.core.access import AccessTier
from haywire.core.farmhand.identity import FarmhandIdentity
from haywire.core.registry.identity import BaseIdentity
from haywire.ui.editor.identity import EditorIdentity
from haywire.ui.panel.identity import PanelIdentity


def _fields(cls):
    return {f.name for f in dataclasses.fields(cls)}


def test_base_identity_has_no_requires_field():
    """A node/skin/widget identity governs an authoring menu, not a running graph."""
    assert "requires" not in _fields(BaseIdentity)


@pytest.mark.parametrize("cls", [PanelIdentity, EditorIdentity, FarmhandIdentity])
def test_surface_identities_have_requires(cls):
    assert "requires" in _fields(cls)


def test_panel_identity_defaults_to_edit():
    identity = PanelIdentity(registry_id="p", registry_key="k", label="L")
    assert identity.requires is AccessTier.EDIT


def test_editor_identity_defaults_to_edit():
    identity = EditorIdentity(registry_id="e", registry_key="k", label="L")
    assert identity.requires is AccessTier.EDIT


def test_editor_decorator_without_requires_gives_edit():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    @editor(label="Z")
    class _Z(BaseEditor):
        def draw(self, context, container): ...

    assert _Z.class_identity.requires is AccessTier.EDIT


def test_panel_decorator_without_requires_gives_edit():
    from haywire.barn.builtin.surfaces import AppSettings
    from haywire.ui.panel.base import BasePanel
    from haywire.ui.panel.decorator import panel

    @panel(label="P", surface=AppSettings)
    class _P(BasePanel):
        def draw(self, ctx, container): ...

    assert _P.class_identity.requires is AccessTier.EDIT


def test_farmhand_identity_defaults_to_edit():
    identity = FarmhandIdentity(registry_id="f", registry_key="k", label="L", instructions="i")
    assert identity.requires is AccessTier.EDIT


def test_farmhand_decorator_without_requires_gives_edit():
    from haywire.core.farmhand import Farmhand, farmhand

    @farmhand(instructions="i")
    class _F(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert _F.class_identity.requires is AccessTier.EDIT


def test_farmhand_decorator_accepts_a_lowered_requirement():
    from haywire.core.farmhand import Farmhand, farmhand

    @farmhand(instructions="i", requires=AccessTier.VIEW)
    class _F(Farmhand):
        async def run(self, ctx) -> dict:
            return {}

    assert _F.class_identity.requires is AccessTier.VIEW


# --- decorator coercion ------------------------------------------------


def test_editor_decorator_accepts_the_enum():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    @editor(label="X", requires=AccessTier.ADMIN)
    class _X(BaseEditor):
        def draw(self, context, container): ...

    assert _X.class_identity.requires is AccessTier.ADMIN


def test_editor_decorator_coerces_a_string():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    @editor(label="Y", requires="edit")
    class _Y(BaseEditor):
        def draw(self, context, container): ...

    assert _Y.class_identity.requires is AccessTier.EDIT


def test_editor_decorator_rejects_an_unknown_tier_at_definition_time():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    with pytest.raises(ValueError, match=".*"):

        @editor(label="Z", requires="superuser")
        class _Z(BaseEditor):
            def draw(self, context, container): ...
