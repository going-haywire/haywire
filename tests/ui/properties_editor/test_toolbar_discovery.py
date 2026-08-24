# tests/ui/properties_editor/test_toolbar_discovery.py
"""The SurfaceToolbar lists root surfaces that declare ``presentation``.

Root-ness comes from ``registry.get_root_surfaces()``; the ``presentation``
filter is the strip's own discovery policy. Every other host names the
surface it opens, so only this one needs a filter at all (ADR-0029,
Presentation).
"""

from __future__ import annotations

from haywire.core.library.identity import LibraryIdentity
from haywire.ui.panel import BasePanel, PanelRegistry, panel
from haywire.ui.surface import Presentation, Surface


_FAKE_LIBRARY_IDENTITY = LibraryIdentity(
    label="fake",
    version="0.1",
    folder_path="/tmp/fake",
    module_name="fake",
    name="fake",
)


class _LowOrderTab(Surface):
    id = "library_low_order_surface_test"
    order = 10
    presentation = Presentation(label="Low", icon="library_books")


class _HighOrderTab(Surface):
    id = "library_high_order_surface_test"
    order = 90
    presentation = Presentation(label="High", icon="library_books")


class _MenuSurface(Surface):
    """A root surface with no chrome of its own — not a tab."""

    id = "library_menu_surface_test"
    order = 20


class _HostedTab(Surface):
    """Declares presentation but is hosted, so a panel draws it, not the strip."""

    id = "library_hosted_surface_test"
    order = 15
    presentation = Presentation(label="Hosted", icon="library_books")


@panel(surface=_LowOrderTab, label="Low Panel")
class _LowOrderPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_HighOrderTab, hosts=(_HostedTab,), label="High Panel")
class _HighOrderPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_MenuSurface, label="Menu Panel")
class _MenuPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


@panel(surface=_HostedTab, label="Hosted Panel")
class _HostedPanel(BasePanel):
    def draw(self, ctx, layout):
        pass


def _stub_wrapper():
    """Minimal wrapper stand-in — toolbar discovery never reads it."""
    from typing import cast
    from haywire.ui.editor.wrapper import EditorWrapper

    return cast(EditorWrapper, object())


def test_toolbar_empty_registry_yields_no_surfaces():
    """With no panels registered, the toolbar is empty."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    editor = PropertiesEditor(_stub_wrapper())
    assert editor._compute_toolbar_surfaces(PanelRegistry()) == []


def test_toolbar_includes_library_surface_via_registry():
    """A library-defined surface appears in the toolbar via registry discovery."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_LowOrderPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    assert _LowOrderTab in editor._compute_toolbar_surfaces(reg)


def test_toolbar_surfaces_are_sorted_by_order():
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    # Register in reverse-order so the discovered set order doesn't trivially match.
    reg._register_class(_HighOrderPanel, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_LowOrderPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    surfaces = editor._compute_toolbar_surfaces(reg)
    assert surfaces.index(_LowOrderTab) < surfaces.index(_HighOrderTab)


def test_toolbar_excludes_a_surface_without_presentation():
    """A menu surface is a root, but has no chrome to draw — so not a tab."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_MenuPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    assert reg.get_root_surfaces() == [_MenuSurface]
    assert editor._compute_toolbar_surfaces(reg) == []


def test_toolbar_excludes_a_hosted_surface_even_with_presentation():
    """A surface some panel hosts is drawn by that panel, not by the strip."""
    from haybale_studio.editors.properties_editor import PropertiesEditor

    reg = PanelRegistry()
    reg._register_class(_HighOrderPanel, _FAKE_LIBRARY_IDENTITY)
    reg._register_class(_HostedPanel, _FAKE_LIBRARY_IDENTITY)
    editor = PropertiesEditor(_stub_wrapper())
    surfaces = editor._compute_toolbar_surfaces(reg)
    assert _HighOrderTab in surfaces
    assert _HostedTab not in surfaces


def test_no_real_menu_surface_declares_presentation():
    """The synthetic surfaces above prove the filter's *mechanism*; this
    proves the *catalog* obeys it — every in-tree menu/toolbar/region surface
    (as opposed to a properties tab) declares no ``presentation``, so none of
    them could ever slip into the strip even if some future panel forgot to
    nest it under a host. Guards the invariant Task C's review flagged."""
    from haybale_graph_editor.surfaces import (
        EdgeMenu,
        GraphContext,
        GraphContextBody,
        GraphMoreActions,
        GraphToolBar,
        PinMenu,
        SelectionMenu,
        SelectionToolbar,
    )
    from haywire.barn.builtin.surfaces import AccountMenu

    menu_surfaces = [
        GraphContext,
        GraphToolBar,
        GraphContextBody,
        GraphMoreActions,
        EdgeMenu,
        SelectionMenu,
        PinMenu,
        SelectionToolbar,
        AccountMenu,
    ]
    for surface in menu_surfaces:
        assert surface.presentation is None, f"{surface.id!r} is a menu surface but declares presentation"
