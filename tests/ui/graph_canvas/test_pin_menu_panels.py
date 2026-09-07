"""Tests for the PinMenu identity panels (Type / Widget).

Both rows are ungated navigation: they resolve a registry key and publish
``RevealComponentSource``. ``poll`` is the load-bearing half — a row that
polls true without a resolvable key would render a dead entry, and the
widget row must vanish entirely on a port that has no widget.
"""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from haywire.core.session.context import SessionContext
from haywire.core.signals import RevealComponentSource
from haybale_graph_editor.panels.graph.menu.port.port import (
    DetachSettingMenuPanel,
    PinEditMenuPanel,
    PortTypeMenuPanel,
    PortWidgetMenuPanel,
)


def _ctx(port: Any) -> SessionContext:
    """A SessionContext whose EditState lookup yields a stub holding *port*.

    Mirrors ``test_session_context_menu_provider._make_provider``: the data
    namespace is stubbed so the lookup resolves regardless of the EditState
    class identity, which differs across a library hot-reload.
    """
    edit_stub = SimpleNamespace(active_port=port, active_node=None)
    fake_data = MagicMock()
    fake_data.__getitem__.return_value = edit_stub
    ctx = SessionContext(session_id="t", app=MagicMock())
    ctx.data = fake_data
    ctx.session = MagicMock()
    return ctx


class _Identity:
    def __init__(self, registry_key: str, label: str = "") -> None:
        self.registry_key = registry_key
        self.label = label


def _port(*, stored_type: Any = None, widget_key: str | None = None, promoted: bool = False) -> Any:
    return SimpleNamespace(
        id="value",
        stored_type=stored_type,
        widget_key=widget_key,
        promoted=promoted,
    )


def _typed(registry_key: str = "core:vec3", label: str = "Vec3") -> type:
    """A stand-in IType carrying the class_identity registration stamps on."""
    return cast(type, type("Vec3", (), {"class_identity": _Identity(registry_key, label)}))


# ---------------------------------------------------------------------------
# Type row
# ---------------------------------------------------------------------------


def test_type_row_polls_false_without_a_port():
    assert PortTypeMenuPanel.poll(_ctx(None)) is False


def test_type_row_polls_true_for_a_registered_type():
    assert PortTypeMenuPanel.poll(_ctx(_port(stored_type=_typed()))) is True


def test_type_row_polls_false_for_an_unregistered_type():
    """An unregistered class (test double, generated type) has no
    class_identity, so there is no key to open — draw no row rather than a
    dead one."""
    bare = cast(type, type("Bare", (), {}))
    assert PortTypeMenuPanel.poll(_ctx(_port(stored_type=bare))) is False


# ---------------------------------------------------------------------------
# Widget row
# ---------------------------------------------------------------------------


def test_widget_row_polls_false_when_the_port_has_no_widget():
    """An outlet, or an inlet whose type carries no editor."""
    assert PortWidgetMenuPanel.poll(_ctx(_port(widget_key=None))) is False


def test_widget_row_polls_false_for_an_uninstalled_widget_key():
    """widget_key is resolved through the registry, never trusted: a key
    naming a widget that isn't installed resolves to None."""
    assert PortWidgetMenuPanel.poll(_ctx(_port(widget_key="nope:widget:missing"))) is False


def test_widget_row_polls_true_for_a_registered_widget(monkeypatch: pytest.MonkeyPatch):
    from haywire.ui.widget import globals as widget_globals

    widget_cls = type("NumberWidget", (), {"class_identity": _Identity("core:widget:number", "Number")})
    monkeypatch.setitem(widget_globals.WIDGET_REGISTRY, "core:widget:number", cast(Any, widget_cls))

    assert PortWidgetMenuPanel.poll(_ctx(_port(widget_key="core:widget:number"))) is True


# ---------------------------------------------------------------------------
# Detach (unchanged behaviour, re-checked after the reorder)
# ---------------------------------------------------------------------------


def test_detach_polls_only_on_a_promoted_port():
    assert DetachSettingMenuPanel.poll(_ctx(_port(promoted=True))) is True
    assert DetachSettingMenuPanel.poll(_ctx(_port(promoted=False))) is False


def test_detach_still_draws_greyed_when_it_does_not_apply():
    """PinMenu's ONLY leaf, and the popup opens only if a leaf drew.

    The Edit row beside it is a hosting panel, excluded from the leaf count
    on purpose, and the counter resets per flyout level so its submenu body
    never reaches the popup's count. If this panel vanished on an unpromoted
    pin the popup would have zero leaves and be deleted — no pin menu at all
    on most pins, and no edge-drag resume either. Overriding draw_disabled is
    what keeps the count at one; the base class default is a no-op, so this
    is a real override, not inherited behaviour.
    """
    assert "draw_disabled" in vars(DetachSettingMenuPanel)


# ---------------------------------------------------------------------------
# Reveal
# ---------------------------------------------------------------------------


def test_clicking_a_row_publishes_reveal_component_source():
    """The row reveals rather than only assigning active_component: from a
    pin right-click the CONTEXT slot may be collapsed, and only a reveal
    expands it."""
    from haybale_graph_editor.panels.graph.menu.component_rows import reveal_component

    ctx = _ctx(_port())
    reveal_component(ctx, "core:vec3")

    published = cast(Any, ctx.session).publish.call_args[0][0]
    assert isinstance(published, RevealComponentSource)
    assert published.registry_key == "core:vec3"


def test_edit_submenu_rows_are_ordered_type_then_widget():
    orders = [
        PortTypeMenuPanel.class_identity.order,
        PortWidgetMenuPanel.class_identity.order,
    ]
    assert orders == sorted(orders)
    assert len(set(orders)) == 2


def test_edit_row_sits_before_detach_on_the_parent_menu():
    """Identity first, verbs after — the row order the menu reads in."""
    assert PinEditMenuPanel.class_identity.order < DetachSettingMenuPanel.class_identity.order


def test_edit_row_polls_on_what_its_body_will_hold():
    """A submenu whose body would be empty must not draw its anchor: a
    ``hui.submenu_row`` with nothing inside greys itself retroactively, which
    reads as a broken command rather than an absent one."""
    assert PinEditMenuPanel.poll(_ctx(_port(stored_type=_typed()))) is True
    assert PinEditMenuPanel.poll(_ctx(_port())) is False
    assert PinEditMenuPanel.poll(_ctx(None)) is False


def test_edit_row_hosts_the_pin_edit_surface():
    from haybale_graph_editor.surfaces import PinEditMenu

    hosted = {s.id for s in PinEditMenuPanel.class_identity.hosts}
    assert PinEditMenu.id in hosted
