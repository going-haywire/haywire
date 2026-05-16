# tests/ui/panel/test_panel_registry_class_keyed.py
"""PanelRegistry.get_panels_for_action and get_display_focuses use protocol identity + focus-id match."""

from typing import Protocol, runtime_checkable

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.panel.focus import Focus


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    description="test",
    url="",
    help_url="",
    author="",
    author_url="",
    folder_path="/tmp/fake",
    module_name="fake",
    id="fake",
)


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


# Action panels — have `actions:` annotation and actions= decorator arg.
@panel(actions=_ActionsA, focus=_FocusOne, label="A1")
class _PanelA1(BasePanel):
    actions: _ActionsA

    def draw(self, ctx, layout):
        pass


@panel(actions=_ActionsA, focus=_FocusTwo, label="A2")
class _PanelA2(BasePanel):
    actions: _ActionsA

    def draw(self, ctx, layout):
        pass


@panel(actions=_ActionsB, focus=_FocusOne, label="B1")
class _PanelB1(BasePanel):
    actions: _ActionsB

    def draw(self, ctx, layout):
        pass


# Display panels (no actions: annotation) — used to test get_display_focuses.
@panel(focus=_FocusOne, label="Display-One", registry_id="display_one_ck")
class _DisplayPanelOne(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(focus=_FocusTwo, label="Display-Two", registry_id="display_two_ck")
class _DisplayPanelTwo(BasePanel):
    def draw(self, ctx, layout):
        pass


def _registry_with_panels() -> PanelRegistry:
    """Build a registry, manually register the test panels."""
    reg = PanelRegistry()
    for cls in (_PanelA1, _PanelA2, _PanelB1):
        reg._register_class(cls, _FAKE_LIBRARY_IDENTITY)
    return reg


def test_get_panels_for_action_filters_by_protocol_and_focus():
    reg = _registry_with_panels()
    panels = reg.get_panels_for_action(_ActionsA, _FocusOne)
    assert _PanelA1 in panels
    assert _PanelA2 not in panels  # wrong focus
    assert _PanelB1 not in panels  # wrong protocol


def test_get_panels_for_action_returns_empty_when_protocol_not_registered():
    reg = _registry_with_panels()

    @runtime_checkable
    class _Unrelated(Protocol):
        def unrelated_verb(self) -> None: ...

    panels = reg.get_panels_for_action(_Unrelated, _FocusOne)
    assert panels == []


def test_get_display_focuses_returns_focuses_referenced_by_display_panels():
    reg = PanelRegistry()
    reg._register_class(_DisplayPanelOne, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_DisplayPanelTwo, _FAKE_LIBRARY_IDENTITY)
    focuses = reg.get_display_focuses()
    assert _FocusOne in focuses
    assert _FocusTwo in focuses


def test_get_display_focuses_excludes_action_panel_focuses():
    reg = _registry_with_panels()
    # Only action panels registered — get_display_focuses must return nothing.
    focuses = reg.get_display_focuses()
    assert _FocusOne not in focuses
    assert _FocusTwo not in focuses


def test_get_display_focuses_deduplicates_by_focus_id():
    # Register two display panels with the same focus — each focus appears once.
    reg = PanelRegistry()

    @panel(focus=_FocusOne, label="Dup1", registry_id="dup1_ck")
    class _DupPanel1(BasePanel):
        def draw(self, ctx, layout):
            pass

    @panel(focus=_FocusOne, label="Dup2", registry_id="dup2_ck")
    class _DupPanel2(BasePanel):
        def draw(self, ctx, layout):
            pass

    reg._register_class(_DupPanel1, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_DupPanel2, _FAKE_LIBRARY_IDENTITY)
    focuses = reg.get_display_focuses()
    assert focuses.count(_FocusOne) == 1


# ---------------------------------------------------------------------------
# Regression test: folder-scan registration accepts new-contract BasePanel subclasses
# ---------------------------------------------------------------------------


def test_class_filter_accepts_decorated_panel_subclass():
    """Regression: PanelRegistry._class_filter must accept BasePanel subclasses
    decorated with @panel. Without this, the folder scanner silently skips
    every panel at startup."""
    reg = PanelRegistry()
    assert reg._class_filter(_PanelA1) is True
    assert reg._class_filter(_PanelA2) is True
    assert reg._class_filter(_PanelB1) is True


def test_class_filter_rejects_panel_base_itself():
    reg = PanelRegistry()
    assert reg._class_filter(BasePanel) is False


def test_class_filter_rejects_unrelated_class():
    reg = PanelRegistry()

    class NotAPanel:
        pass

    assert reg._class_filter(NotAPanel) is False
