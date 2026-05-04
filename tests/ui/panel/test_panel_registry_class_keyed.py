# tests/ui/panel/test_panel_registry_class_keyed.py
"""PanelRegistry.get_panels_for and get_focuses_for use isinstance + focus-class match."""

from typing import Protocol, runtime_checkable

from haywire.ui.panel import Panel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


@runtime_checkable
class _ActionsA(Protocol):
    def verb_a(self) -> None: ...


@runtime_checkable
class _ActionsB(Protocol):
    def verb_b(self) -> None: ...


class _FocusOne(Focus):
    id = "one_test_focus"
    label = "One"
    icon = "1"

    @classmethod
    def available(cls, ctx):
        return True


class _FocusTwo(Focus):
    id = "two_test_focus"
    label = "Two"
    icon = "2"

    @classmethod
    def available(cls, ctx):
        return True


@panel(action=_ActionsA, focus=_FocusOne, label="A1")
class _PanelA1(Panel):
    def draw(self, ctx, layout, actions):
        pass


@panel(action=_ActionsA, focus=_FocusTwo, label="A2")
class _PanelA2(Panel):
    def draw(self, ctx, layout, actions):
        pass


@panel(action=_ActionsB, focus=_FocusOne, label="B1")
class _PanelB1(Panel):
    def draw(self, ctx, layout, actions):
        pass


class _ProviderA:
    def verb_a(self) -> None:
        pass


class _ProviderB:
    def verb_b(self) -> None:
        pass


def _registry_with_panels() -> PanelRegistry:
    """Build a registry, manually register the test panels."""
    reg = PanelRegistry()
    for cls in (_PanelA1, _PanelA2, _PanelB1):
        reg._register_class(cls)
    return reg


def test_get_panels_for_filters_by_action_and_focus():
    reg = _registry_with_panels()
    p = _ProviderA()
    panels = reg.get_panels_for(actions_provider=p, focus=_FocusOne)
    assert _PanelA1 in panels
    assert _PanelA2 not in panels  # wrong focus
    assert _PanelB1 not in panels  # wrong action


def test_get_panels_for_returns_empty_when_action_doesnt_satisfy():
    reg = _registry_with_panels()

    class _Unrelated:
        pass

    panels = reg.get_panels_for(actions_provider=_Unrelated(), focus=_FocusOne)
    assert panels == []


def test_get_focuses_for_returns_focuses_referenced_by_compatible_panels():
    reg = _registry_with_panels()
    p_a = _ProviderA()
    focuses = reg.get_focuses_for(actions_provider=p_a)
    assert _FocusOne in focuses
    assert _FocusTwo in focuses

    p_b = _ProviderB()
    focuses_b = reg.get_focuses_for(actions_provider=p_b)
    assert _FocusOne in focuses_b
    assert _FocusTwo not in focuses_b


# ---------------------------------------------------------------------------
# Regression test: folder-scan registration accepts new-contract Panel subclasses
# ---------------------------------------------------------------------------


def test_class_filter_accepts_decorated_panel_subclass():
    """Regression: PanelRegistry._class_filter must accept Panel subclasses
    decorated with @panel. Without this, the folder scanner silently skips
    every panel at startup."""
    reg = PanelRegistry()
    assert reg._class_filter(_PanelA1) is True
    assert reg._class_filter(_PanelA2) is True
    assert reg._class_filter(_PanelB1) is True


def test_class_filter_rejects_panel_base_itself():
    reg = PanelRegistry()
    assert reg._class_filter(Panel) is False


def test_class_filter_rejects_unrelated_class():
    reg = PanelRegistry()

    class NotAPanel:
        pass

    assert reg._class_filter(NotAPanel) is False
