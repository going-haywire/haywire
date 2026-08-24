# tests/ui/panel/test_panel_registry_class_keyed.py
"""PanelRegistry routes on ``Surface.id``, never on the surface class object.

The old fork matched action panels by Protocol *class identity* — defensible
only while a panel and its Protocol were guaranteed to reload together. All
three queries now compare ids, because ``hosts=`` holds classes captured at
decoration time and a panel may host a surface from a library that reloads on
its own schedule (docs/adr/0009-surface-id-stable-key.md).
"""

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.surface import Surface


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


class _SurfaceOne(Surface):
    id = "one_test_surface"


class _SurfaceTwo(Surface):
    id = "two_test_surface"


class _HostedSurface(Surface):
    id = "hosted_test_surface"


@panel(surface=_SurfaceOne, label="A1")
class _PanelA1(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_SurfaceTwo, label="A2")
class _PanelA2(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_SurfaceOne, hosts=(_HostedSurface,), label="B1")
class _PanelB1(BasePanel):
    def draw(self, ctx, layout):
        pass


def _registry_with_panels() -> PanelRegistry:
    """Build a registry, manually register the test panels."""
    reg = PanelRegistry()
    for cls in (_PanelA1, _PanelA2, _PanelB1):
        reg._register_class(cls, _FAKE_LIBRARY_IDENTITY)
    return reg


def test_get_panels_filters_by_surface():
    reg = _registry_with_panels()
    panels = reg.get_panels(_SurfaceOne)
    assert _PanelA1 in panels
    assert _PanelB1 in panels
    assert _PanelA2 not in panels  # different surface


def test_get_panels_returns_empty_for_a_surface_with_no_panels():
    reg = _registry_with_panels()

    class _Unrelated(Surface):
        id = "unrelated_test_surface"

    assert reg.get_panels(_Unrelated) == []


def test_get_panels_matches_a_reloaded_surface_by_id():
    """A hot-reload hands back a *new class object* with the same id."""
    reg = _registry_with_panels()

    class _ReloadedOne:
        id = "one_test_surface"

    assert _PanelA1 in reg.get_panels(_ReloadedOne)


def test_get_root_surfaces_deduplicates_by_id():
    reg = PanelRegistry()

    @panel(surface=_SurfaceOne, label="Dup1", registry_id="dup1_ck")
    class _DupPanel1(BasePanel):
        def draw(self, ctx, layout):
            pass

    @panel(surface=_SurfaceOne, label="Dup2", registry_id="dup2_ck")
    class _DupPanel2(BasePanel):
        def draw(self, ctx, layout):
            pass

    reg._register_class(_DupPanel1, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_DupPanel2, _FAKE_LIBRARY_IDENTITY)
    assert reg.get_root_surfaces().count(_SurfaceOne) == 1


def test_get_root_surfaces_excludes_a_surface_named_in_hosts():
    reg = _registry_with_panels()

    @panel(surface=_HostedSurface, label="Nested", registry_id="nested_ck")
    class _NestedPanel(BasePanel):
        def draw(self, ctx, layout):
            pass

    reg._register_class(_NestedPanel, _FAKE_LIBRARY_IDENTITY)
    roots = reg.get_root_surfaces()
    assert _SurfaceOne in roots
    assert _HostedSurface not in roots


# ---------------------------------------------------------------------------
# Regression test: folder-scan registration accepts decorated BasePanel subclasses
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
