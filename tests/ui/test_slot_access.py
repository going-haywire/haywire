"""access= enforcement in the editor slots."""

from typing import Any, cast
from unittest.mock import MagicMock

from haywire.core.access import AccessTier
from haywire.ui.app.slot import Slot
from haywire.ui.editor.identity import EditorIdentity, SlotName


def _editor_cls(name: str, access: AccessTier):
    cls = cast(Any, type(name, (), {}))
    cls.class_identity = EditorIdentity(
        registry_id=name, registry_key=f"lib:editor:{name}", label=name, access=access
    )
    return cls


def _wrapper(name: str, access: AccessTier):
    wrapper = MagicMock()
    wrapper.editor_cls = _editor_cls(name, access)
    wrapper.editor_key = f"lib:editor:{name}"
    wrapper.editor_binding_id = name
    return wrapper


class _TestSlot(Slot):
    _ORIENTATION = "horizontal"

    def render(self, parent): ...

    def _render_bar_contents(self): ...


def _slot(tier: AccessTier):
    session = MagicMock()
    session.context.can_access.side_effect = lambda required: tier.satisfies(required)
    registry = MagicMock()
    return _TestSlot(session=session, name=SlotName.EDIT, registry=registry)


def test_accessible_bindings_filters_by_tier():
    slot = _slot(AccessTier.VIEW)
    slot._bindings = [
        _wrapper("ViewE", AccessTier.VIEW),
        _wrapper("AdminE", AccessTier.ADMIN),
    ]
    assert [w.editor_binding_id for w in slot._accessible_bindings()] == ["ViewE"]


def test_admin_sees_all_bindings():
    slot = _slot(AccessTier.ADMIN)
    slot._bindings = [
        _wrapper("ViewE", AccessTier.VIEW),
        _wrapper("AdminE", AccessTier.ADMIN),
    ]
    assert len(slot._accessible_bindings()) == 2


def test_accessible_bindings_reevaluates_after_demotion():
    """Live tier read: no re-login, no eviction — the next redraw simply shows less."""
    tier = {"value": AccessTier.ADMIN}
    session = MagicMock()
    session.context.can_access.side_effect = lambda required: tier["value"].satisfies(required)
    slot = _TestSlot(session=session, name=SlotName.EDIT, registry=MagicMock())
    slot._bindings = [_wrapper("AdminE", AccessTier.ADMIN)]

    assert len(slot._accessible_bindings()) == 1
    tier["value"] = AccessTier.VIEW
    assert slot._accessible_bindings() == []


def test_wrapper_without_editor_cls_is_dropped():
    slot = _slot(AccessTier.ADMIN)
    orphan = MagicMock()
    orphan.editor_cls = None
    slot._bindings = [orphan]
    assert slot._accessible_bindings() == []


def test_editor_accessible_treats_a_missing_identity_as_view():
    slot = _slot(AccessTier.VIEW)
    assert slot._editor_accessible(type("NoIdentity", (), {})) is True
