"""access= on panel, editor and farmhand identities — and NOT on BaseIdentity."""

import dataclasses

import pytest

from haywire.core.access import AccessTier
from haywire.core.farmhand.identity import FarmhandIdentity
from haywire.core.registry.identity import BaseIdentity
from haywire.ui.editor.identity import EditorIdentity
from haywire.ui.panel.identity import PanelIdentity


def _fields(cls):
    return {f.name for f in dataclasses.fields(cls)}


def test_base_identity_has_no_access_field():
    """A node/skin/widget identity governs an authoring menu, not a running graph."""
    assert "access" not in _fields(BaseIdentity)


@pytest.mark.parametrize("cls", [PanelIdentity, EditorIdentity, FarmhandIdentity])
def test_surface_identities_have_access(cls):
    assert "access" in _fields(cls)


def test_panel_identity_defaults_to_view():
    identity = PanelIdentity(registry_id="p", registry_key="k", label="L")
    assert identity.access is AccessTier.VIEW


def test_editor_identity_defaults_to_view():
    identity = EditorIdentity(registry_id="e", registry_key="k", label="L")
    assert identity.access is AccessTier.VIEW


def test_farmhand_identity_defaults_to_view():
    identity = FarmhandIdentity(registry_id="f", registry_key="k", label="L", instructions="i")
    assert identity.access is AccessTier.VIEW


# --- decorator coercion ------------------------------------------------


def test_editor_decorator_accepts_the_enum():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    @editor(label="X", access=AccessTier.ADMIN)
    class _X(BaseEditor):
        def draw(self, context, container): ...

    assert _X.class_identity.access is AccessTier.ADMIN


def test_editor_decorator_coerces_a_string():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    @editor(label="Y", access="edit")
    class _Y(BaseEditor):
        def draw(self, context, container): ...

    assert _Y.class_identity.access is AccessTier.EDIT


def test_editor_decorator_rejects_an_unknown_tier_at_definition_time():
    from haywire.ui.editor.base import BaseEditor
    from haywire.ui.editor.decorator import editor

    with pytest.raises(ValueError, match=".*"):

        @editor(label="Z", access="superuser")
        class _Z(BaseEditor):
            def draw(self, context, container): ...
